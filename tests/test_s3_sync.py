"""Tests for the S3 sync (SPEC Phase E + ADR-0001).

Uses moto's in-process S3 mock so the tests run offline + don't
need real AWS credentials. Per ADR-0001, the function refuses to
upload without explicit auth — we set fake AWS creds via monkeypatch
to satisfy that gate.
"""

from __future__ import annotations

import pytest

# moto[s3] required; declared in [dev] extras
moto = pytest.importorskip("moto")
boto3 = pytest.importorskip("boto3")

from ai_config_kit import ClaudeConfig, ConfigError, S3SyncReport  # noqa: E402


@pytest.fixture
def mock_aws_creds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set fake AWS env vars so the auth gate passes."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.delenv("AWS_PROFILE", raising=False)


# --- auth-gate path ------------------------------------------------------


def test_sync_to_s3_refuses_without_auth(
    cfg: ClaudeConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    with pytest.raises(ConfigError, match="no AWS auth"):
        cfg.sync_to_s3("s3://bucket/path", dry_run=True)


def test_sync_to_s3_refuses_non_s3_target(
    cfg: ClaudeConfig, mock_aws_creds: None
) -> None:
    with pytest.raises(ConfigError, match="must be s3"):
        cfg.sync_to_s3("https://example.com/", dry_run=True)


def test_sync_to_s3_refuses_target_without_bucket(
    cfg: ClaudeConfig, mock_aws_creds: None
) -> None:
    with pytest.raises(ConfigError, match="missing bucket"):
        cfg.sync_to_s3("s3:///key-only", dry_run=True)


# --- dry-run + actual upload via moto ------------------------------------


def test_sync_to_s3_dry_run_no_upload(
    cfg: ClaudeConfig, mock_aws_creds: None
) -> None:
    cfg.src_dir.mkdir(parents=True, exist_ok=True)
    (cfg.src_dir / "CLAUDE.md").write_text("test content\n", encoding="utf-8")
    r = cfg.sync_to_s3("s3://my-bucket/prefix", dry_run=True)
    assert r.dry_run
    assert r.uploaded
    assert r.bytes_transferred == 0  # dry-run uploaded nothing


def test_sync_to_s3_real_upload_via_moto(
    cfg: ClaudeConfig, mock_aws_creds: None
) -> None:
    from moto import mock_aws

    cfg.src_dir.mkdir(parents=True, exist_ok=True)
    (cfg.src_dir / "CLAUDE.md").write_text("a CLAUDE.md\n", encoding="utf-8")
    (cfg.src_dir / "commands").mkdir(exist_ok=True)
    (cfg.src_dir / "commands" / "demo.md").write_text("a command\n", encoding="utf-8")

    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="my-bucket")

        r = cfg.sync_to_s3("s3://my-bucket/prefix", dry_run=False)

        # Report: both files uploaded, bytes > 0
        assert isinstance(r, S3SyncReport)
        assert not r.dry_run
        assert sorted(r.uploaded) == ["CLAUDE.md", "commands/demo.md"]
        assert r.bytes_transferred > 0

        # And actually present in the (mocked) bucket.
        listed = {
            obj["Key"] for obj in s3.list_objects_v2(Bucket="my-bucket").get("Contents", [])
        }
        assert "prefix/CLAUDE.md" in listed
        assert "prefix/commands/demo.md" in listed


def test_sync_to_s3_root_no_prefix(
    cfg: ClaudeConfig, mock_aws_creds: None
) -> None:
    """Target without a trailing key-prefix lands files at bucket root."""
    from moto import mock_aws

    cfg.src_dir.mkdir(parents=True, exist_ok=True)
    (cfg.src_dir / "CLAUDE.md").write_text("x", encoding="utf-8")

    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        cfg.sync_to_s3("s3://test-bucket", dry_run=False)
        keys = {
            obj["Key"] for obj in s3.list_objects_v2(Bucket="test-bucket").get("Contents", [])
        }
        assert "CLAUDE.md" in keys
        assert all("prefix" not in k for k in keys)


def test_sync_to_s3_filters_secret_files(
    cfg: ClaudeConfig, mock_aws_creds: None
) -> None:
    """Files matching the secret patterns are NEVER uploaded."""
    from moto import mock_aws

    cfg.src_dir.mkdir(parents=True, exist_ok=True)
    (cfg.src_dir / "CLAUDE.md").write_text("safe", encoding="utf-8")
    (cfg.src_dir / ".env").write_text("API_KEY=hunter2", encoding="utf-8")
    (cfg.src_dir / ".credentials.json").write_text('{"token":"x"}', encoding="utf-8")

    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        r = cfg.sync_to_s3("s3://test-bucket/cfg", dry_run=False)

        assert "CLAUDE.md" in r.uploaded
        assert ".env" not in r.uploaded
        assert ".credentials.json" not in r.uploaded
        assert any(".env" in s for s in r.skipped_secrets)
        assert any("credentials" in s for s in r.skipped_secrets)

        listed = {
            obj["Key"] for obj in s3.list_objects_v2(Bucket="test-bucket").get("Contents", [])
        }
        # Confirm the bucket only has the safe file (under the prefix).
        assert listed == {"cfg/CLAUDE.md"}


def test_sync_to_s3_endpoint_url_passes_through(
    cfg: ClaudeConfig, mock_aws_creds: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """endpoint_url is forwarded to boto3.Session.client(...).

    Moto only intercepts AWS-style endpoints, so we can't end-to-end
    test a non-AWS upload without a separate mock. Instead, capture
    the kwargs handed to `client()` and assert endpoint_url is wired.
    """
    captured: dict[str, object] = {}

    real_session_client = boto3.Session.client

    def fake_client(self, service_name, **kwargs):  # type: ignore[no-untyped-def]
        captured["service_name"] = service_name
        captured["endpoint_url"] = kwargs.get("endpoint_url")
        return real_session_client(self, service_name, **kwargs)

    monkeypatch.setattr(boto3.Session, "client", fake_client)

    cfg.src_dir.mkdir(parents=True, exist_ok=True)
    (cfg.src_dir / "CLAUDE.md").write_text("x", encoding="utf-8")

    # Dry-run so we don't need to mock the actual upload.
    cfg.sync_to_s3(
        "s3://test-bucket/k",
        endpoint_url="https://minio.example.com",
        dry_run=True,
    )
    assert captured["service_name"] == "s3"
    assert captured["endpoint_url"] == "https://minio.example.com"


def test_sync_to_s3_audit_event_recorded(
    cfg: ClaudeConfig, mock_aws_creds: None
) -> None:
    """A real upload emits a sync_to_s3 audit event."""
    import json as _json

    from moto import mock_aws

    cfg.src_dir.mkdir(parents=True, exist_ok=True)
    (cfg.src_dir / "CLAUDE.md").write_text("x", encoding="utf-8")

    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        cfg.sync_to_s3("s3://test-bucket/k", dry_run=False)

    log = cfg.audit_log_path
    assert log.is_file()
    lines = [_json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line]
    events = [r for r in lines if r["event"] == "sync_to_s3"]
    assert events
    e = events[-1]
    assert e["target"] == "s3://test-bucket/k"
    assert e["files"] == 1
