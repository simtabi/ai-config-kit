"""End-to-end CLI tests: argparse wiring, exit codes, env var precedence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_config_kit.cli import main


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "ai-config-kit" in out
    # Env var section visible in epilog
    assert "CLAUDE_CONFIG_FILE" in out


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "ai-config-kit" in out


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
    # never installed: link missing
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


def test_bootstrap_runs_full_sequence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    target.mkdir()
    rc = main(
        [
            "--content", str(content),
            "--target", str(target),
            "--yes",
            "bootstrap", "--no-git", "--dry-run",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "bootstrap" in out
    assert "validate" in out
    assert "init" in out


def test_bootstrap_real_run_zero_exit(tmp_path: Path) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    target.mkdir()
    rc = main(
        [
            "--content", str(content),
            "--target", str(target),
            "--yes",
            "bootstrap", "--no-git",
        ]
    )
    assert rc == 0
    assert (target / "CLAUDE.md").is_symlink()


def test_cleanup_dry_run_default(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    (content / "claude").mkdir(parents=True)
    target.mkdir()
    (target / ".DS_Store").write_bytes(b"\x00")
    rc = main(["--content", str(content), "--target", str(target), "cleanup"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "dry-run" in out
    assert (target / ".DS_Store").exists()  # not actually deleted


def test_cleanup_apply_deletes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    (content / "claude").mkdir(parents=True)
    target.mkdir()
    (target / ".DS_Store").write_bytes(b"\x00")
    rc = main(
        ["--content", str(content), "--target", str(target), "cleanup", "--apply"]
    )
    assert rc == 0
    assert not (target / ".DS_Store").exists()


def test_list_prints_groups(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    (content / "claude").mkdir(parents=True)
    (content / "claude" / "CLAUDE.md").write_text("x")
    target.mkdir()
    rc = main(["--content", str(content), "--target", str(target), "list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Config files" in out
    assert "CLAUDE.md" in out


def test_view_prints_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    (content / "claude").mkdir(parents=True)
    (content / "claude" / "CLAUDE.md").write_text("hello\nworld\n")
    target.mkdir()
    rc = main(
        ["--content", str(content), "--target", str(target), "view", "CLAUDE.md"]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "hello" in out
    assert "world" in out


def test_view_with_line_numbers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    (content / "claude").mkdir(parents=True)
    (content / "claude" / "x.md").write_text("first\nsecond\n")
    target.mkdir()
    rc = main(
        [
            "--content", str(content),
            "--target", str(target),
            "view", "x.md", "--with-line-numbers",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "1  first" in out
    assert "2  second" in out


def test_view_missing_file_exits_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    (content / "claude").mkdir(parents=True)
    target.mkdir()
    rc = main(
        ["--content", str(content), "--target", str(target), "view", "no.md"]
    )
    assert rc == 2


def test_validate_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    target.mkdir()
    rc = main(["--content", str(content), "--target", str(target), "validate"])
    # Should succeed since tmp_path is writable
    assert rc == 0


def test_uninstall_no_restore_flag(tmp_path: Path) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    (content / "claude").mkdir(parents=True)
    (content / "claude" / "CLAUDE.md").write_text("src")
    target.mkdir()
    (target / "CLAUDE.md").write_text("real")
    main(["--content", str(content), "--target", str(target), "install"])
    backup = target / "CLAUDE.md.before-claude-config"
    assert backup.exists()
    rc = main(
        [
            "--content", str(content),
            "--target", str(target),
            "uninstall", "--no-restore",
        ]
    )
    assert rc == 0
    assert backup.exists()  # backup not restored
    assert not (target / "CLAUDE.md").exists()


def test_decisions_list_via_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    (content / "claude").mkdir(parents=True)
    target.mkdir()
    rc = main(
        ["--content", str(content), "--target", str(target), "decisions", "list"]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "core" in out
    assert "script-generation-pattern" in out


def test_decisions_apply_via_cli(tmp_path: Path) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    (content / "claude").mkdir(parents=True)
    target.mkdir()
    rc = main(
        [
            "--content", str(content),
            "--target", str(target),
            "decisions", "apply", "script-generation-pattern",
        ]
    )
    assert rc == 0
    assert (content / "claude" / "commands" / "generate-via-script.md").is_file()


def test_repair_via_cli(tmp_path: Path) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    (content / "claude").mkdir(parents=True)
    (content / "claude" / "CLAUDE.md").write_text("x")
    target.mkdir()
    main(["--content", str(content), "--target", str(target), "install"])
    (target / "CLAUDE.md").unlink()
    rc = main(["--content", str(content), "--target", str(target), "repair"])
    assert rc == 0
    assert (target / "CLAUDE.md").is_symlink()


def test_init_no_decisions_flag(tmp_path: Path) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    target.mkdir()
    rc = main(
        [
            "--content", str(content),
            "--target", str(target),
            "init", "--no-git", "--no-decisions",
        ]
    )
    assert rc == 0
    assert not (content / "claude" / "commands" / "generate-via-script.md").exists()


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


# --- compose-agents-md + project-install (multi-vendor CLI) -------------


def test_compose_agents_md_via_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    target.mkdir()
    (content / "claude").mkdir(parents=True)
    (content / "claude" / "CLAUDE.md").write_text("# rules\n")
    rc = main(
        [
            "--content", str(content),
            "--target", str(target),
            "compose-agents-md",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "composed AGENTS.md" in out
    assert (content / "claude" / "AGENTS.md").is_file()


def test_compose_agents_md_dry_run_via_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    target.mkdir()
    (content / "claude").mkdir(parents=True)
    rc = main(
        [
            "--content", str(content),
            "--target", str(target),
            "compose-agents-md", "--dry-run",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "dry-run" in out
    assert not (content / "claude" / "AGENTS.md").exists()


def test_project_install_via_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    project = tmp_path / "myproj"
    project.mkdir()
    target.mkdir()
    (content / "claude").mkdir(parents=True)
    (content / "claude" / "AGENTS.md").write_text(
        "<!-- ai-config-kit:autogenerated -->\n# rules\n"
    )
    rc = main(
        [
            "--content", str(content),
            "--target", str(target),
            "project-install", str(project),
            "--vendor", "aider",
            "--vendor", "cursor",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "vendors=aider,cursor" in out
    assert (project / "AGENTS.md").is_file()
    assert (project / ".cursorrules").is_file()


def test_project_install_force_via_cli(tmp_path: Path) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    project = tmp_path / "myproj"
    project.mkdir()
    target.mkdir()
    (content / "claude").mkdir(parents=True)
    (content / "claude" / "AGENTS.md").write_text(
        "<!-- ai-config-kit:autogenerated -->\n# new\n"
    )
    (project / ".cursorrules").write_text("# pre-existing\n")
    rc = main(
        [
            "--content", str(content),
            "--target", str(target),
            "project-install", str(project),
            "--vendor", "cursor", "--force",
        ]
    )
    assert rc == 0
    assert "new" in (project / ".cursorrules").read_text()


def test_project_install_dry_run_via_cli(tmp_path: Path) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    project = tmp_path / "myproj"
    project.mkdir()
    target.mkdir()
    (content / "claude").mkdir(parents=True)
    (content / "claude" / "AGENTS.md").write_text(
        "<!-- ai-config-kit:autogenerated -->\nx\n"
    )
    rc = main(
        [
            "--content", str(content),
            "--target", str(target),
            "project-install", str(project),
            "--vendor", "cursor", "--dry-run",
        ]
    )
    assert rc == 0
    assert not (project / ".cursorrules").exists()


# --- heal verb (Workstream A.2) --------------------------------------------


def test_heal_dry_run_reports_findings_nonzero_exit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """When there's a finding and no --yes, exit is nonzero so CI can
    catch drift. Output names the issue + suggested mode."""
    content = tmp_path / "content"
    target = tmp_path / "target"
    target.mkdir()
    (content / "claude").mkdir(parents=True)
    secret = content / "claude" / "bad.key"
    secret.write_text("priv")
    secret.chmod(0o644)
    rc = main(
        [
            "--content", str(content),
            "--target", str(target),
            "heal",
        ]
    )
    out = capsys.readouterr().out
    assert "sensitive-mode-too-open" in out
    assert "expected=0o600" in out
    assert rc != 0  # findings present, dry-run, nonzero
    import stat as _s
    assert _s.S_IMODE(secret.stat().st_mode) == 0o644  # not mutated


def test_heal_yes_applies_fix_and_exits_zero(
    tmp_path: Path
) -> None:
    """`--yes` actually narrows the mode; exit is 0 after fix."""
    content = tmp_path / "content"
    target = tmp_path / "target"
    target.mkdir()
    (content / "claude").mkdir(parents=True)
    secret = content / "claude" / "go.key"
    secret.write_text("priv")
    secret.chmod(0o644)
    rc = main(
        [
            "--content", str(content),
            "--target", str(target),
            "heal", "--yes",
        ]
    )
    assert rc == 0
    import stat as _s
    assert _s.S_IMODE(secret.stat().st_mode) == 0o600


def test_doctor_heal_shortcut_runs_audit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`doctor --heal` runs the doctor check AND the permission audit
    in one invocation."""
    content = tmp_path / "content"
    target = tmp_path / "target"
    target.mkdir()
    (content / "claude").mkdir(parents=True)
    (content / "claude" / "CLAUDE.md").write_text("x")
    secret = content / "claude" / "y.key"
    secret.write_text("priv")
    secret.chmod(0o644)
    main(
        [
            "--content", str(content),
            "--target", str(target),
            "install",
        ]
    )
    rc = main(
        [
            "--content", str(content),
            "--target", str(target),
            "doctor", "--heal",
        ]
    )
    out = capsys.readouterr().out
    # heal's findings present in output (doctor + audit_permissions both ran)
    assert "sensitive-mode-too-open" in out
    assert rc == 0  # doctor itself happy; heal findings don't fail doctor


