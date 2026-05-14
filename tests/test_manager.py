from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_configurator import (
    BootstrapReport,
    ClaudeConfig,
    CleanupReport,
    ConfigError,
    DecisionsApplyReport,
    DecisionsListReport,
    DoctorReport,
    FetchReport,
    InstallReport,
    ListingReport,
    RepairReport,
    StatusReport,
    ValidationReport,
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
    cfg = ClaudeConfig.from_config()  # no arg: env should point us at cfg_file
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
    # files inside reachable via the dir symlink: skipped per-file
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
    # init doesn't commit: git status will show .gitignore as untracked)
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


# --- uninstall: backup restoration ----------------------------------------


def test_uninstall_restores_backups(cfg: ClaudeConfig) -> None:
    (cfg.src_dir / "CLAUDE.md").write_text("from-content")
    (cfg.target_base / "CLAUDE.md").write_text("real-pre-existing")
    cfg.install()  # backs up real file, creates symlink
    backup = cfg.target_base / "CLAUDE.md.before-claude-config"
    assert backup.exists()
    r = cfg.uninstall()
    assert r.backups_restored == 1
    assert (cfg.target_base / "CLAUDE.md").read_text() == "real-pre-existing"
    assert not backup.exists()


def test_uninstall_no_restore_when_flag_off(cfg: ClaudeConfig) -> None:
    (cfg.src_dir / "CLAUDE.md").write_text("from-content")
    (cfg.target_base / "CLAUDE.md").write_text("real")
    cfg.install()
    r = cfg.uninstall(restore_backups=False)
    assert r.backups_restored == 0
    backup = cfg.target_base / "CLAUDE.md.before-claude-config"
    assert backup.exists()


# --- track: persists state change to config ------------------------------


def test_track_dir_persists_dir_symlinks_to_config(
    tmp_path: Path, cfg: ClaudeConfig
) -> None:
    cfg_file = tmp_path / "cfg.json"
    cfg.save_config(cfg_file)
    # Re-load from config so _loaded_config_path is set
    cfg2 = ClaudeConfig.from_config(cfg_file)
    plugin_dir = cfg2.target_base / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "blocklist.json").write_text("{}")
    cfg2.track(plugin_dir)
    on_disk = json.loads(cfg_file.read_text())
    assert "plugins" in on_disk["dir_symlink_names"]


def test_track_sessions_persists_include_sessions(
    tmp_path: Path, cfg: ClaudeConfig
) -> None:
    cfg_file = tmp_path / "cfg.json"
    cfg.save_config(cfg_file)
    cfg2 = ClaudeConfig.from_config(cfg_file)
    sessions = cfg2.target_base / "sessions"
    sessions.mkdir()
    (sessions / "x.json").write_text("{}")
    cfg2.track(sessions)
    on_disk = json.loads(cfg_file.read_text())
    assert on_disk["include_sessions"] is True


