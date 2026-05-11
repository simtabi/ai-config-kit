from __future__ import annotations

import json
from pathlib import Path

import pytest

from claude_config import (
    ClaudeConfig,
    ConfigError,
    DoctorReport,
    InstallReport,
    StatusReport,
)

# --- construction + fluent API ---------------------------------------------


def test_fluent_setters_return_self(cfg: ClaudeConfig, tmp_path: Path) -> None:
    out = (
        cfg.with_content_dir(tmp_path / "a")
        .with_target(tmp_path / "b")
        .with_secret_patterns(["*.x"])
        .with_ignore_patterns(["*.y"])
        .with_dir_symlinks(["z"])
    )
    assert out is cfg
    assert cfg.content_dir == (tmp_path / "a").resolve()
    assert cfg.target_base == (tmp_path / "b").resolve()


def test_from_config_falls_back_to_defaults_when_missing(tmp_path: Path) -> None:
    missing = tmp_path / "no-such.json"
    cfg = ClaudeConfig.from_config(missing)
    assert cfg.content_dir == ClaudeConfig.DEFAULT_CONTENT
    assert cfg.target_base == ClaudeConfig.DEFAULT_TARGET


def test_from_config_loads_fields(tmp_path: Path) -> None:
    cfg_file = tmp_path / "c.json"
    cfg_file.write_text(
        json.dumps(
            {
                "content_dir": str(tmp_path / "c"),
                "target_base": str(tmp_path / "t"),
                "secret_patterns": ["*.x"],
                "ignore_patterns": ["*.y"],
                "dir_symlink_names": ["z"],
            }
        )
    )
    cfg = ClaudeConfig.from_config(cfg_file)
    assert cfg.content_dir == (tmp_path / "c").resolve()
    assert cfg.target_base == (tmp_path / "t").resolve()


def test_from_config_raises_on_invalid_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(ConfigError):
        ClaudeConfig.from_config(bad)


def test_env_var_fallback_when_no_arg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_CONTENT_DIR", str(tmp_path / "envcontent"))
    monkeypatch.setenv("CLAUDE_CONFIG_TARGET", str(tmp_path / "envtarget"))
    cfg = ClaudeConfig()
    assert cfg.content_dir == (tmp_path / "envcontent").resolve()
    assert cfg.target_base == (tmp_path / "envtarget").resolve()


def test_explicit_arg_wins_over_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_CONTENT_DIR", str(tmp_path / "env"))
    cfg = ClaudeConfig(content_dir=tmp_path / "explicit")
    assert cfg.content_dir == (tmp_path / "explicit").resolve()


def test_env_var_overrides_json_in_from_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_file = tmp_path / "c.json"
    cfg_file.write_text(
        json.dumps({"content_dir": str(tmp_path / "from-json")})
    )
    monkeypatch.setenv("CLAUDE_CONFIG_CONTENT_DIR", str(tmp_path / "from-env"))
    cfg = ClaudeConfig.from_config(cfg_file)
    assert cfg.content_dir == (tmp_path / "from-env").resolve()


def test_env_var_can_redirect_config_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_file = tmp_path / "via-env.json"
    cfg_file.write_text(json.dumps({"content_dir": str(tmp_path / "via-env-content")}))
    monkeypatch.setenv("CLAUDE_CONFIG_FILE", str(cfg_file))
    cfg = ClaudeConfig.from_config()  # no arg — env should point us at cfg_file
    assert cfg.content_dir == (tmp_path / "via-env-content").resolve()


def test_save_config_round_trips(cfg: ClaudeConfig, tmp_path: Path) -> None:
    out = tmp_path / "saved.json"
    cfg.save_config(out)
    data = json.loads(out.read_text())
    assert data["content_dir"] == str(cfg.content_dir)
    assert data["target_base"] == str(cfg.target_base)
    assert "secret_patterns" in data


# --- init -------------------------------------------------------------------


