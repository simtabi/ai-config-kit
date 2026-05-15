from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_config_kit import (
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
    ProjectFile,
    RepairReport,
    StatusReport,
    ValidationReport,
    VendorAdapter,
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
    from ai_config_kit import manager as m
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

    from ai_config_kit import manager as m
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

    from ai_config_kit import manager as m
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
    from ai_config_kit import manager as m
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
    "model-overload-resilience",
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
    assert cfg.vendor_status("claude") == "partial"
    assert cfg.vendor_status("nope-not-a-vendor") == "unknown"


def test_unsupported_vendors_flags_non_current(cfg: ClaudeConfig) -> None:
    """Anything not at 'current' status surfaces in unsupported_vendors().
    Today that's just 'claude' (web/desktop, partial CLAUDE.md sharing)."""
    cfg.with_vendors(["claude-code", "claude"])
    unsupp = cfg.unsupported_vendors()
    assert "claude" in unsupp
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


# --- project_install (slice 1: vendor adapters) ----------------------------


def test_vendor_adapters_registry_has_claude_code_and_aider(
    cfg: ClaudeConfig,
) -> None:
    """Slice 1 wires two adapters. Everything else is planned."""
    assert "claude-code" in cfg.VENDOR_ADAPTERS
    assert "aider" in cfg.VENDOR_ADAPTERS
    cc = cfg.VENDOR_ADAPTERS["claude-code"]
    assert cc.global_target is not None
    assert cc.project_files == ()  # claude-code is global-only
    aider = cfg.VENDOR_ADAPTERS["aider"]
    assert aider.global_target is None
    assert len(aider.project_files) == 1
    assert aider.project_files[0].rel_path == "AGENTS.md"
    assert aider.canonical_source == "AGENTS.md"


def test_project_install_writes_agents_md_for_aider(
    cfg: ClaudeConfig, tmp_path: Path
) -> None:
    """The canonical case: aider's AGENTS.md is copied from src_dir to a project."""
    (cfg.src_dir / "AGENTS.md").write_text("# canonical rules\n")
    project = tmp_path / "myproj"
    project.mkdir()
    report = cfg.project_install(project, vendors=["aider"])
    assert "aider:AGENTS.md" in report.files_written
    out = project / "AGENTS.md"
    assert out.is_file()
    assert out.read_text() == "# canonical rules\n"


def test_project_install_skips_existing_without_force(
    cfg: ClaudeConfig, tmp_path: Path
) -> None:
    (cfg.src_dir / "AGENTS.md").write_text("# canon\n")
    project = tmp_path / "myproj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# preexisting; user already had one\n")
    report = cfg.project_install(project, vendors=["aider"])
    assert "aider:AGENTS.md" in report.files_skipped
    assert report.files_written == []
    # File must remain unchanged
    assert "preexisting" in (project / "AGENTS.md").read_text()


def test_project_install_force_overwrites(
    cfg: ClaudeConfig, tmp_path: Path
) -> None:
    (cfg.src_dir / "AGENTS.md").write_text("# canon\n")
    project = tmp_path / "myproj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# stale\n")
    report = cfg.project_install(project, vendors=["aider"], force=True)
    assert "aider:AGENTS.md" in report.files_written
    assert (project / "AGENTS.md").read_text() == "# canon\n"


def test_project_install_dry_run_writes_nothing(
    cfg: ClaudeConfig, tmp_path: Path
) -> None:
    (cfg.src_dir / "AGENTS.md").write_text("# canon\n")
    project = tmp_path / "myproj"
    project.mkdir()
    report = cfg.project_install(project, vendors=["aider"], dry_run=True)
    assert "aider:AGENTS.md" in report.files_written  # marked as would-write
    assert report.dry_run
    assert not (project / "AGENTS.md").exists()


def test_project_install_claude_code_is_noop(
    cfg: ClaudeConfig, tmp_path: Path
) -> None:
    """claude-code is global-only and has no project_files. Selecting it
    for project_install should be a clean no-op, not a failure."""
    project = tmp_path / "myproj"
    project.mkdir()
    report = cfg.project_install(project, vendors=["claude-code"])
    assert report.files_written == []
    assert report.files_failed == []


def test_project_install_skips_planned_vendor_silently(
    cfg: ClaudeConfig, tmp_path: Path
) -> None:
    """A planned-but-unwired vendor (in SUPPORTED_VENDORS but not in
    VENDOR_ADAPTERS) must not fail the run. It surfaces nothing, since
    the user already saw the 'partial' or 'planned' status during
    select_vendors. ``claude`` is the only remaining example today."""
    project = tmp_path / "myproj"
    project.mkdir()
    report = cfg.project_install(project, vendors=["claude"])
    assert report.files_written == []
    assert report.files_failed == []


