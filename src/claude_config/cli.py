"""Thin CLI wrapper around ClaudeConfig."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .manager import ClaudeConfig, ConfigError


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="claude-config",
        description="Manage Claude Code's ~/.claude/ via symlinks from a content dir.",
        epilog=(
            "Env vars (override JSON config, overridden by CLI flags):\n"
            "  CLAUDE_CONFIG_FILE         path to JSON config\n"
            "  CLAUDE_CONFIG_CONTENT_DIR  override content dir\n"
            "  CLAUDE_CONFIG_TARGET       override target dir"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--config",
        type=Path,
        default=None,
        help=f"Path to config JSON (default: {ClaudeConfig.DEFAULT_CONFIG})",
    )
    p.add_argument(
        "--content",
        type=Path,
        default=None,
        help="Override content dir (takes precedence over config file).",
    )
    p.add_argument(
        "--target",
        type=Path,
        default=None,
        help="Override target dir (default: ~/.claude).",
    )
    p.add_argument("-V", "--version", action="version", version=f"claude-config {__version__}")

    sub = p.add_subparsers(dest="cmd", required=True, metavar="COMMAND")

    p_init = sub.add_parser("init", help="Create the content dir + git repo.")
    p_init.add_argument(
        "--no-examples", action="store_true", help="Skip seeding example CLAUDE.md."
    )
    p_init.add_argument(
        "--no-git", action="store_true", help="Skip 'git init' in the content dir."
    )
    p_init.add_argument(
        "--save", action="store_true", help="Persist the resolved config to JSON."
    )

    p_install = sub.add_parser("install", help="Symlink content into ~/.claude/.")
    p_install.add_argument("--dry-run", action="store_true")

    sub.add_parser("uninstall", help="Remove symlinks (content untouched).")

    p_sync = sub.add_parser("sync", help="Commit (and optionally push) content changes.")
    p_sync.add_argument("-m", "--message", default=None)
    p_sync.add_argument("--push", action="store_true")

    p_track = sub.add_parser("track", help="Move a real file into the content dir + symlink back.")
    p_track.add_argument("path", type=Path)

    sub.add_parser("status", help="Tracked + untracked + git state.")
    sub.add_parser("doctor", help="Verify symlink health.")
    return p


def _build(args: argparse.Namespace) -> ClaudeConfig:
    """Build a ClaudeConfig from --config and CLI overrides."""
    cfg = ClaudeConfig.from_config(args.config)
    if args.content:
        cfg = cfg.with_content_dir(args.content)
    if args.target:
        cfg = cfg.with_target(args.target)
    return cfg


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        cfg = _build(args)

        if args.cmd == "init":
            cfg.init(with_examples=not args.no_examples, init_git=not args.no_git)
            if args.save:
                cfg.save_config(args.config)
                print(f"saved config → {args.config or ClaudeConfig.DEFAULT_CONFIG}")
            print(f"content dir ready: {cfg.content_dir}")
            print("  next: claude-config install")
            return 0

        if args.cmd == "install":
            install_report = cfg.install(dry_run=args.dry_run)
            print(("[dry-run] " if args.dry_run else "") + install_report.summary())
            return 0

        if args.cmd == "uninstall":
            print(cfg.uninstall().summary())
            return 0

        if args.cmd == "sync":
            sync_report = cfg.sync(message=args.message, push=args.push)
            print(sync_report.summary())
            return 0 if not sync_report.push_error else 1

        if args.cmd == "track":
            cfg.track(args.path)
            print(f"tracked: {args.path}")
            return 0

        if args.cmd == "status":
            print(cfg.status().to_text())
            return 0

        if args.cmd == "doctor":
            doctor_report = cfg.doctor()
            print(doctor_report.summary())
            return 0 if doctor_report.healthy else 1

    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130

    return 0


if __name__ == "__main__":
    sys.exit(main())