def test_init_creates_dirs_and_examples(tmp_path: Path) -> None:
    content = tmp_path / "fresh"
    cfg = ClaudeConfig(content_dir=content, target_base=tmp_path / "t")
    cfg.init(init_git=False)
    assert (content / "claude").is_dir()
    assert (content / "claude" / "CLAUDE.md").exists()
    assert (content / ".gitignore").exists()
    assert ".credentials.json" in (content / ".gitignore").read_text()


def test_init_no_examples(tmp_path: Path) -> None:
    content = tmp_path / "fresh"
    cfg = ClaudeConfig(content_dir=content, target_base=tmp_path / "t")
    cfg.init(with_examples=False, init_git=False)
    assert not (content / "claude" / "CLAUDE.md").exists()


# --- install ---------------------------------------------------------------


def test_install_symlinks_files(cfg: ClaudeConfig) -> None:
    (cfg.src_dir / "CLAUDE.md").write_text("hello")
    report = cfg.install()
    assert isinstance(report, InstallReport)
    assert report.links_created == 1
    link = cfg.target_base / "CLAUDE.md"
    assert link.is_symlink()
    assert link.resolve() == cfg.src_dir / "CLAUDE.md"


def test_install_is_idempotent(cfg: ClaudeConfig) -> None:
    (cfg.src_dir / "CLAUDE.md").write_text("x")
    cfg.install()
    r2 = cfg.install()
    assert r2.links_created == 0
    assert r2.already_correct == 1


def test_install_creates_dir_symlink_for_memory(cfg: ClaudeConfig) -> None:
    mem = cfg.src_dir / "projects" / "p1" / "memory"
    mem.mkdir(parents=True)
    (mem / "a.md").write_text("a")
    (mem / "b.md").write_text("b")
    report = cfg.install()
    # one dir symlink (the memory dir itself)
    assert report.dir_links_created == 1
    # files inside reachable via the dir symlink — skipped per-file
    assert report.skipped_via_dir_symlink == 2
    link = cfg.target_base / "projects" / "p1" / "memory"
    assert link.is_symlink()
    assert (link / "a.md").read_text() == "a"


def test_install_backs_up_colliding_real_file(cfg: ClaudeConfig) -> None:
    (cfg.src_dir / "CLAUDE.md").write_text("src")
    (cfg.target_base / "CLAUDE.md").write_text("real")
    report = cfg.install()
    assert report.real_files_backed_up == 1
    backup = cfg.target_base / "CLAUDE.md.before-claude-config"
    assert backup.exists()
    assert backup.read_text() == "real"


def test_install_skips_ignored_files(cfg: ClaudeConfig) -> None:
    (cfg.src_dir / ".DS_Store").write_bytes(b"\x00")
    (cfg.src_dir / "CLAUDE.md").write_text("x")
    report = cfg.install()
    assert report.links_created == 1
    assert not (cfg.target_base / ".DS_Store").exists()


def test_install_skips_secret_files(cfg: ClaudeConfig) -> None:
    (cfg.src_dir / ".credentials.json").write_text("oops")
    (cfg.src_dir / "x.key").write_text("oops")
    (cfg.src_dir / "CLAUDE.md").write_text("ok")
    report = cfg.install()
    assert report.links_created == 1


def test_install_dry_run_makes_no_changes(cfg: ClaudeConfig) -> None:
    (cfg.src_dir / "CLAUDE.md").write_text("x")
    report = cfg.install(dry_run=True)
    assert report.links_created == 1
    assert not (cfg.target_base / "CLAUDE.md").exists()


def test_install_raises_when_src_missing(tmp_path: Path) -> None:
    cfg = ClaudeConfig(content_dir=tmp_path / "missing", target_base=tmp_path / "t")
    with pytest.raises(ConfigError, match="does not exist"):
        cfg.install()


# --- uninstall -------------------------------------------------------------


def test_uninstall_removes_links_but_leaves_content(cfg: ClaudeConfig) -> None:
    (cfg.src_dir / "CLAUDE.md").write_text("x")
    cfg.install()
    cfg.uninstall()
    assert not (cfg.target_base / "CLAUDE.md").exists()
    assert (cfg.src_dir / "CLAUDE.md").exists()