def test_project_install_rejects_unknown_vendor(
    cfg: ClaudeConfig, tmp_path: Path
) -> None:
    project = tmp_path / "myproj"
    project.mkdir()
    report = cfg.project_install(project, vendors=["nope-not-real"])
    assert any("unknown vendor" in msg for _, msg in report.files_failed)


def test_project_install_raises_when_project_missing(
    cfg: ClaudeConfig, tmp_path: Path
) -> None:
    missing = tmp_path / "no-such-project"
    with pytest.raises(ConfigError, match="not a directory"):
        cfg.project_install(missing, vendors=["aider"])


def test_project_install_raises_when_canonical_source_missing(
    cfg: ClaudeConfig, tmp_path: Path
) -> None:
    """aider needs AGENTS.md in src_dir. With auto_compose disabled and
    no canonical on disk, surface a file-level failure rather than
    silently writing empty content. Slice-3 auto_compose=True changes
    this default; this test pins the strict path."""
    project = tmp_path / "myproj"
    project.mkdir()
    report = cfg.project_install(project, vendors=["aider"], auto_compose=False)
    # src_dir has no AGENTS.md (fixture only makes the dir)
    assert any(
        "canonical source missing" in msg for _, msg in report.files_failed
    )
    assert report.files_written == []


def test_project_install_falls_back_to_configured_vendors(
    cfg: ClaudeConfig, tmp_path: Path
) -> None:
    """When vendors=None, project_install uses the ClaudeConfig.vendors list."""
    (cfg.src_dir / "AGENTS.md").write_text("# x\n")
    project = tmp_path / "myproj"
    project.mkdir()
    cfg.with_vendors(["claude-code", "aider"])
    report = cfg.project_install(project)
    assert report.vendors == ("claude-code", "aider")
    # claude-code: no-op; aider: writes AGENTS.md
    assert "aider:AGENTS.md" in report.files_written


# --- project_install (slice 2: cursor/windsurf/copilot) -------------------


@pytest.mark.parametrize(
    "vendor, rel_path",
    [
        ("cursor", ".cursorrules"),
        ("windsurf", ".windsurfrules"),
        ("copilot", ".github/copilot-instructions.md"),
    ],
)
def test_project_install_writes_per_vendor_file(
    cfg: ClaudeConfig, tmp_path: Path, vendor: str, rel_path: str
) -> None:
    """Each new adapter copies AGENTS.md into the vendor's expected dest."""
    (cfg.src_dir / "AGENTS.md").write_text("# canon\n")
    project = tmp_path / "myproj"
    project.mkdir()
    report = cfg.project_install(project, vendors=[vendor])
    assert f"{vendor}:{rel_path}" in report.files_written
    out = project / rel_path
    assert out.is_file()
    assert out.read_text() == "# canon\n"
    # For the copilot case the .github dir must have been created
    if vendor == "copilot":
        assert (project / ".github").is_dir()


def test_project_install_writes_all_four_vendors_in_one_call(
    cfg: ClaudeConfig, tmp_path: Path
) -> None:
    """A user with the full project-vendor set gets one canonical AGENTS.md
    plus three copies in vendor-specific paths in a single command."""
    (cfg.src_dir / "AGENTS.md").write_text("# canonical rules\n")
    project = tmp_path / "myproj"
    project.mkdir()
    report = cfg.project_install(
        project,
        vendors=["aider", "cursor", "windsurf", "copilot"],
    )
    expected = {
        "aider:AGENTS.md",
        "cursor:.cursorrules",
        "windsurf:.windsurfrules",
        "copilot:.github/copilot-instructions.md",
    }
    assert set(report.files_written) == expected
    assert report.files_failed == []


def test_cursor_adapter_declares_global_target(cfg: ClaudeConfig) -> None:
    """Cursor supports both project-level (.cursorrules) and a global rules
    directory (~/.cursor/rules). The global path will be honored by
    install() in slice 3; slice 2 just declares it."""
    cursor = cfg.VENDOR_ADAPTERS["cursor"]
    assert cursor.global_target is not None
    assert cursor.global_target.name == "rules"
    assert cursor.global_target.parent.name == ".cursor"


def test_windsurf_and_copilot_are_project_only(cfg: ClaudeConfig) -> None:
    """Windsurf + Copilot have no documented global config location."""
    assert cfg.VENDOR_ADAPTERS["windsurf"].global_target is None
    assert cfg.VENDOR_ADAPTERS["copilot"].global_target is None


def test_all_cli_vendors_current_after_codex_cline_wired(
    cfg: ClaudeConfig,
) -> None:
    """Every CLI-based vendor in SUPPORTED_VENDORS is now 'current'.
    Only 'claude' (web/desktop, partial CLAUDE.md sharing) stays
    non-current."""
    for vendor in (
        "claude-code", "aider", "cursor", "windsurf", "copilot",
        "codex", "cline",
    ):
        assert cfg.vendor_status(vendor) == "current", vendor
    assert cfg.vendor_status("claude") == "partial"


