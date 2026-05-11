"""End-to-end CLI tests — argparse wiring, exit codes, env var precedence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from claude_config.cli import main


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "claude-config" in out
    # Env var section visible in epilog
    assert "CLAUDE_CONFIG_FILE" in out


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "claude-config" in out


def test_no_command_exits_two(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_init_install_doctor_roundtrip(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    target.mkdir()

    rc = main(["--content", str(content), "--target", str(target), "init", "--no-git"])
    assert rc == 0
    assert (content / "claude" / "CLAUDE.md").exists()

    rc = main(["--content", str(content), "--target", str(target), "install"])
    assert rc == 0
    assert (target / "CLAUDE.md").is_symlink()

    rc = main(["--content", str(content), "--target", str(target), "doctor"])
    assert rc == 0


def test_doctor_nonzero_when_unhealthy(tmp_path: Path) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    (content / "claude").mkdir(parents=True)
    (content / "claude" / "CLAUDE.md").write_text("x")
    target.mkdir()
    # never installed — link missing
    rc = main(["--content", str(content), "--target", str(target), "doctor"])
    assert rc == 1


def test_status_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    (content / "claude").mkdir(parents=True)
    target.mkdir()
    rc = main(["--content", str(content), "--target", str(target), "status"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Content dir" in out
    assert "Tracked files" in out


def test_invalid_json_config_exits_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid")
    rc = main(["--config", str(bad), "status"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "error" in err.lower()


def test_env_var_picked_up_by_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    content = tmp_path / "via-env"
    (content / "claude").mkdir(parents=True)
    target = tmp_path / "target"
    target.mkdir()

    monkeypatch.setenv("CLAUDE_CONFIG_CONTENT_DIR", str(content))
    monkeypatch.setenv("CLAUDE_CONFIG_TARGET", str(target))

    rc = main(["doctor"])
    assert rc == 0  # empty content dir → no issues


def test_install_dry_run_does_not_write(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    (content / "claude").mkdir(parents=True)
    (content / "claude" / "CLAUDE.md").write_text("x")
    target.mkdir()

    rc = main(
        ["--content", str(content), "--target", str(target), "install", "--dry-run"]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "[dry-run]" in out
    assert not (target / "CLAUDE.md").exists()


def test_track_via_cli(tmp_path: Path) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    (content / "claude").mkdir(parents=True)
    target.mkdir()
    (target / "real.md").write_text("hello")

    rc = main(
        [
            "--content",
            str(content),
            "--target",
            str(target),
            "track",
            str(target / "real.md"),
        ]
    )
    assert rc == 0
    assert (target / "real.md").is_symlink()
    assert (content / "claude" / "real.md").read_text() == "hello"


def test_init_save_writes_config(tmp_path: Path) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    target.mkdir()
    cfg_file = tmp_path / "out-config.json"

    rc = main(
        [
            "--config", str(cfg_file),
            "--content", str(content),
            "--target", str(target),
            "init", "--no-git", "--save",
        ]
    )
    assert rc == 0
    assert cfg_file.exists()
    data = json.loads(cfg_file.read_text())
    assert Path(data["content_dir"]) == content.resolve()
    assert Path(data["target_base"]) == target.resolve()