# --- doctor ----------------------------------------------------------------


def test_doctor_healthy_after_install(cfg: ClaudeConfig) -> None:
    (cfg.src_dir / "CLAUDE.md").write_text("x")
    cfg.install()
    report = cfg.doctor()
    assert isinstance(report, DoctorReport)
    assert report.healthy


def test_doctor_reports_missing_link(cfg: ClaudeConfig) -> None:
    (cfg.src_dir / "CLAUDE.md").write_text("x")
    # never installed
    report = cfg.doctor()
    assert not report.healthy
    assert any("missing path" in i for i in report.issues)


def test_doctor_reports_wrong_resolution(cfg: ClaudeConfig) -> None:
    (cfg.src_dir / "CLAUDE.md").write_text("x")
    (cfg.src_dir / "other.md").write_text("y")
    cfg.install()
    # repoint the symlink at a wrong target
    link = cfg.target_base / "CLAUDE.md"
    link.unlink()
    link.symlink_to(cfg.src_dir / "other.md")
    report = cfg.doctor()
    assert not report.healthy
    assert any("wrong resolution" in i for i in report.issues)


# --- track -----------------------------------------------------------------


def test_track_moves_file_and_symlinks(cfg: ClaudeConfig) -> None:
    real = cfg.target_base / "skills" / "x.md"
    real.parent.mkdir(parents=True)
    real.write_text("real-content")
    cfg.track(real)
    assert real.is_symlink()
    assert real.resolve() == cfg.src_dir / "skills" / "x.md"
    assert (cfg.src_dir / "skills" / "x.md").read_text() == "real-content"