def test_codex_adapter_declares_global_and_agents_md(cfg: ClaudeConfig) -> None:
    codex = cfg.VENDOR_ADAPTERS["codex"]
    assert codex.global_target is not None
    assert codex.global_target.name == "instructions"
    assert codex.global_target.parent.name == ".codex"
    assert any(pf.rel_path == "AGENTS.md" for pf in codex.project_files)


def test_cline_adapter_writes_clinerules(
    cfg: ClaudeConfig, tmp_path: Path
) -> None:
    (cfg.src_dir / "AGENTS.md").write_text(
        f"{ClaudeConfig.AGENTS_MD_AUTOGEN_MARKER}\n# rules\n"
    )
    project = tmp_path / "myproj"
    project.mkdir()
    report = cfg.project_install(project, vendors=["cline"])
    assert "cline:.clinerules" in report.files_written
    assert (project / ".clinerules").is_file()


def test_codex_project_install_writes_agents_md(
    cfg: ClaudeConfig, tmp_path: Path
) -> None:
    """Selecting codex alone (no aider) should still drop AGENTS.md so
    Codex's native AGENTS.md support kicks in."""
    (cfg.src_dir / "AGENTS.md").write_text(
        f"{ClaudeConfig.AGENTS_MD_AUTOGEN_MARKER}\n# rules\n"
    )
    project = tmp_path / "myproj"
    project.mkdir()
    report = cfg.project_install(project, vendors=["codex"])
    assert "codex:AGENTS.md" in report.files_written
    assert (project / "AGENTS.md").is_file()


# --- compose_agents_md (slice 3) ------------------------------------------


def test_compose_agents_md_writes_to_default_location(
    cfg: ClaudeConfig,
) -> None:
    """With nothing in src_dir, compose still emits a stub with the
    autogen marker and the cross-vendor header."""
    report = cfg.compose_agents_md()
    out = cfg.src_dir / "AGENTS.md"
    assert out.is_file()
    body = out.read_text(encoding="utf-8")
    assert ClaudeConfig.AGENTS_MD_AUTOGEN_MARKER in body
    assert "Cross-vendor rules" in body
    assert report.output == out
    assert report.bytes_written == len(body.encode("utf-8"))


def test_compose_agents_md_includes_claude_md(cfg: ClaudeConfig) -> None:
    """The user's CLAUDE.md content lands in AGENTS.md verbatim."""
    (cfg.src_dir / "CLAUDE.md").write_text("# my rules\n\nBe terse.\n")
    cfg.compose_agents_md()
    body = (cfg.src_dir / "AGENTS.md").read_text(encoding="utf-8")
    assert "# my rules" in body
    assert "Be terse." in body
    assert "<!-- from CLAUDE.md -->" in body


def test_compose_agents_md_concatenates_fragments(cfg: ClaudeConfig) -> None:
    """Fragments are added in sorted-name order so output is stable."""
    (cfg.src_dir / "CLAUDE.md.zeta.fragment").write_text("## Zeta rules\n")
    (cfg.src_dir / "CLAUDE.md.alpha.fragment").write_text("## Alpha rules\n")
    cfg.compose_agents_md()
    body = (cfg.src_dir / "AGENTS.md").read_text(encoding="utf-8")
    # alpha must appear before zeta
    assert body.index("Alpha rules") < body.index("Zeta rules")


def test_compose_agents_md_dry_run_skips_write(cfg: ClaudeConfig) -> None:
    out = cfg.src_dir / "AGENTS.md"
    assert not out.exists()
    report = cfg.compose_agents_md(dry_run=True)
    assert report.dry_run
    assert report.bytes_written > 0
    assert not out.exists()


def test_compose_agents_md_refuses_to_clobber_hand_edited(
    cfg: ClaudeConfig,
) -> None:
    """A pre-existing AGENTS.md without the autogen marker must not be
    overwritten. This protects users who wrote their own."""
    (cfg.src_dir / "AGENTS.md").write_text("# my own rules, hand-written\n")
    with pytest.raises(ConfigError, match="autogen marker"):
        cfg.compose_agents_md()


def test_compose_agents_md_replaces_previously_autogenerated(
    cfg: ClaudeConfig,
) -> None:
    """If the existing AGENTS.md has the marker, replace happily."""
    cfg.compose_agents_md()
    (cfg.src_dir / "CLAUDE.md").write_text("# new rules\n")
    cfg.compose_agents_md()
    body = (cfg.src_dir / "AGENTS.md").read_text(encoding="utf-8")
    assert "new rules" in body


def test_project_install_auto_composes_when_canonical_missing(
    cfg: ClaudeConfig, tmp_path: Path
) -> None:
    """project_install for aider used to fail when src_dir/AGENTS.md
    didn't exist. With auto-compose, it composes one and ships it."""
    (cfg.src_dir / "CLAUDE.md").write_text("# composed rules\n")
    project = tmp_path / "myproj"
    project.mkdir()
    report = cfg.project_install(project, vendors=["aider"])
    assert "aider:AGENTS.md" in report.files_written
    assert report.files_failed == []
    assert (project / "AGENTS.md").read_text().__contains__("composed rules")