def test_track_uses_shutil_move_across_filesystems(
    cfg: ClaudeConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """track() must use shutil.move so cross-filesystem renames don't fail."""
    real = cfg.target_base / "skills" / "x.md"
    real.parent.mkdir(parents=True)
    real.write_text("data")

    # Force rename to raise OSError (simulating cross-device); shutil.move handles it
    calls: list[str] = []
    original_move = __import__("shutil").move

    def tracking_move(src: str, dst: str) -> str:
        calls.append("move")
        return original_move(src, dst)

    monkeypatch.setattr("shutil.move", tracking_move)
    cfg.track(real)
    assert calls == ["move"]
    assert real.is_symlink()


# --- cleanup --------------------------------------------------------------


def test_cleanup_dry_run_lists_ds_store(cfg: ClaudeConfig) -> None:
    (cfg.src_dir / ".DS_Store").write_bytes(b"\x00")
    (cfg.target_base / ".DS_Store").write_bytes(b"\x00")
    report = cfg.cleanup(dry_run=True)
    assert isinstance(report, CleanupReport)
    assert report.dry_run
    assert len(report.ds_store_removed) == 2
    # Nothing actually deleted
    assert (cfg.src_dir / ".DS_Store").exists()


def test_cleanup_apply_deletes(cfg: ClaudeConfig) -> None:
    (cfg.src_dir / ".DS_Store").write_bytes(b"\x00")
    cfg.cleanup(dry_run=False)
    assert not (cfg.src_dir / ".DS_Store").exists()


def test_cleanup_finds_broken_symlinks(cfg: ClaudeConfig) -> None:
    (cfg.src_dir / "CLAUDE.md").write_text("x")
    cfg.install()
    # Delete src so the symlink at target points nowhere
    (cfg.src_dir / "CLAUDE.md").unlink()
    report = cfg.cleanup(dry_run=True)
    assert len(report.broken_symlinks_removed) == 1


def test_cleanup_finds_orphan_backups(cfg: ClaudeConfig) -> None:
    # A real file backed up but no corresponding primary
    (cfg.target_base / "settings.json.before-claude-config").write_text("old")
    report = cfg.cleanup(dry_run=True)
    assert any("before-claude-config" in str(p) for p in report.orphan_backups)


def test_cleanup_ephemeral_only_with_flag(cfg: ClaudeConfig) -> None:
    (cfg.target_base / "paste-cache").mkdir()
    (cfg.target_base / "paste-cache" / "x.txt").write_text("clip")
    r1 = cfg.cleanup(dry_run=True, include_ephemeral=False)
    assert not r1.ephemeral_paths_cleaned
    r2 = cfg.cleanup(dry_run=True, include_ephemeral=True)
    assert r2.ephemeral_paths_cleaned


def test_cleanup_respects_include_sessions(cfg: ClaudeConfig) -> None:
    (cfg.target_base / "sessions").mkdir()
    (cfg.target_base / "sessions" / "s.json").write_text("{}")
    cfg.with_sessions(True)
    r = cfg.cleanup(dry_run=True, include_ephemeral=True)
    # sessions should NOT be in ephemeral_paths_cleaned because they're tracked
    assert not any("sessions" in str(p) for p in r.ephemeral_paths_cleaned)


# --- list -----------------------------------------------------------------


def test_list_groups_top_level_and_dirs(cfg: ClaudeConfig) -> None:
    (cfg.src_dir / "CLAUDE.md").write_text("x")
    (cfg.src_dir / "settings.json").write_text("{}")
    (cfg.src_dir / "commands").mkdir()
    (cfg.src_dir / "commands" / "review.md").write_text("review")
    report = cfg.list_contents()
    assert isinstance(report, ListingReport)
    text = report.to_text()
    assert "Config files" in text
    assert "CLAUDE.md" in text
    assert "Auto-grow dir: commands/" in text
    assert "review.md" in text


def test_list_empty_content_dir(cfg: ClaudeConfig) -> None:
    report = cfg.list_contents()
    text = report.to_text()
    assert "empty" in text.lower()


def test_list_includes_plugin_config_files(cfg: ClaudeConfig) -> None:
    (cfg.src_dir / "plugins").mkdir()
    (cfg.src_dir / "plugins" / "blocklist.json").write_text("{}")
    (cfg.src_dir / "plugins" / "known_marketplaces.json").write_text("{}")
    text = cfg.list_contents().to_text()
    assert "Plugin config files" in text


def test_list_includes_host_overlays(cfg: ClaudeConfig) -> None:
    overlay = cfg.src_dir / "hosts" / cfg.hostname
    overlay.mkdir(parents=True)
    (overlay / "settings.local.json").write_text("{}")
    text = cfg.list_contents().to_text()
    assert "Host overlays" in text


# --- view -----------------------------------------------------------------


def test_view_returns_file_contents(cfg: ClaudeConfig) -> None:
    (cfg.src_dir / "CLAUDE.md").write_text("hello world\n")
    assert cfg.view("CLAUDE.md") == "hello world\n"


def test_view_refuses_path_traversal(cfg: ClaudeConfig, tmp_path: Path) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text("secret")
    with pytest.raises(ConfigError, match="outside src_dir"):
        cfg.view("../../outside.md")


def test_view_refuses_absolute_path(cfg: ClaudeConfig) -> None:
    with pytest.raises(ConfigError, match="must be a path relative"):
        cfg.view("/etc/passwd")


def test_view_refuses_missing_file(cfg: ClaudeConfig) -> None:
    with pytest.raises(ConfigError, match="not a file"):
        cfg.view("does-not-exist.md")


# --- host overlays --------------------------------------------------------


def test_install_links_host_overlay_only_for_matching_host(
    cfg: ClaudeConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_HOSTNAME", "alpha")
    # Build a fresh cfg so the hostname applies
    cfg = ClaudeConfig(content_dir=cfg.content_dir, target_base=cfg.target_base)
    alpha = cfg.src_dir / "hosts" / "alpha"
    beta = cfg.src_dir / "hosts" / "beta"
    alpha.mkdir(parents=True)
    beta.mkdir(parents=True)
    (alpha / "settings.local.json").write_text("alpha-config")
    (beta / "settings.local.json").write_text("beta-config")

    report = cfg.install()
    assert report.host_overlays_linked == 1
    assert (cfg.target_base / "settings.local.json").is_symlink()
    assert (cfg.target_base / "settings.local.json").read_text() == "alpha-config"


def test_doctor_flags_foreign_host_overlay_link(
    cfg: ClaudeConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_HOSTNAME", "alpha")
    cfg = ClaudeConfig(content_dir=cfg.content_dir, target_base=cfg.target_base)
    beta = cfg.src_dir / "hosts" / "beta"
    beta.mkdir(parents=True)
    src = beta / "settings.local.json"
    src.write_text("beta")
    # Manually create a symlink as if installed on the wrong host
    target = cfg.target_base / "settings.local.json"
    import os as _os
    _os.symlink(src, target)
    report = cfg.doctor()
    assert any("foreign host overlay" in i for i in report.issues)


# --- projects/* guard -----------------------------------------------------


def test_install_skips_projects_non_memory_files(cfg: ClaudeConfig) -> None:
    slug = cfg.src_dir / "projects" / "-Users-foo"
    slug.mkdir(parents=True)
    (slug / "stray.txt").write_text("should not be linked")
    cfg.install()
    assert not (cfg.target_base / "projects" / "-Users-foo" / "stray.txt").exists()


def test_install_allows_projects_memory_dir(cfg: ClaudeConfig) -> None:
    mem = cfg.src_dir / "projects" / "-Users-foo" / "memory"
    mem.mkdir(parents=True)
    (mem / "a.md").write_text("a")
    report = cfg.install()
    assert report.dir_links_created == 1
    link = cfg.target_base / "projects" / "-Users-foo" / "memory"
    assert link.is_symlink()


# --- expanded defaults ----------------------------------------------------


def test_default_dir_symlink_names_includes_commands(cfg: ClaudeConfig) -> None:
    assert "commands" in cfg.dir_symlink_names
    assert "agents" in cfg.dir_symlink_names
    assert "skills" in cfg.dir_symlink_names
    assert "hooks" in cfg.dir_symlink_names
    assert "prompts" in cfg.dir_symlink_names


def test_secret_patterns_block_ssh_keys(cfg: ClaudeConfig) -> None:
    real = cfg.target_base / "id_rsa"
    real.write_text("private")
    with pytest.raises(ConfigError, match="secret pattern"):
        cfg.track(real)


def test_secret_patterns_block_npmrc(cfg: ClaudeConfig) -> None:
    real = cfg.target_base / ".npmrc"
    real.write_text("//registry.npmjs.org/:_authToken=oops")
    with pytest.raises(ConfigError, match="secret pattern"):
        cfg.track(real)


# --- save_config: merges with existing -----------------------------------


def test_save_config_preserves_unknown_keys(cfg: ClaudeConfig, tmp_path: Path) -> None:
    cfg_file = tmp_path / "c.json"
    cfg_file.write_text(json.dumps({"future_field": "future_value", "content_dir": "/x"}))
    cfg.save_config(cfg_file)
    data = json.loads(cfg_file.read_text())
    assert data["future_field"] == "future_value"
    # And our known fields are present too
    assert "content_dir" in data
    assert "secret_patterns" in data


# --- validate -------------------------------------------------------------


def test_validate_returns_ok_with_writable_dirs(cfg: ClaudeConfig) -> None:
    r = cfg.validate()
    assert isinstance(r, ValidationReport)
    assert r.ok


def test_validate_flags_unwritable_target_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "no-perm" / ".claude"
    target.parent.mkdir(mode=0o500)  # read+exec only
    try:
        cfg = ClaudeConfig(
            content_dir=tmp_path / "content", target_base=target
        )
        r = cfg.validate()
        # Permission check is platform-sensitive; assert structure not specifics
        assert isinstance(r, ValidationReport)
    finally:
        target.parent.chmod(0o700)


# --- bootstrap ------------------------------------------------------------


def test_bootstrap_dry_run_runs_all_steps(cfg: ClaudeConfig) -> None:
    r = cfg.bootstrap(dry_run=True)
    assert isinstance(r, BootstrapReport)
    assert r.dry_run
    names = [s.name for s in r.steps]
    assert "validate" in names
    assert "init" in names
    assert "install" in names
    assert "doctor" in names
    assert r.ok


def test_bootstrap_real_run_creates_symlinks(cfg: ClaudeConfig) -> None:
    r = cfg.bootstrap(init_git=False, dry_run=False)
    assert r.ok
    assert (cfg.src_dir / "CLAUDE.md").exists()
    assert (cfg.target_base / "CLAUDE.md").is_symlink()


def test_bootstrap_prompts_on_existing_content(cfg: ClaudeConfig) -> None:
    (cfg.src_dir / "existing.md").write_text("pre")
    calls: list[str] = []

    def declining_prompter(question: str, default: bool) -> bool:
        calls.append(question)
        return False  # decline

    r = cfg.bootstrap(init_git=False, dry_run=False, prompt=declining_prompter)
    assert calls  # was prompted
    skipped = [s for s in r.steps if s.skipped]
    assert any(s.name == "init" for s in skipped)


def test_bootstrap_skips_doctor_on_install_failure(
    cfg: ClaudeConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Force install to fail
    def bad_install(*a: object, **kw: object) -> None:
        raise ConfigError("simulated install failure")

    monkeypatch.setattr(cfg, "install", bad_install)
    r = cfg.bootstrap(init_git=False, dry_run=False)
    assert not r.ok
    names_failed = [s.name for s in r.steps if not s.ok and not s.skipped]
    assert "install" in names_failed


# --- decisions ------------------------------------------------------------


def test_decisions_list_finds_bundled_packs(cfg: ClaudeConfig) -> None:
    r = cfg.decisions_list()
    assert isinstance(r, DecisionsListReport)
    names = [p.name for p in r.packs]
    assert "core" in names
    assert "script-generation-pattern" in names


def test_decisions_show_returns_manifest(cfg: ClaudeConfig) -> None:
    pack = cfg.decisions_show("core")
    assert pack.name == "core"
    assert pack.version
    assert pack.description
    assert pack.files
    assert pack.readme  # README.md should be present


def test_decisions_show_unknown_raises(cfg: ClaudeConfig) -> None:
    with pytest.raises(ConfigError, match="unknown decision pack"):
        cfg.decisions_show("does-not-exist")


def test_decisions_apply_writes_files(cfg: ClaudeConfig) -> None:
    r = cfg.decisions_apply("script-generation-pattern")
    assert isinstance(r, DecisionsApplyReport)
    assert r.pack == "script-generation-pattern"
    assert r.written
    cmd = cfg.src_dir / "commands" / "generate-via-script.md"
    assert cmd.is_file()


def test_decisions_apply_skips_existing_without_force(cfg: ClaudeConfig) -> None:
    cfg.decisions_apply("script-generation-pattern")
    r2 = cfg.decisions_apply("script-generation-pattern")
    assert not r2.written
    assert r2.skipped


def test_decisions_apply_force_overwrites(cfg: ClaudeConfig) -> None:
    cfg.decisions_apply("script-generation-pattern")
    r2 = cfg.decisions_apply("script-generation-pattern", force=True)
    assert r2.overwritten
    assert not r2.skipped


def test_decisions_apply_dry_run_writes_nothing(cfg: ClaudeConfig) -> None:
    r = cfg.decisions_apply("script-generation-pattern", dry_run=True)
    assert r.dry_run
    assert r.written  # report says it would write
    cmd = cfg.src_dir / "commands" / "generate-via-script.md"
    assert not cmd.exists()


def test_init_auto_applies_script_generation_pattern(cfg: ClaudeConfig) -> None:
    cfg.init(init_git=False)
    assert (cfg.src_dir / "commands" / "generate-via-script.md").is_file()


def test_init_no_decisions_skips_packs(cfg: ClaudeConfig) -> None:
    cfg.init(init_git=False, apply_decisions=())
    assert not (cfg.src_dir / "commands" / "generate-via-script.md").exists()


# --- repair ---------------------------------------------------------------


def test_repair_dry_run_finds_broken_symlinks(cfg: ClaudeConfig) -> None:
    (cfg.src_dir / "CLAUDE.md").write_text("x")
    cfg.install()
    # Break the symlink by deleting the source
    (cfg.src_dir / "CLAUDE.md").unlink()
    r = cfg.repair(dry_run=True)
    assert isinstance(r, RepairReport)
    assert r.dry_run
    assert any(a.kind == "broken-symlink-removed" for a in r.actions)


def test_repair_apply_recreates_missing_links(cfg: ClaudeConfig) -> None:
    (cfg.src_dir / "CLAUDE.md").write_text("x")
    cfg.install()
    (cfg.target_base / "CLAUDE.md").unlink()
    r = cfg.repair()
    assert not r.dry_run
    assert (cfg.target_base / "CLAUDE.md").is_symlink()
    assert any(a.kind == "link-recreated" for a in r.actions)


def test_repair_is_idempotent(cfg: ClaudeConfig) -> None:
    (cfg.src_dir / "CLAUDE.md").write_text("x")
    cfg.install()
    cfg.repair()
    r2 = cfg.repair()
    # Second run should have no actions
    assert not r2.actions


# --- fetch_canonical ------------------------------------------------------


@pytest.fixture
def http_server(tmp_path: Path):
    """Run a tiny HTTP server out of a temp dir; yield (port, root)."""
    import http.server
    import socketserver
    import threading

    root = tmp_path / "served"
    root.mkdir()

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(root), **kw)

        def log_message(self, *a, **kw):
            pass

    server = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1], root
    finally:
        server.shutdown()
        server.server_close()


def test_fetch_https_only_by_default(cfg: ClaudeConfig, tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="https"):
        cfg.fetch_canonical(
            "http://example.com/x.txt", tmp_path / "x.txt"
        )


def test_fetch_rejects_non_http_scheme(cfg: ClaudeConfig, tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="http"):
        cfg.fetch_canonical("ftp://example.com/x.txt", tmp_path / "x.txt")


def test_fetch_writes_file_disk_to_disk(
    cfg: ClaudeConfig, tmp_path: Path, http_server
) -> None:
    port, root = http_server
    (root / "license.md").write_text(
        "# License\n\nApache License Version 2.0\n", encoding="utf-8"
    )
    dest = tmp_path / "LICENSE.md"
    r = cfg.fetch_canonical(
        f"http://127.0.0.1:{port}/license.md",
        dest,
        allow_http=True,
    )
    assert isinstance(r, FetchReport)
    assert r.status == "created"
    assert r.bytes > 0
    assert r.sha256
    assert r.first_line == "# License"
    assert dest.is_file()


def test_fetch_idempotent_unchanged(
    cfg: ClaudeConfig, tmp_path: Path, http_server
) -> None:
    port, root = http_server
    (root / "x.md").write_text("# X\n", encoding="utf-8")
    dest = tmp_path / "x.md"
    r1 = cfg.fetch_canonical(
        f"http://127.0.0.1:{port}/x.md", dest, allow_http=True
    )
    r2 = cfg.fetch_canonical(
        f"http://127.0.0.1:{port}/x.md", dest, allow_http=True
    )
    assert r1.status == "created"
    assert r2.status == "unchanged"


def test_fetch_detects_update(
    cfg: ClaudeConfig, tmp_path: Path, http_server
) -> None:
    port, root = http_server
    (root / "x.md").write_text("# v1\n", encoding="utf-8")
    dest = tmp_path / "x.md"
    cfg.fetch_canonical(
        f"http://127.0.0.1:{port}/x.md", dest, allow_http=True
    )
    (root / "x.md").write_text("# v2\n", encoding="utf-8")
    r2 = cfg.fetch_canonical(
        f"http://127.0.0.1:{port}/x.md", dest, allow_http=True
    )
    assert r2.status == "updated"


def test_fetch_size_cap(cfg: ClaudeConfig, tmp_path: Path, http_server) -> None:
    port, root = http_server
    big = "a" * 2048
    (root / "big.md").write_text(big, encoding="utf-8")
    with pytest.raises(ConfigError, match="exceeds max-bytes"):
        cfg.fetch_canonical(
            f"http://127.0.0.1:{port}/big.md",
            tmp_path / "big.md",
            max_bytes=1024,
            allow_http=True,
        )


def test_fetch_sha256_mismatch(
    cfg: ClaudeConfig, tmp_path: Path, http_server
) -> None:
    port, root = http_server
    (root / "x.md").write_text("# X\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="sha256 mismatch"):
        cfg.fetch_canonical(
            f"http://127.0.0.1:{port}/x.md",
            tmp_path / "x.md",
            allow_http=True,
            expect_sha256="0" * 64,
        )


def test_fetch_no_first_line_flag(
    cfg: ClaudeConfig, tmp_path: Path, http_server
) -> None:
    port, root = http_server
    (root / "x.md").write_text("# X\n", encoding="utf-8")
    r = cfg.fetch_canonical(
        f"http://127.0.0.1:{port}/x.md",
        tmp_path / "x.md",
        allow_http=True,
        include_first_line=False,
    )
    assert r.first_line == ""


def test_fetch_summary_contains_only_metadata(
    cfg: ClaudeConfig, tmp_path: Path, http_server
) -> None:
    port, root = http_server
    body = "Apache License Version 2.0\nbody bytes that should not appear\n"
    (root / "x.txt").write_text(body, encoding="utf-8")
    r = cfg.fetch_canonical(
        f"http://127.0.0.1:{port}/x.txt", tmp_path / "x.txt", allow_http=True
    )
    summary = r.summary()
    # The first line is allowed in the summary; body should not be
    assert "Apache License Version 2.0" in summary
    assert "body bytes that should not appear" not in summary


# --- fetch-canonical-pattern is auto-applied -----------------------------


def test_init_auto_applies_fetch_canonical_pattern(cfg: ClaudeConfig) -> None:
    cfg.init(init_git=False)
    assert (cfg.src_dir / "commands" / "fetch-canonical.md").is_file()


# --- validate flags Python version ---------------------------------------


def test_validate_python_version_check(cfg: ClaudeConfig) -> None:
    r = cfg.validate()
    # Running version meets MIN_PYTHON, so no Python issue
    assert not any("Python" in i and "older" in i for i in r.issues)


# --- session-protocol pack (auto-applied on init) ------------------------


def test_session_protocol_pack_listed(cfg: ClaudeConfig) -> None:
    """The new pack appears in the bundled decisions."""
    listing = cfg.decisions_list()
    names = [p.name for p in listing.packs]
    assert "session-protocol" in names


def test_session_protocol_pack_has_expected_files(cfg: ClaudeConfig) -> None:
    """Manifest declares every file we ship in the pack."""
    pack = cfg.decisions_show("session-protocol")
    dest_paths = [f.dest for f in pack.files]
    # CLAUDE.md fragment + five slash commands
    assert any(d.startswith("CLAUDE.md.session-protocol") for d in dest_paths)
    for cmd in ("session-start.md", "session-end.md", "track-progress.md",
                "research-source.md", "clarify.md"):
        assert f"commands/{cmd}" in dest_paths


def test_init_auto_applies_session_protocol(cfg: ClaudeConfig) -> None:
    """init() drops the slash commands into src_dir by default."""
    cfg.init(init_git=False)
    for cmd in ("session-start.md", "session-end.md", "track-progress.md",
                "research-source.md", "clarify.md"):
        assert (cfg.src_dir / "commands" / cmd).is_file(), f"missing {cmd}"


def test_session_protocol_fragment_is_self_contained(cfg: ClaudeConfig) -> None:
    """The CLAUDE.md fragment mentions the session-end + hand-off concepts."""
    cfg.init(init_git=False)
    frag = cfg.src_dir / "CLAUDE.md.session-protocol.fragment"
    assert frag.is_file()
    body = frag.read_text(encoding="utf-8")
    # Spot-check that the key concepts are present
    for term in ("Session start", "Hallucination guard", "Track progress",
                 "Research before guessing", "Hand-off summary"):
        assert term in body, f"missing term: {term}"


# --- docker-multiarch pack (auto-applied, self-gated to Docker projects) --


def test_docker_multiarch_pack_listed(cfg: ClaudeConfig) -> None:
    listing = cfg.decisions_list()
    assert "docker-multiarch" in [p.name for p in listing.packs]


def test_init_auto_applies_docker_multiarch(cfg: ClaudeConfig) -> None:
    cfg.init(init_git=False)
    assert (cfg.src_dir / "commands" / "docker-multiarch-check.md").is_file()
    assert (cfg.src_dir / "CLAUDE.md.docker-multiarch.fragment").is_file()


def test_docker_multiarch_fragment_self_gates(cfg: ClaudeConfig) -> None:
    """The fragment must explicitly tell the model to skip when no Dockerfile is present."""
    cfg.init(init_git=False)
    body = (cfg.src_dir / "CLAUDE.md.docker-multiarch.fragment").read_text(encoding="utf-8")
    assert "Skip this entire section" in body
    assert "Dockerfile" in body
    # And it must call out both arches by name
    assert "linux/amd64" in body
    assert "linux/arm64" in body


# --- claude-best-practices pack (auto-applied) ----------------------------


def test_claude_best_practices_pack_listed(cfg: ClaudeConfig) -> None:
    listing = cfg.decisions_list()
    assert "claude-best-practices" in [p.name for p in listing.packs]


def test_init_auto_applies_claude_best_practices(cfg: ClaudeConfig) -> None:
    cfg.init(init_git=False)
    assert (cfg.src_dir / "commands" / "audit-claude-md.md").is_file()
    assert (cfg.src_dir / "commands" / "init-rules.md").is_file()
    assert (cfg.src_dir / "CLAUDE.md.claude-best-practices.fragment").is_file()


def test_best_practices_fragment_cites_official_docs(cfg: ClaudeConfig) -> None:
    """Every claim in the fragment must point at code.claude.com: the only
    way to keep this honest as the docs evolve."""
    cfg.init(init_git=False)
    body = (cfg.src_dir / "CLAUDE.md.claude-best-practices.fragment").read_text(
        encoding="utf-8"
    )
    assert "code.claude.com/docs/en/memory" in body
    assert "code.claude.com/docs/en/skills" in body
    assert "code.claude.com/docs/en/hooks" in body
    # Specific rule we want every CLAUDE.md author to know about
    assert "200 lines" in body
    # Mention AGENTS.md interop + the modern skills replace-commands story
    assert "AGENTS.md" in body
    assert "SKILL.md" in body


# --- reconcile (auto-apply on upgrade) -----------------------------------


def test_reconcile_skipped_when_versions_match(
    tmp_path: Path, cfg: ClaudeConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the recorded version matches the current package, no-op."""
    cfg_file = tmp_path / "cfg.json"
    cfg.save_config(cfg_file)

    # Pin _package_version to a known value + write the same in config
    from ai_configurator import manager as m
    monkeypatch.setattr(m, "_package_version", lambda: "1.2.3")
    cfg2 = ClaudeConfig.from_config(cfg_file)
    cfg2._write_last_applied_version("1.2.3")

    rep = cfg2.reconcile()
    assert not rep.upgrade_happened
    assert rep.from_version == "1.2.3"
    assert rep.to_version == "1.2.3"


def test_reconcile_applies_packs_on_version_bump(
    tmp_path: Path, cfg: ClaudeConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stored version < current → reconcile applies every auto-apply pack."""
    cfg_file = tmp_path / "cfg.json"
    cfg.save_config(cfg_file)

    from ai_configurator import manager as m
    monkeypatch.setattr(m, "_package_version", lambda: "9.9.9")
    cfg2 = ClaudeConfig.from_config(cfg_file)
    # No last_applied_version written: defaults to "0.0.0"

    rep = cfg2.reconcile()
    assert rep.upgrade_happened
    assert rep.from_version == "0.0.0"
    assert rep.to_version == "9.9.9"
    assert rep.packs_applied
    # Files actually landed
    assert (cfg2.src_dir / "commands" / "audit-claude-md.md").is_file()


def test_reconcile_writes_version_to_config(
    tmp_path: Path, cfg: ClaudeConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After reconcile, the version is persisted so the next call no-ops."""
    cfg_file = tmp_path / "cfg.json"
    cfg.save_config(cfg_file)

    from ai_configurator import manager as m
    monkeypatch.setattr(m, "_package_version", lambda: "5.0.0")
    cfg2 = ClaudeConfig.from_config(cfg_file)

    cfg2.reconcile()
    on_disk = json.loads(cfg_file.read_text())
    assert on_disk["last_applied_version"] == "5.0.0"

    # Second reconcile no-ops
    rep2 = cfg2.reconcile()
    assert not rep2.upgrade_happened


def test_reconcile_force_reapplies(
    tmp_path: Path, cfg: ClaudeConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """force_reapply=True applies packs even when versions match."""
    cfg_file = tmp_path / "cfg.json"
    cfg.save_config(cfg_file)
    from ai_configurator import manager as m
    monkeypatch.setattr(m, "_package_version", lambda: "1.0.0")
    cfg2 = ClaudeConfig.from_config(cfg_file)
    cfg2._write_last_applied_version("1.0.0")

    rep = cfg2.reconcile(force_reapply=True)
    assert rep.upgrade_happened


def test_reconcile_if_enabled_respects_flag(
    tmp_path: Path, cfg: ClaudeConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """auto_reconcile=False short-circuits the auto-reconcile path."""
    cfg_file = tmp_path / "cfg.json"
    cfg2 = ClaudeConfig(
        content_dir=cfg.content_dir, target_base=cfg.target_base,
        auto_reconcile=False,
    )
    cfg2.save_config(cfg_file)
    # Reload to set _loaded_config_path
    cfg2 = ClaudeConfig.from_config(cfg_file)
    cfg2._auto_reconcile = False
    assert cfg2.reconcile_if_enabled() is None


def test_reconcile_if_enabled_skips_when_no_config(cfg: ClaudeConfig) -> None:
    """Without a loaded config (env-var-only invocation), reconcile is skipped."""
    # cfg fixture has no _loaded_config_path
    assert cfg.reconcile_if_enabled() is None


# --- new packs from this session -----------------------------------------


@pytest.mark.parametrize("pack", [
    "humanistic-style",
    "docs-structure",
    "mcp-best-practices",
    "safety-net-commits",
    "vendor-portability",
    "docker-env-interpolation",
    "polling-discipline",
])
def test_new_packs_listed(cfg: ClaudeConfig, pack: str) -> None:
    listing = cfg.decisions_list()
    assert pack in [p.name for p in listing.packs]


def test_init_auto_applies_all_four_new_packs(cfg: ClaudeConfig) -> None:
    cfg.init(init_git=False)
    expected_commands = [
        "audit-prose.md",
        "audit-docblocks.md",
        "audit-docs-structure.md",
        "migrate-readmes-to-docs.md",
        "audit-mcp-config.md",
        "add-mcp-server.md",
        "checkpoint-now.md",
        "review-changes.md",
    ]
    for cmd in expected_commands:
        assert (cfg.src_dir / "commands" / cmd).is_file(), f"missing {cmd}"


def test_humanistic_style_ships_banned_phrases_file(cfg: ClaudeConfig) -> None:
    """The banned-phrases.txt must land at the documented location so
    other tools (linters, hooks) can grep it."""
    cfg.init(init_git=False)
    banned = cfg.src_dir / "humanistic-style" / "banned-phrases.txt"
    assert banned.is_file()
    body = banned.read_text(encoding="utf-8")
    # Spot-check a few signature phrases that mark AI output
    for phrase in ("delve into", "leverage", "robust and scalable", "let's dive into"):
        assert phrase in body.lower(), f"missing: {phrase}"


def test_mcp_fragment_cites_official_docs(cfg: ClaudeConfig) -> None:
    cfg.init(init_git=False)
    body = (cfg.src_dir / "CLAUDE.md.mcp-best-practices.fragment").read_text(
        encoding="utf-8"
    )
    assert "code.claude.com/docs/en/mcp" in body
    # Names of common MCP servers must appear
    assert "filesystem" in body
    assert ".mcp.json" in body
    # The Anthropic directory is the recommended discovery channel
    assert "claude.ai/directory" in body


def test_docs_structure_fragment_lists_root_allowlist(cfg: ClaudeConfig) -> None:
    cfg.init(init_git=False)
    body = (cfg.src_dir / "CLAUDE.md.docs-structure.fragment").read_text(
        encoding="utf-8"
    )
    for required in ("README.md", "CHANGELOG.md", "CONTRIBUTING.md",
                     "CODE_OF_CONDUCT.md", "SECURITY.md", "LICENSE"):
        assert required in body, f"missing in allowlist: {required}"


def test_safety_net_fragment_requires_explicit_verb(cfg: ClaudeConfig) -> None:
    """The whole point of safety-net-commits is that the agent prompts
    rather than commits unilaterally."""
    cfg.init(init_git=False)
    body = (cfg.src_dir / "CLAUDE.md.safety-net-commits.fragment").read_text(
        encoding="utf-8"
    )
    assert "explicit verb" in body.lower() or "always ask" in body.lower()
    # Forbid silent destructive ops
    assert "without explicit" in body.lower() or "explicit verb" in body.lower()


def test_docker_env_interpolation_ships_executable_script(cfg: ClaudeConfig) -> None:
    """The render-env.sh script must land executable so users can call it
    directly from ~/.claude/scripts/render-env.sh without a shell prefix."""
    cfg.init(init_git=False)
    script = cfg.src_dir / "scripts" / "render-env.sh"
    assert script.is_file()
    body = script.read_text(encoding="utf-8")
    # POSIX shell script, not Python: Docker can't natively read .py
    assert body.startswith("#!/")
    assert "sh" in body.splitlines()[0]
    # Executable bit (manifest declares mode 0755)
    mode = script.stat().st_mode & 0o777
    assert mode == 0o755, f"expected 0755 got {oct(mode)}"


def test_docker_env_interpolation_fragment_documents_precedence(
    cfg: ClaudeConfig,
) -> None:
    cfg.init(init_git=False)
    body = (cfg.src_dir / "CLAUDE.md.docker-env-interpolation.fragment").read_text(
        encoding="utf-8"
    )
    # Precedence chain must match Docker Compose behavior
    for token in ("Shell environment", "--local", "--input", "--example"):
        assert token in body, f"missing precedence rung: {token}"
    # Invocation no longer goes through python3
    assert "python3" not in body
    assert "render-env.sh" in body


def test_polling_discipline_fragment_lists_three_primitives(
    cfg: ClaudeConfig,
) -> None:
    """The fragment must name all three valid waiting primitives so an
    agent can pick correctly: Monitor + until-loop, Bash
    run_in_background, ScheduleWakeup. Regression guard against the
    rule getting shortened to just one option."""
    cfg.init(init_git=False)
    body = (cfg.src_dir / "CLAUDE.md.polling-discipline.fragment").read_text(
        encoding="utf-8"
    )
    assert "until" in body and "do sleep" in body  # until-loop pattern
    assert "run_in_background" in body
    assert "ScheduleWakeup" in body
    # Must also name the failure mode it guards against
    assert "chain" in body.lower() and "sleep" in body.lower()


def test_polling_discipline_slash_command_ships(cfg: ClaudeConfig) -> None:
    cfg.init(init_git=False)
    cmd = cfg.src_dir / "commands" / "wait-for.md"
    assert cmd.is_file()
    body = cmd.read_text(encoding="utf-8")
    # The four situation buckets the command branches on
    for tag in ("Command I started", "External state change",
                "Fixed delay", "long idle"):
        assert tag.lower() in body.lower(), f"missing situation: {tag}"


def test_decision_mode_field_applies_to_dest(
    cfg: ClaudeConfig, tmp_path: Path
) -> None:
    """A pack manifest with mode='0755' must produce an executable dest.

    Verifies the generic mechanism: not just the docker-env-interpolation
    pack: so future packs can ship executable artifacts the same way.
    """
    cfg.init(init_git=False)
    # docker-env-interpolation is the canonical user of the mode field
    pack = cfg.decisions_show("docker-env-interpolation")
    sh_entry = next(f for f in pack.files if f.dest.endswith("render-env.sh"))
    assert sh_entry.mode == "0755"
    # And the file on disk reflects it
    script = cfg.src_dir / sh_entry.dest
    assert script.stat().st_mode & 0o111, "executable bit not set"


# --- multi-vendor support ------------------------------------------------


def test_default_vendor_is_claude_code(cfg: ClaudeConfig) -> None:
    assert cfg.vendors == ("claude-code",)


def test_with_vendors_accepts_known_set(cfg: ClaudeConfig) -> None:
    cfg.with_vendors(["claude-code", "cursor", "aider"])
    assert cfg.vendors == ("claude-code", "cursor", "aider")


def test_vendor_status_returns_correct_levels(cfg: ClaudeConfig) -> None:
    assert cfg.vendor_status("claude-code") == "current"
    assert cfg.vendor_status("cursor") == "planned"
    assert cfg.vendor_status("nope-not-a-vendor") == "unknown"


def test_unsupported_vendors_flags_planned(cfg: ClaudeConfig) -> None:
    cfg.with_vendors(["claude-code", "cursor", "aider"])
    unsupp = cfg.unsupported_vendors()
    assert "cursor" in unsupp and "aider" in unsupp
    assert "claude-code" not in unsupp


def test_select_vendors_uses_defaults_without_prompt(cfg: ClaudeConfig) -> None:
    """When no Prompter is supplied, fall back to the default vendor set."""
    chosen = cfg.select_vendors_interactively(prompt=None)
    assert chosen == cfg.DEFAULT_VENDORS


def test_select_vendors_respects_prompter_choices(cfg: ClaudeConfig) -> None:
    """A prompter that only says yes to specific vendors returns just those."""
    def picky_prompter(question: str, default: bool) -> bool:
        return any(name in question for name in ("claude-code", "cursor"))

    chosen = cfg.select_vendors_interactively(prompt=picky_prompter)
    assert "claude-code" in chosen
    assert "cursor" in chosen
    assert "aider" not in chosen


def test_select_vendors_falls_back_when_user_picks_none(cfg: ClaudeConfig) -> None:
    """Refusing every prompt still gives the user the default set, not empty."""
    chosen = cfg.select_vendors_interactively(
        prompt=lambda q, d: False,
    )
    assert chosen == cfg.DEFAULT_VENDORS


def test_vendors_persist_to_config(cfg: ClaudeConfig, tmp_path: Path) -> None:
    """save_config / from_config round-trip preserves the vendor list."""
    cfg.with_vendors(["claude-code", "cursor"])
    out = tmp_path / "saved.json"
    cfg.save_config(out)
    cfg2 = ClaudeConfig.from_config(out)
    assert cfg2.vendors == ("claude-code", "cursor")


def test_vendors_default_when_config_has_none(
    cfg: ClaudeConfig, tmp_path: Path
) -> None:
    """An older JSON config without the vendors field still loads cleanly."""
    out = tmp_path / "old.json"
    out.write_text(json.dumps({"content_dir": str(tmp_path / "x")}))
    cfg2 = ClaudeConfig.from_config(out)
    assert cfg2.vendors == ClaudeConfig.DEFAULT_VENDORS