# --- capacity verb ---------------------------------------------------------


def test_capacity_via_cli_uses_package_data_fallback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """capacity verb works even without init having dropped the JSON
    into the content dir (loads from package resources)."""
    content = tmp_path / "content"
    target = tmp_path / "target"
    target.mkdir()
    (content / "claude").mkdir(parents=True)
    rc = main(
        [
            "--content", str(content),
            "--target", str(target),
            "capacity",
            "--timezone", "Europe/London",
            "--provider", "anthropic",
        ]
    )
    out = capsys.readouterr().out
    assert "timezone: Europe/London" in out
    assert "anthropic" in out
    # Either GREEN or AMBER depending on current time
    assert any(tag in out for tag in ("GREEN", "AMBER", "UNKNOWN"))
    assert rc == 0  # never all-red without hot-day logic


def test_capacity_via_cli_unknown_timezone_reports_unknown(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    content = tmp_path / "content"
    target = tmp_path / "target"
    target.mkdir()
    (content / "claude").mkdir(parents=True)
    rc = main(
        [
            "--content", str(content),
            "--target", str(target),
            "capacity",
            "--timezone", "Antarctica/Vostok",
            "--provider", "anthropic",
        ]
    )
    out = capsys.readouterr().out
    assert "UNKNOWN" in out
    assert rc == 0  # unknown is informational, not a failure