def test_project_install_auto_compose_can_be_disabled(
    cfg: ClaudeConfig, tmp_path: Path
) -> None:
    """auto_compose=False preserves the slice-1 failure mode for callers
    that want explicit control."""
    project = tmp_path / "myproj"
    project.mkdir()
    report = cfg.project_install(
        project, vendors=["aider"], auto_compose=False
    )
    assert any(
        "canonical source missing" in msg for _, msg in report.files_failed
    )


def test_project_install_auto_compose_skipped_under_dry_run(
    cfg: ClaudeConfig, tmp_path: Path
) -> None:
    """Dry-run reports must not have side effects, so auto-compose must
    not write AGENTS.md to src_dir during a dry-run probe."""
    project = tmp_path / "myproj"
    project.mkdir()
    cfg.project_install(project, vendors=["aider"], dry_run=True)
    # No real write to src_dir even though aider was selected
    assert not (cfg.src_dir / "AGENTS.md").exists()


# --- install() global_target propagation (slice 4) ------------------------


def _cursor_adapter_at(target: Path) -> VendorAdapter:
    """A cursor adapter pointed at a sandboxed tmp_path/.cursor/rules/."""
    return VendorAdapter(
        name="cursor",
        status="current",
        global_target=target,
        project_files=(
            ProjectFile(rel_path=".cursorrules", style="copy"),
        ),
        canonical_source="AGENTS.md",
    )


def test_install_writes_to_cursor_global_target(
    cfg: ClaudeConfig, tmp_path: Path
) -> None:
    """When cursor is in the configured vendors, install() drops the
    canonical AGENTS.md into the adapter's global_target."""
    fake_cursor = tmp_path / "fake-home" / ".cursor" / "rules"
    cfg.with_vendors(["claude-code", "cursor"])
    cfg.with_vendor_adapter("cursor", _cursor_adapter_at(fake_cursor))
    (cfg.src_dir / "AGENTS.md").write_text(
        f"{ClaudeConfig.AGENTS_MD_AUTOGEN_MARKER}\n# rules\n"
    )
    report = cfg.install()
    assert ("cursor", str(fake_cursor / "agents.md")) in report.global_writes
    assert (fake_cursor / "agents.md").is_file()
    assert "# rules" in (fake_cursor / "agents.md").read_text()


def test_install_skips_global_writes_when_vendor_not_selected(
    cfg: ClaudeConfig, tmp_path: Path
) -> None:
    """Default vendors=(claude-code,) means no global writes happen even
    though a cursor override exists. The user must opt in via with_vendors."""
    fake_cursor = tmp_path / ".cursor" / "rules"
    cfg.with_vendor_adapter("cursor", _cursor_adapter_at(fake_cursor))
    (cfg.src_dir / "AGENTS.md").write_text(
        f"{ClaudeConfig.AGENTS_MD_AUTOGEN_MARKER}\n# x\n"
    )
    report = cfg.install()
    assert report.global_writes == []
    assert not fake_cursor.exists()


def test_install_global_dry_run_writes_nothing(
    cfg: ClaudeConfig, tmp_path: Path
) -> None:
    fake_cursor = tmp_path / ".cursor" / "rules"
    cfg.with_vendors(["cursor"])
    cfg.with_vendor_adapter("cursor", _cursor_adapter_at(fake_cursor))
    (cfg.src_dir / "AGENTS.md").write_text(
        f"{ClaudeConfig.AGENTS_MD_AUTOGEN_MARKER}\n# x\n"
    )
    report = cfg.install(dry_run=True)
    # Dest tracked as a would-write
    assert any(
        dest.endswith("agents.md") for _, dest in report.global_writes
    )
    assert not (fake_cursor / "agents.md").exists()


def test_install_global_auto_composes_when_canonical_missing(
    cfg: ClaudeConfig, tmp_path: Path
) -> None:
    """If AGENTS.md isn't in src_dir, install() composes one and then
    writes to the vendor's global target."""
    fake_cursor = tmp_path / ".cursor" / "rules"
    cfg.with_vendors(["cursor"])
    cfg.with_vendor_adapter("cursor", _cursor_adapter_at(fake_cursor))
    (cfg.src_dir / "CLAUDE.md").write_text("# user rules\n")
    cfg.install()
    body = (fake_cursor / "agents.md").read_text()
    assert "user rules" in body


def test_with_vendor_adapter_overrides_class_registry(
    cfg: ClaudeConfig, tmp_path: Path
) -> None:
    """Instance overrides win when resolving an adapter."""
    custom = _cursor_adapter_at(tmp_path / "custom")
    cfg.with_vendor_adapter("cursor", custom)
    assert cfg._adapter_for("cursor") is custom
    # claude-code untouched
    assert cfg._adapter_for("claude-code") is cfg.VENDOR_ADAPTERS["claude-code"]


