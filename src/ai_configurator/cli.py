"""Thin CLI wrapper around ClaudeConfig.

Subcommands:
    bootstrap     one-shot first-time setup (init + install + [sync --push] + doctor)
    init          create the content dir + git repo
    install       symlink content/claude/* into ~/.claude/*
    uninstall     remove the symlinks (content untouched)
    sync          git add + commit (+ optionally push) the content dir
    track         move a real file under ~/.claude/ into the content dir + symlink back
    status        tracked + untracked + git state
    doctor        verify symlink health
    cleanup       remove noise (.DS_Store, broken symlinks, orphan backups)
    list          grouped view of everything in the content dir
    view          print the contents of a tracked file
    validate      pre-flight environment check (used by bootstrap)
    decisions     list / show / apply bundled global-decision packs
    repair        heal a broken install (cleanup + rebuild symlinks)
    fetch         disk-to-disk download of a canonical / upstream text file
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .manager import ClaudeConfig, ConfigError, Prompter

# ---------------------------------------------------------------------------
# Prompting
# ---------------------------------------------------------------------------


def _tty_prompter(assume_yes: bool) -> Prompter:
    """Return a Prompter that reads from stdin, or always answers ``default``."""

    def prompt(question: str, default: bool) -> bool:
        if assume_yes or not sys.stdin.isatty():
            return default
        hint = "[Y/n]" if default else "[y/N]"
        try:
            ans = input(f"{question} {hint} ").strip().lower()
        except EOFError:
            return default
        if not ans:
            return default
        return ans in ("y", "yes")

    return prompt


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ai-configurator",
        description="Manage Claude Code's ~/.claude/ via symlinks from a content dir.",
        epilog=(
            "Common flow: `ai-configurator bootstrap` covers init + install + doctor in "
            "one shot.\n\n"
            "Env vars (override JSON config, overridden by CLI flags):\n"
            "  CLAUDE_CONFIG_FILE         path to JSON config\n"
            "  CLAUDE_CONFIG_CONTENT_DIR  override content dir\n"
            "  CLAUDE_CONFIG_TARGET       override target dir\n"
            "  CLAUDE_CONFIG_HOSTNAME     override hostname for host-overlay matching"
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
    p.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Skip prompts; assume the default answer to every question.",
    )
    p.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Print only essential output.",
    )
    p.add_argument(
        "-V", "--version",
        action="version",
        version=f"ai-configurator {__version__}",
    )

    sub = p.add_subparsers(dest="cmd", required=True, metavar="COMMAND")

    # bootstrap (new: one-shot wrapper)
    p_boot = sub.add_parser(
        "bootstrap",
        help="One-shot first-time setup (init + install + optional push + doctor).",
        description=(
            "Run init, install, optional sync --push, and doctor in sequence "
            "with validation, prompting, and clean error reporting. Idempotent: "
            "safe to re-run on a machine that's already set up."
        ),
    )
    p_boot.add_argument(
        "--push",
        action="store_true",
        help="After install, commit + push the content dir to its remote.",
    )
    p_boot.add_argument(
        "--remote",
        metavar="URL",
        default=None,
        help="Set `origin` to this URL before pushing (use with --push on a fresh setup).",
    )
    p_boot.add_argument(
        "--no-git",
        action="store_true",
        help="Skip `git init` in the content dir.",
    )
    p_boot.add_argument(
        "--with-settings",
        action="store_true",
        help="Also seed a starter settings.json template (skipped if file exists).",
    )
    p_boot.add_argument(
        "-m", "--message",
        default=None,
        help="Commit message for the sync step (when --push is used).",
    )
    p_boot.add_argument(
        "--no-decisions",
        action="store_true",
        help="Skip applying baked-in decision packs during init.",
    )
    p_boot.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the steps that would run; touch nothing.",
    )

    # init
    p_init = sub.add_parser("init", help="Create the content dir + git repo.")
    p_init.add_argument("--no-examples", action="store_true", help="Skip seeding CLAUDE.md.")
    p_init.add_argument("--no-git", action="store_true", help="Skip 'git init'.")
    p_init.add_argument(
        "--with-settings",
        action="store_true",
        help="Also seed a starter settings.json template.",
    )
    p_init.add_argument(
        "--no-decisions",
        action="store_true",
        help="Skip applying baked-in decision packs.",
    )
    p_init.add_argument(
        "--save", action="store_true", help="Persist resolved config to JSON."
    )

    # install
    p_install = sub.add_parser("install", help="Symlink content into ~/.claude/.")
    p_install.add_argument("--dry-run", action="store_true")

    # uninstall
    p_un = sub.add_parser("uninstall", help="Remove symlinks (content untouched).")
    p_un.add_argument(
        "--no-restore",
        action="store_true",
        help="Don't restore *.before-claude-config backups when removing symlinks.",
    )

    # sync
    p_sync = sub.add_parser("sync", help="Commit (and optionally push) content changes.")
    p_sync.add_argument("-m", "--message", default=None)
    p_sync.add_argument("--push", action="store_true")

    # track
    p_track = sub.add_parser("track", help="Move a real path into the content dir + symlink back.")
    p_track.add_argument("path", type=Path)

    # status / doctor / validate
    sub.add_parser("status", help="Tracked + untracked + git state.")
    sub.add_parser("doctor", help="Verify symlink health.")
    sub.add_parser("validate", help="Pre-flight environment check.")

    # cleanup
    p_clean = sub.add_parser(
        "cleanup",
        help="Remove .DS_Store, broken symlinks, orphan backups.",
    )
    p_clean.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete the listed paths (default is dry-run).",
    )
    p_clean.add_argument(
        "--include-ephemeral",
        action="store_true",
        help="Also clear paste-cache, file-history, todos, etc. under target.",
    )

    # list
    sub.add_parser("list", help="Grouped view of content_dir contents.")

    # view
    p_view = sub.add_parser("view", help="Print the contents of a tracked file.")
    p_view.add_argument("relpath", help="Path relative to content_dir/claude/.")
    p_view.add_argument(
        "--with-line-numbers",
        action="store_true",
        help="Prefix each line with its line number (1-indexed).",
    )

    # decisions
    p_dec = sub.add_parser(
        "decisions", help="List / show / apply bundled global-decision packs."
    )
    dec_sub = p_dec.add_subparsers(dest="decisions_cmd", required=True, metavar="ACTION")
    dec_sub.add_parser("list", help="Show all bundled packs.")
    p_dec_show = dec_sub.add_parser("show", help="Print a pack's manifest + README.")
    p_dec_show.add_argument("name")
    p_dec_apply = dec_sub.add_parser(
        "apply", help="Copy a pack's files into the content dir."
    )
    p_dec_apply.add_argument("name")
    p_dec_apply.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files (default refuses).",
    )
    p_dec_apply.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be written without writing.",
    )

    # repair
    p_rep = sub.add_parser(
        "repair", help="Heal a broken install (cleanup + rebuild symlinks)."
    )
    p_rep.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without touching anything.",
    )

    # reconcile: re-apply auto-apply packs missing since last upgrade
    p_recon = sub.add_parser(
        "reconcile",
        help="Re-apply auto-apply decision packs (transparently on every command).",
        description=(
            "Compares the installed ai-configurator version against the "
            "last_applied_version stored in your JSON config. When they "
            "differ, applies every pack in DEFAULT_DECISIONS_ON_INIT "
            "non-clobberingly. This usually runs transparently on every "
            "command: invoke explicitly to force the check or to "
            "re-apply with --force."
        ),
    )
    p_recon.add_argument(
        "--force",
        action="store_true",
        help="Re-apply auto-apply packs even when versions match.",
    )

    # fetch: disk-to-disk download
    p_fetch = sub.add_parser(
        "fetch",
        help="Disk-to-disk download of a canonical / upstream text file.",
        description=(
            "Streams URL -> disk via urllib (stdlib only). Body bytes never "
            "enter the response stream. Atomic write, idempotent, HTTPS-only "
            "unless --allow-http. Use this instead of letting the model emit "
            "a canonical file's content inline (which can be content-filter "
            "blocked)."
        ),
    )
    p_fetch.add_argument("url", help="Source URL (https:// by default).")
    p_fetch.add_argument("dest", type=Path, help="Destination file path.")
    p_fetch.add_argument(
        "--expect-sha256",
        metavar="HEX",
        default=None,
        help="Abort if the downloaded sha256 doesn't match.",
    )
    p_fetch.add_argument(
        "--max-bytes",
        type=int,
        default=1024 * 1024,
        help="Refuse downloads larger than N bytes (default: 1048576).",
    )
    p_fetch.add_argument(
        "--allow-http",
        action="store_true",
        help="Permit http:// URLs (default: https only).",
    )
    p_fetch.add_argument(
        "--allow-binary",
        action="store_true",
        help="Skip UTF-8 validation (for non-text downloads).",
    )
    p_fetch.add_argument(
        "--no-first-line",
        action="store_true",
        help="Omit the file's first line from the report (extra strict).",
    )

    return p


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build(args: argparse.Namespace) -> ClaudeConfig:
    """Build a ClaudeConfig from --config and CLI overrides."""
    cfg = ClaudeConfig.from_config(args.config)
    if args.content:
        cfg = cfg.with_content_dir(args.content)
    if args.target:
        cfg = cfg.with_target(args.target)
    return cfg


def _print(msg: str, quiet: bool) -> None:
    if not quiet:
        print(msg)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        cfg = _build(args)
        prompter = _tty_prompter(assume_yes=args.yes)

        # Auto-reconcile on upgrade. No-op when the user is up-to-date.
        # When a newer ai-configurator added packs to
        # DEFAULT_DECISIONS_ON_INIT, they apply transparently here.
        rec = cfg.reconcile_if_enabled()
        if rec and rec.upgrade_happened and rec.packs_applied and not args.quiet:
            sys.stderr.write(
                f"reconciled {rec.from_version} -> {rec.to_version}: "
                f"applied {', '.join(rec.packs_applied)}\n"
            )

        if args.cmd == "bootstrap":
            boot_report = cfg.bootstrap(
                push=args.push,
                remote_url=args.remote,
                with_settings=args.with_settings,
                init_git=not args.no_git,
                commit_message=args.message,
                dry_run=args.dry_run,
                prompt=prompter,
                apply_decisions=() if args.no_decisions else None,
            )
            print(boot_report.summary())
            if boot_report.ok:
                _print("\nnext steps:", args.quiet)
                _print("  - edit ~/.claude/CLAUDE.md to add your preferences", args.quiet)
                _print("  - `ai-configurator status` shows what's tracked", args.quiet)
                _print("  - `ai-configurator sync` commits changes", args.quiet)
            return 0 if boot_report.ok else 1

        if args.cmd == "init":
            cfg.init(
                with_examples=not args.no_examples,
                init_git=not args.no_git,
                with_settings=args.with_settings,
                apply_decisions=() if args.no_decisions else None,
            )
            if args.save:
                cfg.save_config(args.config)
                _print(
                    f"saved config -> {args.config or ClaudeConfig.DEFAULT_CONFIG}",
                    args.quiet,
                )
            _print(f"content dir ready: {cfg.content_dir}", args.quiet)
            _print("  next: ai-configurator install", args.quiet)
            return 0

        if args.cmd == "install":
            install_report = cfg.install(dry_run=args.dry_run)
            print(("[dry-run] " if args.dry_run else "") + install_report.summary())
            return 0

        if args.cmd == "uninstall":
            r = cfg.uninstall(restore_backups=not args.no_restore)
            print(r.summary())
            return 0

        if args.cmd == "sync":
            sync_report = cfg.sync(message=args.message, push=args.push)
            print(sync_report.summary())
            return 0 if not sync_report.push_error else 1

        if args.cmd == "track":
            cfg.track(args.path)
            _print(f"tracked: {args.path}", args.quiet)
            return 0

        if args.cmd == "status":
            print(cfg.status().to_text())
            return 0

        if args.cmd == "doctor":
            doctor_report = cfg.doctor()
            print(doctor_report.summary())
            return 0 if doctor_report.healthy else 1

        if args.cmd == "validate":
            val_report = cfg.validate()
            print(val_report.summary())
            return 0 if val_report.ok else 1

        if args.cmd == "cleanup":
            clean_report = cfg.cleanup(
                dry_run=not args.apply,
                include_ephemeral=args.include_ephemeral,
            )
            print(clean_report.summary())
            if not args.quiet and clean_report.total:
                _print_cleanup_detail(clean_report)
            if clean_report.dry_run and clean_report.total:
                _print(
                    "\nre-run with `--apply` to actually delete these paths",
                    args.quiet,
                )
            return 0

        if args.cmd == "list":
            print(cfg.list_contents().to_text())
            return 0

        if args.cmd == "decisions":
            if args.decisions_cmd == "list":
                print(cfg.decisions_list().summary())
                return 0
            if args.decisions_cmd == "show":
                pack = cfg.decisions_show(args.name)
                print(pack.summary())
                if pack.readme:
                    print()
                    print(pack.readme.rstrip())
                return 0
            if args.decisions_cmd == "apply":
                apply_report = cfg.decisions_apply(
                    args.name, force=args.force, dry_run=args.dry_run
                )
                print(apply_report.summary())
                if not args.quiet:
                    if apply_report.written:
                        print("  written:")
                        for f in apply_report.written:
                            print(f"    + {f}")
                    if apply_report.overwritten:
                        print("  overwritten:")
                        for f in apply_report.overwritten:
                            print(f"    ~ {f}")
                    if apply_report.skipped:
                        print("  skipped (already present; --force to overwrite):")
                        for f in apply_report.skipped:
                            print(f"    = {f}")
                return 0

        if args.cmd == "reconcile":
            recon_report = cfg.reconcile(force_reapply=args.force)
            print(recon_report.summary())
            if recon_report.packs_applied and not args.quiet:
                for p in recon_report.packs_applied:
                    print(f"  applied: {p}")
            if recon_report.packs_failed:
                for name, err in recon_report.packs_failed:
                    print(f"  failed: {name} ({err})", file=sys.stderr)
            return 0 if not recon_report.packs_failed else 1

        if args.cmd == "repair":
            repair_report = cfg.repair(dry_run=args.dry_run)
            print(repair_report.summary())
            if not args.quiet and repair_report.actions:
                for a in repair_report.actions:
                    suffix = f" ({a.detail})" if a.detail else ""
                    print(f"  {a.kind}: {a.target}{suffix}")
            return 0

        if args.cmd == "fetch":
            fetch_report = cfg.fetch_canonical(
                args.url,
                args.dest,
                expect_sha256=args.expect_sha256,
                max_bytes=args.max_bytes,
                allow_http=args.allow_http,
                allow_binary=args.allow_binary,
                include_first_line=not args.no_first_line,
            )
            print(fetch_report.summary())
            return 0

        if args.cmd == "view":
            try:
                text = cfg.view(args.relpath)
            except ConfigError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 2
            if args.with_line_numbers:
                width = len(str(text.count("\n") + 1))
                for i, line in enumerate(text.splitlines(), 1):
                    print(f"{i:>{width}}  {line}")
            else:
                sys.stdout.write(text)
                if not text.endswith("\n"):
                    sys.stdout.write("\n")
            return 0

    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130

    return 0


def _print_cleanup_detail(report: object) -> None:
    """Print per-category paths for the cleanup report (helper, not on the class)."""
    from .manager import CleanupReport

    if not isinstance(report, CleanupReport):
        return
    if report.ds_store_removed:
        print("  .DS_Store / swap files:")
        for p in report.ds_store_removed[:20]:
            print(f"    {p}")
        if len(report.ds_store_removed) > 20:
            print(f"    ... ({len(report.ds_store_removed) - 20} more)")
    if report.broken_symlinks_removed:
        print("  broken symlinks:")
        for p in report.broken_symlinks_removed[:20]:
            print(f"    {p}")
    if report.orphan_backups:
        print("  orphan backups:")
        for p in report.orphan_backups[:20]:
            print(f"    {p}")
    if report.ephemeral_paths_cleaned:
        print(f"  ephemeral paths ({len(report.ephemeral_paths_cleaned)} total):")
        for p in report.ephemeral_paths_cleaned[:10]:
            print(f"    {p}")
        if len(report.ephemeral_paths_cleaned) > 10:
            print(f"    ... ({len(report.ephemeral_paths_cleaned) - 10} more)")


if __name__ == "__main__":
    sys.exit(main())