def test_track_refuses_paths_outside_target(cfg: ClaudeConfig, tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere.md"
    outside.write_text("nope")
    with pytest.raises(ConfigError, match="must live under"):
        cfg.track(outside)


def test_track_refuses_secrets(cfg: ClaudeConfig) -> None:
    secret = cfg.target_base / ".credentials.json"
    secret.write_text("token")
    with pytest.raises(ConfigError, match="secret pattern"):
        cfg.track(secret)


def test_track_refuses_existing_symlink(cfg: ClaudeConfig) -> None:
    (cfg.src_dir / "x.md").write_text("x")
    cfg.install()
    with pytest.raises(ConfigError, match="already a symlink"):
        cfg.track(cfg.target_base / "x.md")


# --- status ----------------------------------------------------------------


def test_status_lists_tracked_and_untracked(cfg: ClaudeConfig) -> None:
    (cfg.src_dir / "CLAUDE.md").write_text("x")
    # untracked real file under target
    (cfg.target_base / "skills").mkdir()
    (cfg.target_base / "skills" / "new.md").write_text("y")

    report = cfg.status()
    assert isinstance(report, StatusReport)
    assert "CLAUDE.md" in report.tracked_files
    assert any("skills/new.md" in c for c in report.untracked_candidates)


def test_status_skips_well_known_ephemeral_dirs(cfg: ClaudeConfig) -> None:
    (cfg.target_base / "sessions").mkdir()
    (cfg.target_base / "sessions" / "x.log").write_text("data")
    (cfg.target_base / "cache").mkdir()
    (cfg.target_base / "cache" / "x").write_text("data")
    report = cfg.status()
    assert not any("sessions" in c or "cache" in c for c in report.untracked_candidates)


# --- sessions + history tracking ------------------------------------------


def test_sessions_disabled_by_default(cfg: ClaudeConfig) -> None:
    assert "sessions" not in cfg._dir_syms  # type: ignore[attr-defined]


def test_with_sessions_adds_to_dir_symlinks(cfg: ClaudeConfig) -> None:
    cfg.with_sessions(True)
    assert "sessions" in cfg._dir_syms  # type: ignore[attr-defined]


def test_with_sessions_is_idempotent(cfg: ClaudeConfig) -> None:
    cfg.with_sessions(True).with_sessions(True)
    # not duplicated
    assert cfg._dir_syms.count("sessions") == 1  # type: ignore[attr-defined]


def test_with_sessions_false_removes(cfg: ClaudeConfig) -> None:
    cfg.with_sessions(True)
    cfg.with_sessions(False)
    assert "sessions" not in cfg._dir_syms  # type: ignore[attr-defined]


def test_include_sessions_in_json_round_trip(tmp_path: Path) -> None:
    cfg_file = tmp_path / "c.json"
    cfg_file.write_text(
        json.dumps(
            {
                "include_sessions": True,
                "include_history": True,
            }
        )
    )
    cfg = ClaudeConfig.from_config(cfg_file)
    assert "sessions" in cfg._dir_syms  # type: ignore[attr-defined]
    assert cfg._include_history  # type: ignore[attr-defined]


def test_track_directory_moves_and_dir_symlinks(cfg: ClaudeConfig) -> None:
    sessions = cfg.target_base / "sessions"
    sessions.mkdir()
    (sessions / "a.log").write_text("a")
    (sessions / "b.log").write_text("b")

    cfg.track(sessions)
    assert sessions.is_symlink()
    assert sessions.resolve() == cfg.src_dir / "sessions"
    assert (cfg.src_dir / "sessions" / "a.log").read_text() == "a"
    # Tracking a directory adds it to dir_symlink_names
    assert "sessions" in cfg._dir_syms  # type: ignore[attr-defined]


def test_track_history_jsonl_sets_include_history(cfg: ClaudeConfig) -> None:
    hist = cfg.target_base / "history.jsonl"
    hist.write_text("{}\n")
    cfg.track(hist)
    assert hist.is_symlink()
    assert cfg._include_history  # type: ignore[attr-defined]


def test_status_surfaces_sessions_when_tracking_enabled(cfg: ClaudeConfig) -> None:
    (cfg.target_base / "sessions").mkdir()
    (cfg.target_base / "sessions" / "x.log").write_text("data")
    cfg.with_sessions(True)
    report = cfg.status()
    # Now sessions should appear in candidates (it's a real dir not yet tracked)
    assert any("sessions/x.log" in c for c in report.untracked_candidates)


def test_status_surfaces_history_when_tracking_enabled(cfg: ClaudeConfig) -> None:
    (cfg.target_base / "history.jsonl").write_text("{}\n")
    cfg.with_history(True)
    report = cfg.status()
    assert any(c == "history.jsonl" for c in report.untracked_candidates)


def test_save_config_persists_include_flags(cfg: ClaudeConfig, tmp_path: Path) -> None:
    cfg.with_sessions(True).with_history(True)
    out = tmp_path / "saved.json"
    cfg.save_config(out)
    data = json.loads(out.read_text())
    assert data["include_sessions"] is True
    assert data["include_history"] is True


# --- sync ------------------------------------------------------------------


def test_sync_requires_git_repo(cfg: ClaudeConfig) -> None:
    (cfg.src_dir / "CLAUDE.md").write_text("x")
    with pytest.raises(ConfigError, match="not a git repo"):
        cfg.sync()


def test_sync_commits_changes(cfg: ClaudeConfig) -> None:
    cfg.init(init_git=True, with_examples=False)
    (cfg.src_dir / "CLAUDE.md").write_text("x")

    # configure local git identity for this test repo
    import subprocess

    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=cfg.content_dir,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=cfg.content_dir,
        check=True,
    )

    report = cfg.sync(message="test commit")
    assert report.committed
    assert report.commit_sha
    assert report.commit_message == "test commit"


def test_sync_on_clean_tree_returns_uncommitted(cfg: ClaudeConfig) -> None:
    cfg.init(init_git=True, with_examples=False)
    # nothing changed beyond .gitignore (already committed by init? actually
    # init doesn't commit — git status will show .gitignore as untracked)
    # Let's commit it first so the tree IS clean:
    import subprocess

    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=cfg.content_dir,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "T"], cwd=cfg.content_dir, check=True)
    subprocess.run(["git", "add", "-A"], cwd=cfg.content_dir, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=cfg.content_dir, check=True)

    report = cfg.sync()
    assert not report.committed