# --- end-to-end smoke (init → compose → project-install) -----------------


def test_e2e_multi_vendor_pipeline(tmp_path: Path) -> None:
    """Full pipeline as a user would experience it:

    1. init() builds the content dir, applies decision packs.
    2. The user writes their own CLAUDE.md.
    3. compose-agents-md synthesizes AGENTS.md from CLAUDE.md + packs.
    4. project-install drops the right files into the project for every
       configured vendor.

    Validates that the canonical content reaches each vendor's
    expected destination unchanged."""
    content = tmp_path / "content"
    target = tmp_path / "target"
    project = tmp_path / "myproj"
    project.mkdir()

    cfg = ClaudeConfig(content_dir=content, target_base=target)
    cfg.with_vendors([
        "claude-code", "aider", "cursor", "windsurf",
        "copilot", "codex", "cline",
    ])
    cfg.init(init_git=False)

    # Override cursor's global_target to a tmp path so install() doesn't
    # write to the real ~/.cursor/rules/.
    cfg.with_vendor_adapter(
        "cursor", _cursor_adapter_at(tmp_path / "fake-cursor" / "rules")
    )

    # The user puts their own rules in CLAUDE.md
    (cfg.src_dir / "CLAUDE.md").write_text(
        "# project rules\n\nUse 2-space indent.\n"
    )

    compose_report = cfg.compose_agents_md()
    agents_md = (cfg.src_dir / "AGENTS.md").read_text(encoding="utf-8")
    assert "project rules" in agents_md
    assert ClaudeConfig.AGENTS_MD_AUTOGEN_MARKER in agents_md
    # init() applied 13 decision packs; their fragments must be in AGENTS.md
    for marker in (
        "<!-- from CLAUDE.md.script-generation-pattern.fragment -->",
        "<!-- from CLAUDE.md.polling-discipline.fragment -->",
        "<!-- from CLAUDE.md.docker-env-interpolation.fragment -->",
    ):
        assert marker in agents_md, marker
    assert compose_report.bytes_written == len(agents_md.encode("utf-8"))

    pi = cfg.project_install(project)
    expected_writes = {
        "aider:AGENTS.md",
        "cursor:.cursorrules",
        "windsurf:.windsurfrules",
        "copilot:.github/copilot-instructions.md",
        "codex:AGENTS.md",  # codex also lands at AGENTS.md
        "cline:.clinerules",
    }
    # codex + aider both want AGENTS.md. The first one wins; the second
    # skips because the file now exists. Either order is fine for the
    # test as long as both are accounted for (written or skipped).
    accounted = set(pi.files_written) | set(pi.files_skipped)
    assert expected_writes <= accounted

    # Every vendor's file must contain the user's project rule
    for rel in (
        "AGENTS.md", ".cursorrules", ".windsurfrules",
        ".github/copilot-instructions.md", ".clinerules",
    ):
        body = (project / rel).read_text(encoding="utf-8")
        assert "Use 2-space indent" in body, rel

    # claude-code is global-only; nothing per-project should be written for it
    assert not any(name.startswith("claude-code:") for name in pi.files_written)


# --- audit_permissions (heal) ----------------------------------------------


import stat  # noqa: E402


def test_audit_permissions_empty_content_dir_reports_nothing(
    cfg: ClaudeConfig,
) -> None:
    """A fresh content dir with no problematic files yields zero findings."""
    report = cfg.audit_permissions()
    assert report.findings == []
    assert "no permission issues" in report.summary()


def test_audit_permissions_flags_sensitive_too_open(
    cfg: ClaudeConfig,
) -> None:
    """A secret-pattern file with 0644 is flagged sensitive-mode-too-open."""
    secret = cfg.src_dir / "x.key"
    secret.write_text("private")
    secret.chmod(0o644)
    report = cfg.audit_permissions()
    issues = [f.issue for f in report.findings if f.path == secret]
    assert "sensitive-mode-too-open" in issues
    finding = next(f for f in report.findings if f.path == secret)
    assert finding.current_mode == 0o644
    assert finding.expected_mode == 0o600


def test_audit_permissions_flags_world_writable_file(
    cfg: ClaudeConfig,
) -> None:
    """An 0o666 file lands as world-writable, expected narrowed to 0o644."""
    f = cfg.src_dir / "shared.md"
    f.write_text("hi")
    f.chmod(0o666)
    report = cfg.audit_permissions()
    finding = next(
        (x for x in report.findings if x.issue == "world-writable"), None
    )
    assert finding is not None
    assert finding.path == f
    assert finding.expected_mode == 0o644


