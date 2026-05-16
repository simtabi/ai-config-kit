"""End-to-end integration tests on real symlinks (SPEC §5 C6).

The unit tests in test_manager.py cover the surface contract.
This file adds a few real-FS scenarios that exercise the symlink
machinery against actual files instead of fixture dicts.

Each test sets up a tmp_path-rooted content_dir + target_base,
runs the real `install` / `uninstall` cycle, and asserts symlinks
resolve correctly.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ai_config_kit import ClaudeConfig, ConfigError


def _make_cfg(tmp_path: Path, *, with_settings: bool = True) -> ClaudeConfig:
    """Bootstrap a fresh content_dir + target_base under tmp_path."""
    content = tmp_path / "content"
    target = tmp_path / "target"
    (content / "claude").mkdir(parents=True)
    target.mkdir()
    if with_settings:
        (content / "claude" / "CLAUDE.md").write_text("# test\n", encoding="utf-8")
    return ClaudeConfig(content_dir=content, target_base=target)


def test_install_creates_symlink_then_uninstall_removes_it(tmp_path: Path) -> None:
    """End-to-end: install symlinks, uninstall removes them."""
    cfg = _make_cfg(tmp_path)
    cfg.install(dry_run=False)
    link = cfg.target_base / "CLAUDE.md"
    assert link.is_symlink()
    assert link.resolve() == (cfg.src_dir / "CLAUDE.md").resolve()
    cfg.uninstall()
    assert not link.exists()


def test_install_preserves_existing_real_file_via_backup(tmp_path: Path) -> None:
    """A real file at the target path is backed up before symlinking."""
    cfg = _make_cfg(tmp_path)
    real = cfg.target_base / "CLAUDE.md"
    real.write_text("existing content", encoding="utf-8")
    cfg.install(dry_run=False)
    # Symlink replaced the real file
    assert real.is_symlink()
    # Backup sidecar exists
    backup = real.with_suffix(real.suffix + ".before-claude-config")
    assert backup.is_file()
    assert backup.read_text(encoding="utf-8") == "existing content"


def test_uninstall_restores_backup(tmp_path: Path) -> None:
    """uninstall(restore_backups=True) puts the original file back."""
    cfg = _make_cfg(tmp_path)
    real = cfg.target_base / "CLAUDE.md"
    real.write_text("original", encoding="utf-8")
    cfg.install(dry_run=False)
    cfg.uninstall(restore_backups=True)
    assert not real.is_symlink()
    assert real.is_file()
    assert real.read_text(encoding="utf-8") == "original"


def test_install_idempotent_correct_link_not_recreated(tmp_path: Path) -> None:
    """Running install twice leaves the symlink in the same state."""
    cfg = _make_cfg(tmp_path)
    cfg.install(dry_run=False)
    link = cfg.target_base / "CLAUDE.md"
    first_inode = link.lstat().st_ino
    cfg.install(dry_run=False)
    second_inode = link.lstat().st_ino
    assert first_inode == second_inode, "second install should be a no-op"


def test_install_into_nested_directory_creates_parents(tmp_path: Path) -> None:
    """Files in nested content paths get symlinked through new parent dirs."""
    cfg = _make_cfg(tmp_path)
    nested = cfg.src_dir / "commands" / "deep" / "nested.md"
    nested.parent.mkdir(parents=True)
    nested.write_text("deep", encoding="utf-8")
    cfg.install(dry_run=False)
    # `commands` is in the dir-symlink list — whole dir gets one link.
    cmd_link = cfg.target_base / "commands"
    assert cmd_link.is_symlink()
    # Walking through the symlink resolves the nested file.
    assert (cmd_link / "deep" / "nested.md").read_text(encoding="utf-8") == "deep"


@pytest.mark.skipif(
    os.name == "nt",
    reason="POSIX symlink-of-symlink behaviour is OS-dependent on Windows",
)
def test_uninstall_ignores_symlinks_pointing_outside_content_dir(
    tmp_path: Path,
) -> None:
    """A symlink at target_base/ pointing to ELSEWHERE (not into src_dir) is left alone."""
    cfg = _make_cfg(tmp_path)
    outside = tmp_path / "other.md"
    outside.write_text("not ours", encoding="utf-8")
    foreign = cfg.target_base / "other.md"
    foreign.symlink_to(outside)
    cfg.install(dry_run=False)
    cfg.uninstall()
    # `other.md` still resolves outside — uninstall didn't touch it.
    assert foreign.is_symlink()
    assert foreign.resolve() == outside.resolve()


def test_install_refuses_when_src_dir_missing(tmp_path: Path) -> None:
    """install raises ConfigError if claude/ doesn't exist yet."""
    content = tmp_path / "content"
    target = tmp_path / "target"
    content.mkdir()
    target.mkdir()
    cfg = ClaudeConfig(content_dir=content, target_base=target)
    with pytest.raises(ConfigError, match="does not exist"):
        cfg.install(dry_run=False)


def test_decisions_apply_then_install_chain(tmp_path: Path) -> None:
    """Real-FS chain: apply a bundled pack, then install symlinks the result."""
    cfg = _make_cfg(tmp_path, with_settings=False)
    cfg.decisions_apply("script-generation-pattern")
    cfg.install(dry_run=False)
    # The pack writes a commands/ file; commands/ is a dir symlink target.
    cmd = cfg.target_base / "commands" / "generate-via-script.md"
    assert cmd.exists()
    assert cmd.read_text(encoding="utf-8").startswith("---") or cmd.read_text(
        encoding="utf-8"
    ).strip()