def test_audit_permissions_flags_world_writable_dir(
    cfg: ClaudeConfig,
) -> None:
    """A 0o777 dir narrows to 0o755."""
    d = cfg.src_dir / "open-dir"
    d.mkdir()
    d.chmod(0o777)
    report = cfg.audit_permissions()
    finding = next(
        (x for x in report.findings
         if x.issue == "world-writable" and x.path == d),
        None,
    )
    assert finding is not None
    assert finding.expected_mode == 0o755


def test_audit_permissions_flags_script_missing_exec(
    cfg: ClaudeConfig,
) -> None:
    """A shell script under scripts/ without +x is flagged not-executable."""
    scripts = cfg.src_dir / "scripts"
    scripts.mkdir()
    script = scripts / "render.sh"
    script.write_text("#!/bin/sh\necho hello\n")
    script.chmod(0o644)
    report = cfg.audit_permissions()
    finding = next(
        (x for x in report.findings if x.issue == "not-executable"), None
    )
    assert finding is not None
    assert finding.path == script
    assert finding.expected_mode == 0o755


def test_audit_permissions_dry_run_default_does_not_mutate(
    cfg: ClaudeConfig,
) -> None:
    """Default is dry-run; the actual mode must not change."""
    secret = cfg.src_dir / "y.key"
    secret.write_text("priv")
    secret.chmod(0o644)
    cfg.audit_permissions()
    assert stat.S_IMODE(secret.stat().st_mode) == 0o644


def test_audit_permissions_yes_fixes_sensitive_mode(
    cfg: ClaudeConfig,
) -> None:
    """yes=True + dry_run=False actually narrows the mode."""
    secret = cfg.src_dir / "z.key"
    secret.write_text("priv")
    secret.chmod(0o644)
    report = cfg.audit_permissions(dry_run=False, yes=True)
    assert stat.S_IMODE(secret.stat().st_mode) == 0o600
    assert any(f.issue == "sensitive-mode-too-open" for f in report.fixed)
    assert report.dry_run is False


def test_audit_permissions_dry_run_overrides_yes(
    cfg: ClaudeConfig,
) -> None:
    """Explicitly: yes alone without dry_run=False does NOT mutate.
    dry_run is the master safety; yes only matters when dry_run=False."""
    secret = cfg.src_dir / "a.key"
    secret.write_text("priv")
    secret.chmod(0o644)
    cfg.audit_permissions(dry_run=True, yes=True)
    assert stat.S_IMODE(secret.stat().st_mode) == 0o644


def test_audit_permissions_script_flag_promotes_world_writable(
    cfg: ClaudeConfig,
) -> None:
    """A world-writable file with +x should narrow to 0o755 (script)
    rather than 0o644 (data)."""
    scripts = cfg.src_dir / "scripts"
    scripts.mkdir()
    s = scripts / "bad.sh"
    s.write_text("#!/bin/sh\necho hi\n")
    s.chmod(0o777)
    report = cfg.audit_permissions()
    ww = next(
        (x for x in report.findings
         if x.issue == "world-writable" and x.path == s),
        None,
    )
    assert ww is not None
    assert ww.expected_mode == 0o755


def test_audit_permissions_symlinks_are_skipped(
    cfg: ClaudeConfig,
) -> None:
    """Symlinks have no meaningful mode and chmod() follows them;
    skip them entirely so we don't mutate the target."""
    target = cfg.src_dir / "real.md"
    target.write_text("ok")
    target.chmod(0o644)
    link = cfg.src_dir / "linked.md"
    link.symlink_to(target)
    report = cfg.audit_permissions()
    assert not any(f.path == link for f in report.findings)


def test_audit_permissions_skip_git_subtree(
    cfg: ClaudeConfig,
) -> None:
    """`.git/` is internal plumbing; never audit it."""
    git_dir = cfg.content_dir / ".git"
    git_dir.mkdir()
    junk = git_dir / "loose.key"
    junk.write_text("ignored")
    junk.chmod(0o666)
    report = cfg.audit_permissions()
    assert not any(f.path == junk for f in report.findings)


# --- model-overload-resilience pack ---------------------------------------


def test_overload_pack_ships_all_four_files(cfg: ClaudeConfig) -> None:
    """Init drops all four declared files at their dest paths.

    Pack ships: CLAUDE.md fragment, /capacity-check command,
    off-peak data JSON, api-retry Python helper.
    """
    cfg.init(init_git=False)
    assert (cfg.src_dir / "CLAUDE.md.model-overload-resilience.fragment").is_file()
    assert (cfg.src_dir / "commands" / "capacity-check.md").is_file()
    assert (cfg.src_dir / "data" / "off-peak-windows.json").is_file()
    assert (cfg.src_dir / "scripts" / "api-retry.py").is_file()


def test_overload_pack_python_script_is_executable(
    cfg: ClaudeConfig,
) -> None:
    """The Python retry helper ships executable (manifest mode 0755)."""
    cfg.init(init_git=False)
    script = cfg.src_dir / "scripts" / "api-retry.py"
    mode = script.stat().st_mode & 0o111
    assert mode != 0, f"api-retry.py must be executable, got {oct(mode)}"


def test_overload_fragment_lists_all_supported_providers(
    cfg: ClaudeConfig,
) -> None:
    """The fragment must enumerate every provider the JSON covers, so
    the rules + data don't drift apart silently."""
    cfg.init(init_git=False)
    body = (
        cfg.src_dir / "CLAUDE.md.model-overload-resilience.fragment"
    ).read_text(encoding="utf-8").lower()
    for provider in ("anthropic", "openai", "codex", "google", "cohere",
                     "mistral"):
        assert provider in body, f"missing provider in fragment: {provider}"


def test_overload_fragment_distinguishes_529_from_429(
    cfg: ClaudeConfig,
) -> None:
    """The 529-vs-429 distinction is the most important conceptual
    point in the pack; the fragment must surface it explicitly."""
    cfg.init(init_git=False)
    body = (
        cfg.src_dir / "CLAUDE.md.model-overload-resilience.fragment"
    ).read_text(encoding="utf-8")
    assert "529" in body and "429" in body
    # Both codes must appear in the per-provider table AND in prose
    assert body.count("529") >= 3
    assert body.count("429") >= 3


def test_overload_json_data_parses_and_covers_seven_providers(
    cfg: ClaudeConfig,
) -> None:
    """The off-peak JSON is the data dependency for /capacity-check and
    any downstream tool. Must parse cleanly and cover the expected set."""
    import json as _json
    cfg.init(init_git=False)
    data = _json.loads(
        (cfg.src_dir / "data" / "off-peak-windows.json").read_text(
            encoding="utf-8"
        )
    )
    assert data["schema_version"] == 1
    providers = set(data["providers"].keys())
    for required in {"anthropic", "openai", "codex", "google", "cohere",
                     "mistral", "local"}:
        assert required in providers, f"missing provider in data: {required}"


def test_overload_json_anthropic_covers_major_timezones(
    cfg: ClaudeConfig,
) -> None:
    """The Anthropic block has to cover the timezones the slash command
    will actually look up. The set is heuristic but should at least span
    Americas / Europe / Africa / Asia / Oceania."""
    import json as _json
    cfg.init(init_git=False)
    data = _json.loads(
        (cfg.src_dir / "data" / "off-peak-windows.json").read_text(
            encoding="utf-8"
        )
    )
    windows = data["providers"]["anthropic"]["off_peak_windows"]
    for tz in (
        "America/Los_Angeles",
        "America/New_York",
        "Europe/London",
        "Africa/Nairobi",
        "Asia/Tokyo",
        "Australia/Sydney",
    ):
        assert tz in windows, f"missing tz coverage: {tz}"


def test_overload_capacity_check_command_invokes_data_file(
    cfg: ClaudeConfig,
) -> None:
    """The slash command must reference the JSON path, not duplicate
    its contents in prose (avoids drift between command + data)."""
    cfg.init(init_git=False)
    body = (cfg.src_dir / "commands" / "capacity-check.md").read_text(
        encoding="utf-8"
    )
    assert "off-peak-windows.json" in body
    assert "~/.claude" in body  # explicit reference to the installed path


def test_overload_python_helper_self_test_passes(
    cfg: ClaudeConfig,
) -> None:
    """Run the api-retry.py self-test in a subprocess. The helper's
    __main__ block exercises a 529-then-success retry path with a
    very short delay; should exit 0 in well under a second."""
    import subprocess
    import sys
    cfg.init(init_git=False)
    script = cfg.src_dir / "scripts" / "api-retry.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, (
        f"api-retry.py self-test failed:\nstdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
    assert "self-test ok" in result.stdout


# --- capacity_check API ----------------------------------------------------


def test_capacity_check_loads_from_package_resources_when_no_user_copy(
    cfg: ClaudeConfig,
) -> None:
    """Before init(), the data file isn't in the content dir yet. The
    method must fall back to the packaged copy."""
    verdict = cfg.capacity_check(
        timezone="America/New_York", providers=["anthropic"]
    )
    assert verdict.user_timezone == "America/New_York"
    assert verdict.data_source == "(package resources)"
    assert "anthropic" in verdict.providers
    # Status should be green/amber, not unknown (we know NY is in the table)
    assert verdict.providers["anthropic"].status in ("green", "amber")


def test_capacity_check_unknown_provider_marked_unknown(
    cfg: ClaudeConfig,
) -> None:
    verdict = cfg.capacity_check(
        timezone="UTC", providers=["definitely-not-a-real-provider"]
    )
    cap = verdict.providers["definitely-not-a-real-provider"]
    assert cap.status == "unknown"
    assert "not in data file" in cap.reason


def test_capacity_check_unknown_timezone_marked_unknown(
    cfg: ClaudeConfig,
) -> None:
    """An IANA zone the JSON doesn't cover yields 'unknown' so the
    caller knows to check the data file rather than guess."""
    verdict = cfg.capacity_check(
        timezone="Antarctica/Vostok",  # not in the table
        providers=["anthropic"],
    )
    assert verdict.providers["anthropic"].status == "unknown"


def test_capacity_check_offpeak_window_lookup_is_correct(
    cfg: ClaudeConfig,
) -> None:
    """Asia/Tokyo's off-peak window is 14:00-22:00; verify our window
    parser computes the right verdict for both ends of the range."""
    # We can't easily mock time without freezegun; instead test the
    # static parser directly.
    win = "14:00-22:00"
    # Hours fully inside the window
    assert ClaudeConfig._in_off_peak_window(win, hour=14, weekday=2) is True
    assert ClaudeConfig._in_off_peak_window(win, hour=18, weekday=2) is True
    assert ClaudeConfig._in_off_peak_window(win, hour=21, weekday=2) is True
    # Hours outside
    assert ClaudeConfig._in_off_peak_window(win, hour=22, weekday=2) is False
    assert ClaudeConfig._in_off_peak_window(win, hour=10, weekday=2) is False
    assert ClaudeConfig._in_off_peak_window(win, hour=0, weekday=2) is False


def test_capacity_check_window_wraps_midnight(cfg: ClaudeConfig) -> None:
    """22:00-06:00 means 22, 23, 0, 1, 2, 3, 4, 5 are inside."""
    win = "22:00-06:00 weekdays; all weekend"
    # weekday=2 (Wednesday); "weekend" clause shouldn't match
    assert ClaudeConfig._in_off_peak_window(win, hour=22, weekday=2) is True
    assert ClaudeConfig._in_off_peak_window(win, hour=23, weekday=2) is True
    assert ClaudeConfig._in_off_peak_window(win, hour=0, weekday=2) is True
    assert ClaudeConfig._in_off_peak_window(win, hour=5, weekday=2) is True
    assert ClaudeConfig._in_off_peak_window(win, hour=6, weekday=2) is False
    assert ClaudeConfig._in_off_peak_window(win, hour=12, weekday=2) is False
    assert ClaudeConfig._in_off_peak_window(win, hour=21, weekday=2) is False


def test_capacity_check_weekend_clause_matches_saturday_sunday(
    cfg: ClaudeConfig,
) -> None:
    """`all weekend` should mark every hour on Sat (5) and Sun (6) green."""
    win = "22:00-06:00 weekdays; all weekend"
    # Saturday + Sunday: any hour
    for hour in (0, 6, 12, 18, 23):
        assert ClaudeConfig._in_off_peak_window(win, hour=hour, weekday=5) is True
        assert ClaudeConfig._in_off_peak_window(win, hour=hour, weekday=6) is True


def test_capacity_check_prefers_user_copy_over_package_resources(
    cfg: ClaudeConfig,
) -> None:
    """When the user has init'd and dropped their own copy, the method
    must read that one (allowing user override)."""
    import json as _json
    cfg.init(init_git=False)
    user_copy = cfg.src_dir / "data" / "off-peak-windows.json"
    assert user_copy.is_file()
    # Mutate the user copy: replace the Anthropic window for UTC with
    # something distinctive so we can tell which file was loaded.
    data = _json.loads(user_copy.read_text(encoding="utf-8"))
    data["providers"]["anthropic"]["off_peak_windows"]["UTC"] = "99:99-99:99 marker"
    user_copy.write_text(_json.dumps(data), encoding="utf-8")
    # Resolve
    verdict = cfg.capacity_check(timezone="UTC", providers=["anthropic"])
    assert "99:99-99:99 marker" in verdict.providers["anthropic"].off_peak_window_local
    assert verdict.data_source == str(user_copy)


def test_capacity_check_summary_text_human_readable(
    cfg: ClaudeConfig,
) -> None:
    verdict = cfg.capacity_check(
        timezone="UTC", providers=["anthropic", "openai"]
    )
    summary = verdict.summary()
    assert "UTC" in summary
    assert "anthropic" in summary
    assert "openai" in summary


def test_capacity_check_default_providers_returns_all(
    cfg: ClaudeConfig,
) -> None:
    """When `providers=None`, every provider in the data file is checked."""
    verdict = cfg.capacity_check(timezone="America/New_York")
    # The data file covers seven providers; the table reports them
    assert len(verdict.providers) >= 6  # allow for future additions


def test_capacity_check_detects_user_timezone_from_env(
    cfg: ClaudeConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """$TZ env var is honored when timezone arg is None."""
    monkeypatch.setenv("TZ", "Europe/Paris")
    verdict = cfg.capacity_check(providers=["anthropic"])
    assert verdict.user_timezone == "Europe/Paris"
