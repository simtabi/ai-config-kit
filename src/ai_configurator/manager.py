"""One class to manage Claude Code's ~/.claude/ via symlinks from a content dir.

Design:
- Single class (ClaudeConfig) with a fluent API.
- JSON config at ~/.config/claude-config/config.json by default; every field
  optional, defaults applied for anything missing. ``save_config`` merges
  with the file on disk rather than overwriting (forward-compat for fields
  this version doesn't know).
- Symlinks files from <content_dir>/claude/* into <target>/* (default
  ~/.claude). Directory symlinks for "auto-grow" subdirs (memory/, commands/,
  agents/, skills/, hooks/, prompts/) so new files inside auto-propagate
  without re-running install.
- Host-overlay pattern for per-machine files: <content>/claude/hosts/<host>/X
  installs as <target>/X on that host; never on others.
- Defence in depth against secrets: refuses to track files matching
  configured patterns. Pattern set covers credentials, keys, tokens, env
  files, SSH keys, package-registry rc files, password DBs.
- Operations on the CONTENT dir's git repo (not the tool's repo) — personal
  content stays isolated.
- Cross-device-safe ``track`` via ``shutil.move``; ``Path.is_relative_to`` for
  path containment; ``importlib.metadata`` for version.
"""

from __future__ import annotations

import contextlib
import fnmatch
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any, ClassVar, Protocol


class Prompter(Protocol):
    """Confirmation prompter contract used by ``ClaudeConfig.bootstrap``.

    A callable that returns the user's yes/no answer. Accepts the question
    plus a default answer to return when the user gives no input.
    """

    def __call__(self, question: str, default: bool) -> bool: ...

# ---------------------------------------------------------------------------
# Errors and result types
# ---------------------------------------------------------------------------


class ConfigError(Exception):
    """Raised on configuration parse, validation, or environment failure."""


@dataclass(frozen=True)
class InstallReport:
    """Outcome of ``.install()``."""

    links_created: int = 0
    dir_links_created: int = 0
    already_correct: int = 0
    real_files_backed_up: int = 0
    skipped_via_dir_symlink: int = 0
    host_overlays_linked: int = 0
    secrets_skipped: int = 0

    def summary(self) -> str:
        parts = [
            f"installed {self.links_created} link(s)",
            f"{self.dir_links_created} dir link(s)",
            f"{self.already_correct} already-correct",
            f"{self.real_files_backed_up} backed up",
            f"{self.skipped_via_dir_symlink} reachable via dir symlink",
        ]
        if self.host_overlays_linked:
            parts.append(f"{self.host_overlays_linked} host overlay(s)")
        if self.secrets_skipped:
            parts.append(f"{self.secrets_skipped} secret(s) refused")
        return ", ".join(parts)


@dataclass(frozen=True)
class UninstallReport:
    removed: int = 0
    backups_restored: int = 0

    def summary(self) -> str:
        parts = [f"removed {self.removed} symlink(s)"]
        if self.backups_restored:
            parts.append(f"restored {self.backups_restored} pre-install backup(s)")
        parts.append("content untouched")
        return "; ".join(parts)


@dataclass(frozen=True)
class DoctorReport:
    issues: list[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return not self.issues

    def summary(self) -> str:
        if self.healthy:
            return "all symlinks healthy"
        return f"{len(self.issues)} issue(s):\n  " + "\n  ".join(self.issues)


@dataclass(frozen=True)
class StatusReport:
    content_dir: Path
    target_base: Path
    hostname: str = ""
    tracked_files: list[str] = field(default_factory=list)
    untracked_candidates: list[str] = field(default_factory=list)
    git_clean: bool = True
    git_summary: str = ""

    def to_text(self, max_listed: int = 30) -> str:
        lines: list[str] = [
            f"Content dir:  {self.content_dir}",
            f"Target base:  {self.target_base}",
            f"Hostname:     {self.hostname}",
            f"Tracked files: {len(self.tracked_files)}",
        ]
        lines.extend(f"  {p}" for p in self.tracked_files[:max_listed])
        if len(self.tracked_files) > max_listed:
            lines.append(f"  ... ({len(self.tracked_files) - max_listed} more)")
        lines.append("")
        lines.append(f"Untracked candidates in {self.target_base}:")
        if self.untracked_candidates:
            lines.extend(f"  {p}" for p in self.untracked_candidates[:max_listed])
            if len(self.untracked_candidates) > max_listed:
                extra = len(self.untracked_candidates) - max_listed
                lines.append(f"  ... ({extra} more)")
        else:
            lines.append("  (none)")
        lines.append("")
        lines.append(f"Git: {'clean' if self.git_clean else 'dirty'}")
        if self.git_summary:
            lines.append(self.git_summary)
        return "\n".join(lines)


@dataclass(frozen=True)
class SyncReport:
    committed: bool
    commit_sha: str | None = None
    commit_message: str | None = None
    pushed: bool = False
    push_error: str | None = None
    branch: str | None = None
    remote: str | None = None

    def summary(self) -> str:
        parts: list[str] = []
        if self.committed:
            short = (self.commit_sha or "")[:8]
            subject = (self.commit_message or "").splitlines()[0] if self.commit_message else ""
            parts.append(f"committed {short}: {subject}")
        else:
            parts.append("nothing to commit")
        if self.pushed:
            ref = f"{self.remote}/{self.branch}" if self.remote and self.branch else "remote"
            parts.append(f"pushed to {ref}")
        elif self.push_error:
            parts.append(f"push failed: {self.push_error}")
        return "; ".join(parts)


@dataclass(frozen=True)
class CleanupReport:
    """Outcome of ``.cleanup()``."""

    ds_store_removed: list[Path] = field(default_factory=list)
    broken_symlinks_removed: list[Path] = field(default_factory=list)
    orphan_backups: list[Path] = field(default_factory=list)
    ephemeral_paths_cleaned: list[Path] = field(default_factory=list)
    dry_run: bool = True

    @property
    def total(self) -> int:
        return (
            len(self.ds_store_removed)
            + len(self.broken_symlinks_removed)
            + len(self.orphan_backups)
            + len(self.ephemeral_paths_cleaned)
        )

    def summary(self) -> str:
        prefix = "[dry-run] " if self.dry_run else ""
        parts = [
            f"{len(self.ds_store_removed)} .DS_Store",
            f"{len(self.broken_symlinks_removed)} broken symlink(s)",
            f"{len(self.orphan_backups)} orphan backup(s)",
        ]
        if self.ephemeral_paths_cleaned:
            parts.append(f"{len(self.ephemeral_paths_cleaned)} ephemeral path(s)")
        verb = "would remove" if self.dry_run else "removed"
        return f"{prefix}{verb} " + ", ".join(parts)


@dataclass(frozen=True)
class BootstrapStep:
    name: str
    ok: bool
    detail: str = ""
    skipped: bool = False


@dataclass(frozen=True)
class BootstrapReport:
    """Outcome of ``.bootstrap()``."""

    steps: list[BootstrapStep] = field(default_factory=list)
    dry_run: bool = False

    @property
    def ok(self) -> bool:
        return all(s.ok or s.skipped for s in self.steps)

    def summary(self) -> str:
        lines: list[str] = []
        for s in self.steps:
            if s.skipped:
                marker = "[skip]"
            elif s.ok:
                marker = "[ ok ]"
            else:
                marker = "[FAIL]"
            line = f"  {marker} {s.name}"
            if s.detail:
                line += f": {s.detail}"
            lines.append(line)
        prefix = "[dry-run] " if self.dry_run else ""
        status = "complete" if self.ok else "FAILED"
        return f"{prefix}bootstrap {status}\n" + "\n".join(lines)


@dataclass(frozen=True)
class ValidationReport:
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    def summary(self) -> str:
        lines: list[str] = []
        if not self.issues and not self.warnings:
            return "environment ok"
        if self.issues:
            lines.append(f"{len(self.issues)} blocker(s):")
            lines.extend(f"  - {i}" for i in self.issues)
        if self.warnings:
            lines.append(f"{len(self.warnings)} warning(s):")
            lines.extend(f"  - {w}" for w in self.warnings)
        return "\n".join(lines)


@dataclass(frozen=True)
class FetchReport:
    """Outcome of ``.fetch_canonical()``.

    Designed to be safe to print: contains metadata only — never body
    content beyond the first line (which for canonical files is a
    title; see ``include_first_line`` to suppress).
    """

    path: Path
    bytes: int
    lines: int
    sha256: str
    status: str  # "created" | "updated" | "unchanged"
    first_line: str = ""

    def summary(self) -> str:
        parts = [
            f"path={self.path}",
            f"bytes={self.bytes}",
            f"lines={self.lines}",
            f"sha256={self.sha256}",
            f"status={self.status}",
        ]
        if self.first_line:
            parts.append(f"first_line={self.first_line}")
        return "\n".join(parts)


@dataclass(frozen=True)
class ReconcileReport:
    """Outcome of ``.reconcile()`` — auto-apply-on-upgrade tracker."""

    from_version: str
    to_version: str
    upgrade_happened: bool
    packs_applied: list[str] = field(default_factory=list)
    packs_failed: list[tuple[str, str]] = field(default_factory=list)

    def summary(self) -> str:
        if not self.upgrade_happened:
            return f"already at {self.to_version} — no reconcile needed"
        parts = [f"reconciled {self.from_version} -> {self.to_version}"]
        if self.packs_applied:
            parts.append(f"applied {len(self.packs_applied)} pack(s)")
        if self.packs_failed:
            parts.append(f"{len(self.packs_failed)} pack(s) failed")
        return "; ".join(parts)


@dataclass(frozen=True)
class DecisionFile:
    """A single file inside a bundled decision pack."""

    src: str
    dest: str
    # Octal string ("0755") set on dest after copy. None leaves the mode at
    # umask default. Only the low 12 bits (perms + sticky) are honored.
    mode: str | None = None


@dataclass(frozen=True)
class DecisionPack:
    name: str
    description: str
    version: str
    files: list[DecisionFile] = field(default_factory=list)
    readme: str = ""

    def summary(self) -> str:
        files = "\n".join(f"    {f.dest}" for f in self.files)
        return (
            f"{self.name} ({self.version})\n"
            f"  {self.description}\n"
            f"  files ({len(self.files)}):\n{files}"
        )


@dataclass(frozen=True)
class DecisionsListReport:
    packs: list[DecisionPack] = field(default_factory=list)

    def summary(self) -> str:
        if not self.packs:
            return "no bundled decision packs"
        lines = [f"{len(self.packs)} bundled pack(s):"]
        for p in self.packs:
            lines.append(f"  {p.name:30s} {p.description}")
        return "\n".join(lines)


@dataclass(frozen=True)
class DecisionsApplyReport:
    pack: str
    written: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    overwritten: list[str] = field(default_factory=list)
    dry_run: bool = False

    @property
    def total(self) -> int:
        return len(self.written) + len(self.overwritten) + len(self.skipped)

    def summary(self) -> str:
        prefix = "[dry-run] " if self.dry_run else ""
        parts = [f"applied {self.pack}"]
        if self.written:
            parts.append(f"{len(self.written)} new")
        if self.overwritten:
            parts.append(f"{len(self.overwritten)} overwritten")
        if self.skipped:
            parts.append(f"{len(self.skipped)} skipped (already present)")
        return prefix + "; ".join(parts)


@dataclass(frozen=True)
class RepairAction:
    kind: str
    target: Path
    detail: str = ""


@dataclass(frozen=True)
class RepairReport:
    """Outcome of ``.repair()``."""

    actions: list[RepairAction] = field(default_factory=list)
    install_report: InstallReport | None = None
    cleanup_report: CleanupReport | None = None
    dry_run: bool = False

    def summary(self) -> str:
        prefix = "[dry-run] " if self.dry_run else ""
        kinds: dict[str, int] = {}
        for a in self.actions:
            kinds[a.kind] = kinds.get(a.kind, 0) + 1
        parts: list[str] = []
        for kind, count in sorted(kinds.items()):
            parts.append(f"{count} {kind}")
        verb = "would perform" if self.dry_run else "performed"
        body = ", ".join(parts) if parts else "no actions"
        return f"{prefix}repair {verb}: {body}"


@dataclass(frozen=True)
class ListingGroup:
    label: str
    paths: list[str] = field(default_factory=list)
    total_bytes: int = 0


@dataclass(frozen=True)
class ListingReport:
    """Grouped, human-readable view of content_dir."""

    content_dir: Path
    target_base: Path
    hostname: str = ""
    groups: list[ListingGroup] = field(default_factory=list)

    def to_text(self, max_per_group: int = 20) -> str:
        lines: list[str] = [
            f"Content dir:  {self.content_dir}",
            f"Target base:  {self.target_base}",
            f"Hostname:     {self.hostname}",
            "",
        ]
        any_content = False
        for group in self.groups:
            count = len(group.paths)
            if not count:
                continue
            any_content = True
            size = _format_size(group.total_bytes)
            lines.append(f"{group.label}  [{count} file(s), {size}]")
            lines.extend(f"  {p}" for p in group.paths[:max_per_group])
            if count > max_per_group:
                lines.append(f"  ... ({count - max_per_group} more)")
            lines.append("")
        if not any_content:
            lines.append("(content dir is empty — try `ai-configurator init`)")
        return "\n".join(lines).rstrip()


def _format_size(n: int) -> str:
    """Human-readable byte size, 1 decimal for KB and above."""
    if n < 1024:
        return f"{n} B"
    if n < 1024**2:
        return f"{n / 1024:.1f} KB"
    if n < 1024**3:
        return f"{n / 1024**2:.1f} MB"
    return f"{n / 1024**3:.1f} GB"


# ---------------------------------------------------------------------------
# Hostname (overridable for tests)
# ---------------------------------------------------------------------------


def _current_hostname() -> str:
    """Return the local hostname, lowercased, without domain suffix."""
    env = os.environ.get("CLAUDE_CONFIG_HOSTNAME")
    if env:
        return env.lower()
    return socket.gethostname().split(".")[0].lower()


def _package_version() -> str:
    """Currently-installed ``ai-configurator`` version, or ``0.0.0`` if unknown."""
    try:
        from importlib.metadata import version as _v

        return _v("ai-configurator")
    except Exception:
        return "0.0.0"


def _user_agent() -> str:
    """User-Agent for the ``fetch_canonical`` HTTP client."""
    return f"ai-configurator/{_package_version()}"


# ---------------------------------------------------------------------------
# The class
# ---------------------------------------------------------------------------


class ClaudeConfig:
    """Manage Claude Code's ~/.claude/ via symlinks from a content directory.

    Construction::

        cfg = ClaudeConfig()                              # defaults
        cfg = ClaudeConfig(content_dir="/path/to/content")
        cfg = ClaudeConfig.from_config()                  # reads config.json
        cfg = (
            ClaudeConfig()
            .with_content_dir("/path/to/content")
            .with_target("/home/x/.claude")
        )

    Operations (chainable setters return self; data-producing operations
    return a frozen ``Report`` dataclass)::

        cfg.init().install().doctor()
        cfg.sync(message="updated rules", push=True)
        cfg.track("/home/x/.claude/skills/foo.md")
        print(cfg.status().to_text())
        print(cfg.list_contents().to_text())
        print(cfg.cleanup(dry_run=True).summary())
        print(cfg.view("CLAUDE.md"))
    """

    # ---- defaults -----------------------------------------------------

    DEFAULT_TARGET: Path = Path.home() / ".claude"
    DEFAULT_CONFIG: Path = Path(
        os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    ) / "ai-configurator" / "config.json"
    DEFAULT_CONTENT: Path = Path(
        os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    ) / "ai-configurator" / "content"

    DEFAULT_SECRET_PATTERNS: tuple[str, ...] = (
        ".credentials.json",
        ".credentials.json.*",
        "*.secret",
        "*.key",
        "*.pem",
        "*.p12",
        "*.pfx",
        "*.kdbx",
        "*.token",
        "*.netrc",
        ".netrc",
        ".npmrc",
        ".pypirc",
        ".env",
        ".env.*",
        "id_rsa",
        "id_rsa.*",
        "id_ed25519",
        "id_ed25519.*",
        "id_ecdsa",
        "id_ecdsa.*",
    )
    DEFAULT_IGNORE_PATTERNS: tuple[str, ...] = (
        ".DS_Store",
        "Thumbs.db",
        "*.swp",
        "*.swo",
        "*~",
        "*.before-claude-config",
    )

    # Subdirectories inside <content>/claude/ symlinked at directory level
    # so new files inside them auto-appear in ~/.claude/ without re-running
    # install. These cover every "auto-grow" config dir Claude Code uses.
    DEFAULT_DIR_SYMLINK_NAMES: tuple[str, ...] = (
        "memory",
        "commands",
        "agents",
        "skills",
        "hooks",
        "prompts",
    )

    # Plugin sub-files that are config (not the marketplaces/ cache).
    DEFAULT_PLUGIN_CONFIG_FILES: tuple[str, ...] = (
        "blocklist.json",
        "known_marketplaces.json",
    )

    # Sentinel dir for per-host overlay files. Layout:
    #     <content>/claude/hosts/<hostname>/<file>
    # installs at <target>/<file> on the matching host only.
    HOST_OVERLAY_DIR: str = "hosts"

    # Directories under <target> normally written by the harness; excluded
    # from candidate listings and never auto-tracked.
    RUNTIME_DIRS: frozenset[str] = frozenset({
        "sessions", "cache", "paste-cache", "shell-snapshots",
        "backups", "tasks", "todos", "telemetry", "statsig", "ide",
        "file-history", "downloads", "session-env", "plans",
    })

    # Single top-level files normally written by the harness.
    RUNTIME_FILES: frozenset[str] = frozenset({"history.jsonl", ".last-cleanup"})

    # Directory names that contain SOME config + SOME runtime children.
    # ``plugins/`` is the canonical case: blocklist.json + known_marketplaces.json
    # are config; marketplaces/ is a cloned-repo cache.
    MIXED_DIRS: frozenset[str] = frozenset({"plugins"})

    # Children inside MIXED_DIRS that are ephemeral (never tracked).
    MIXED_RUNTIME_CHILDREN: ClassVar[dict[str, frozenset[str]]] = {
        "plugins": frozenset({"marketplaces"}),
    }

    # Top-level config files always worth tracking (used by ``list`` grouping).
    KNOWN_CONFIG_FILES: tuple[str, ...] = ("CLAUDE.md", "settings.json")

    # Decision packs auto-applied by ``init``. Each pack's files land in
    # src_dir/ without overwriting anything that's already there. Existing
    # users running ``init`` against an established content dir get the
    # baked-in defaults without losing their custom CLAUDE.md.
    DEFAULT_DECISIONS_ON_INIT: tuple[str, ...] = (
        "script-generation-pattern",
        "fetch-canonical-pattern",
        "session-protocol",
        "docker-multiarch",
        "docker-env-interpolation",
        "claude-best-practices",
        "humanistic-style",
        "docs-structure",
        "mcp-best-practices",
        "safety-net-commits",
        "vendor-portability",
        "polling-discipline",
    )

    # Minimum supported Python — kept in sync with ``pyproject.toml``.
    MIN_PYTHON: ClassVar[tuple[int, int]] = (3, 10)

    # AI coding tools the configurator can target. Default selection is
    # claude-code; multi-vendor mode adds more during bootstrap / init
    # via the user's choice. Each vendor maps to a real install path
    # (added per-vendor in future phases). Vendors not yet wired to a
    # symlink target are accepted into config but flagged as "planned"
    # by ``vendor_status()``.
    SUPPORTED_VENDORS: ClassVar[tuple[str, ...]] = (
        "claude-code",     # Anthropic Claude Code CLI — fully supported
        "claude",          # Claude.ai web/desktop — partial (CLAUDE.md sharing)
        "codex",           # OpenAI Codex CLI — planned
        "cursor",          # Cursor IDE — planned (.cursorrules)
        "cline",           # Cline (VS Code extension) — planned
        "aider",           # Aider CLI — planned (AGENTS.md)
        "windsurf",        # Windsurf IDE — planned (.windsurfrules)
        "copilot",         # GitHub Copilot — planned (.github/copilot-instructions.md)
    )
    DEFAULT_VENDORS: ClassVar[tuple[str, ...]] = ("claude-code",)
    VENDOR_STATUS: ClassVar[dict[str, str]] = {
        "claude-code": "current",
        "claude": "partial",
        "codex": "planned",
        "cursor": "planned",
        "cline": "planned",
        "aider": "planned",
        "windsurf": "planned",
        "copilot": "planned",
    }

    # Environment variables consulted between an explicit argument and the
    # JSON config / class default.
    ENV_CONTENT_DIR: str = "CLAUDE_CONFIG_CONTENT_DIR"
    ENV_TARGET_BASE: str = "CLAUDE_CONFIG_TARGET"
    ENV_CONFIG_FILE: str = "CLAUDE_CONFIG_FILE"

    # ---- construction -------------------------------------------------
    #
    # Precedence (highest first):
    #   1. Explicit argument to __init__ / fluent setter
    #   2. Environment variable
    #   3. JSON config (via from_config())
    #   4. Class default

    def __init__(
        self,
        content_dir: Path | str | None = None,
        target_base: Path | str | None = None,
        secret_patterns: Iterable[str] | None = None,
        ignore_patterns: Iterable[str] | None = None,
        dir_symlink_names: Iterable[str] | None = None,
        include_sessions: bool = False,
        include_history: bool = False,
        relative_symlinks: bool = True,
        auto_reconcile: bool = True,
        vendors: Iterable[str] | None = None,
    ) -> None:
        if content_dir is None:
            content_dir = os.environ.get(self.ENV_CONTENT_DIR)
        if target_base is None:
            target_base = os.environ.get(self.ENV_TARGET_BASE)

        self._content_dir: Path = (
            Path(content_dir).expanduser().resolve() if content_dir else self.DEFAULT_CONTENT
        )
        self._target_base: Path = (
            Path(target_base).expanduser().resolve() if target_base else self.DEFAULT_TARGET
        )
        self._secrets: tuple[str, ...] = tuple(
            secret_patterns if secret_patterns is not None else self.DEFAULT_SECRET_PATTERNS
        )
        self._ignores: tuple[str, ...] = tuple(
            ignore_patterns if ignore_patterns is not None else self.DEFAULT_IGNORE_PATTERNS
        )
        base_dirs = tuple(
            dir_symlink_names if dir_symlink_names is not None else self.DEFAULT_DIR_SYMLINK_NAMES
        )
        if include_sessions and "sessions" not in base_dirs:
            base_dirs = (*base_dirs, "sessions")
        self._dir_syms: tuple[str, ...] = base_dirs
        self._include_sessions: bool = include_sessions
        self._include_history: bool = include_history
        self._relative_symlinks: bool = relative_symlinks
        self._auto_reconcile: bool = auto_reconcile

        # Vendor list — which AI coding tools this configurator should
        # eventually target. Default is just claude-code (the fully-supported
        # path). Unknown vendors are accepted but flagged via vendor_status().
        if vendors is None:
            vendors = self.DEFAULT_VENDORS
        self._vendors: tuple[str, ...] = tuple(vendors)

        # Track which config file (if any) this instance was built from so
        # mutating operations like track() can persist their state changes.
        self._loaded_config_path: Path | None = None

        # Dedup warning state so a noisy condition fires once per run, not
        # once per matching file.
        self._warned_keys: set[str] = set()

    def __repr__(self) -> str:
        return (
            f"ClaudeConfig(content_dir={self._content_dir!r}, "
            f"target_base={self._target_base!r}, "
            f"include_sessions={self._include_sessions}, "
            f"include_history={self._include_history})"
        )

    @classmethod
    def from_config(cls, config_path: Path | str | None = None) -> ClaudeConfig:
        """Load config from JSON. Falls back to defaults when file is absent.

        Env-var precedence: ``CLAUDE_CONFIG_FILE`` overrides the path
        argument; ``CLAUDE_CONFIG_CONTENT_DIR`` / ``CLAUDE_CONFIG_TARGET``
        override the JSON values for those fields.
        """
        env_path = os.environ.get(cls.ENV_CONFIG_FILE)
        path = (
            Path(env_path).expanduser()
            if env_path
            else (Path(config_path).expanduser() if config_path else cls.DEFAULT_CONFIG)
        )

        data: dict[str, Any] = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                raise ConfigError(
                    f"Invalid JSON in {path}: line {e.lineno}: {e.msg}"
                ) from e

        content = os.environ.get(cls.ENV_CONTENT_DIR) or data.get("content_dir")
        target = os.environ.get(cls.ENV_TARGET_BASE) or data.get("target_base")

        cfg = cls(
            content_dir=content,
            target_base=target,
            secret_patterns=data.get("secret_patterns"),
            ignore_patterns=data.get("ignore_patterns"),
            dir_symlink_names=data.get("dir_symlink_names"),
            include_sessions=bool(data.get("include_sessions", False)),
            include_history=bool(data.get("include_history", False)),
            relative_symlinks=bool(data.get("relative_symlinks", True)),
            auto_reconcile=bool(data.get("auto_reconcile", True)),
            vendors=data.get("vendors") or None,
        )
        cfg._loaded_config_path = path if path.exists() else None
        return cfg

    # ---- fluent setters -----------------------------------------------

    def with_content_dir(self, path: Path | str) -> ClaudeConfig:
        self._content_dir = Path(path).expanduser().resolve()
        return self

    def with_target(self, path: Path | str) -> ClaudeConfig:
        self._target_base = Path(path).expanduser().resolve()
        return self

    def with_secret_patterns(self, patterns: Iterable[str]) -> ClaudeConfig:
        self._secrets = tuple(patterns)
        return self

    def with_ignore_patterns(self, patterns: Iterable[str]) -> ClaudeConfig:
        self._ignores = tuple(patterns)
        return self

    def with_dir_symlinks(self, names: Iterable[str]) -> ClaudeConfig:
        self._dir_syms = tuple(names)
        return self

    def with_sessions(self, enabled: bool = True) -> ClaudeConfig:
        """Enable / disable tracking of ~/.claude/sessions/."""
        self._include_sessions = enabled
        if enabled and "sessions" not in self._dir_syms:
            self._dir_syms = (*self._dir_syms, "sessions")
        elif not enabled:
            self._dir_syms = tuple(n for n in self._dir_syms if n != "sessions")
        return self

    def with_history(self, enabled: bool = True) -> ClaudeConfig:
        """Enable / disable tracking of ~/.claude/history.jsonl."""
        self._include_history = enabled
        return self

    def with_relative_symlinks(self, enabled: bool = True) -> ClaudeConfig:
        self._relative_symlinks = enabled
        return self

    def with_vendors(self, vendors: Iterable[str]) -> ClaudeConfig:
        """Set the list of AI vendors this configurator targets.

        Order is preserved. Unknown vendors are accepted but raise
        ``ConfigError`` from :py:meth:`vendor_status` so callers can
        surface them. ``claude-code`` is the only fully-supported
        vendor in v0.3.x; others are placeholders.
        """
        self._vendors = tuple(vendors)
        return self

    def select_vendors_interactively(
        self,
        prompt: Prompter | None = None,
        *,
        defaults: Iterable[str] | None = None,
    ) -> tuple[str, ...]:
        """Walk the supported-vendor list asking one yes/no per vendor.

        Falls back to ``defaults`` (or ``DEFAULT_VENDORS``) when no
        prompter is supplied. The user can opt into vendors marked
        ``planned`` — the configurator just won't yet symlink files for
        them. Callers should pass the result to :py:meth:`with_vendors`.
        """
        default_set = set(defaults or self.DEFAULT_VENDORS)
        if prompt is None:
            return tuple(self.DEFAULT_VENDORS)
        picked: list[str] = []
        for vendor in self.SUPPORTED_VENDORS:
            status = self.VENDOR_STATUS.get(vendor, "unknown")
            suffix = "" if status == "current" else f" [{status}]"
            default = vendor in default_set
            if prompt(f"target {vendor}{suffix}?", default):
                picked.append(vendor)
        return tuple(picked) if picked else tuple(self.DEFAULT_VENDORS)

    # ---- properties ---------------------------------------------------

    @property
    def content_dir(self) -> Path:
        return self._content_dir

    @property
    def src_dir(self) -> Path:
        """The 'claude/' subdir inside content_dir — source for symlinks."""
        return self._content_dir / "claude"

    @property
    def target_base(self) -> Path:
        return self._target_base

    @property
    def hostname(self) -> str:
        return _current_hostname()

    @property
    def dir_symlink_names(self) -> tuple[str, ...]:
        return self._dir_syms

    @property
    def secret_patterns(self) -> tuple[str, ...]:
        return self._secrets

    @property
    def ignore_patterns(self) -> tuple[str, ...]:
        return self._ignores

    @property
    def include_sessions(self) -> bool:
        return self._include_sessions

    @property
    def include_history(self) -> bool:
        return self._include_history

    @property
    def relative_symlinks(self) -> bool:
        return self._relative_symlinks

    @property
    def vendors(self) -> tuple[str, ...]:
        """Tuple of AI vendor keys this configurator targets."""
        return self._vendors

    def vendor_status(self, vendor: str) -> str:
        """Per-vendor support status: ``current`` | ``partial`` |
        ``planned`` | ``unknown``."""
        return self.VENDOR_STATUS.get(vendor, "unknown")

    def unsupported_vendors(self) -> tuple[str, ...]:
        """Selected vendors that aren't ``current`` yet — surfaces in CLI
        output so users see what's wired vs what's a placeholder."""
        return tuple(
            v for v in self._vendors
            if self.VENDOR_STATUS.get(v, "unknown") != "current"
        )

    # ---- config persistence -------------------------------------------

    def save_config(self, config_path: Path | str | None = None) -> ClaudeConfig:
        """Write current settings to JSON, merging with whatever is there.

        Unknown keys present in the file on disk are preserved (forward-compat
        for future fields this version doesn't yet recognise).
        """
        path = (
            Path(config_path).expanduser()
            if config_path
            else (self._loaded_config_path or self.DEFAULT_CONFIG)
        )
        path.parent.mkdir(parents=True, exist_ok=True)

        existing: dict[str, Any] = {}
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                # If on-disk file is broken, overwrite rather than crash.
                existing = {}

        merged: dict[str, Any] = {
            **existing,
            "content_dir": str(self._content_dir),
            "target_base": str(self._target_base),
            "secret_patterns": list(self._secrets),
            "ignore_patterns": list(self._ignores),
            "dir_symlink_names": list(self._dir_syms),
            "include_sessions": self._include_sessions,
            "include_history": self._include_history,
            "relative_symlinks": self._relative_symlinks,
            "auto_reconcile": self._auto_reconcile,
            "vendors": list(self._vendors),
        }
        path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
        self._loaded_config_path = path
        return self

    # ---- init ---------------------------------------------------------

    def init(
        self,
        with_examples: bool = True,
        init_git: bool = True,
        with_settings: bool = False,
        apply_decisions: Iterable[str] | None = None,
    ) -> ClaudeConfig:
        """Create the content dir + claude/ subdir; optionally seed examples + git.

        Also applies bundled decision packs (default:
        ``DEFAULT_DECISIONS_ON_INIT``). Pass ``apply_decisions=()`` to
        skip — useful for tests or for a strictly bare setup.
        """
        self._content_dir.mkdir(parents=True, exist_ok=True)
        self.src_dir.mkdir(parents=True, exist_ok=True)

        gitignore = self._content_dir / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text(
                "# Secrets — never commit\n"
                + "\n".join(f"**/{p}" for p in self._secrets)
                + "\n\n# Local noise\n"
                + "\n".join(self._ignores)
                + "\n",
                encoding="utf-8",
            )

        if with_examples:
            example = self.src_dir / "CLAUDE.md"
            if not example.exists():
                example.write_text(
                    "# Personal Claude Code conventions\n\n"
                    "Replace this template with your own preferences. Loaded by\n"
                    "Claude Code at every session start.\n",
                    encoding="utf-8",
                )

        if with_settings:
            settings = self.src_dir / "settings.json"
            if not settings.exists():
                settings.write_text(
                    json.dumps(
                        {
                            "$schema": "https://json.schemastore.org/claude-code-settings.json",
                            "permissions": {"allow": [], "ask": [], "deny": []},
                            "hooks": {},
                        },
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )

        if init_git and not (self._content_dir / ".git").exists():
            self._git("init", "-b", "main", cwd=self._content_dir)

        # Apply baked-in decision packs (non-clobbering).
        packs = (
            self.DEFAULT_DECISIONS_ON_INIT
            if apply_decisions is None
            else tuple(apply_decisions)
        )
        for pack_name in packs:
            try:
                self.decisions_apply(pack_name, force=False)
            except ConfigError as e:
                self._warn(
                    f"decision-pack-missing:{pack_name}",
                    f"could not apply pack '{pack_name}': {e}",
                )

        return self

    # ---- install ------------------------------------------------------

    def install(self, dry_run: bool = False) -> InstallReport:
        """Symlink src_dir/* into target_base/ at matching relative paths.

        Passes:
        1. Whole-directory symlinks for names in dir_symlink_names (memory/,
           commands/, etc.) so new files inside auto-propagate.
        2. Per-file symlinks for everything else. Skips files whose parent
           dir already resolves into src_dir (reachable via a dir symlink).
        3. Host-overlay pass: ``hosts/<current-host>/*`` installs into target
           at the relative path *without* the ``hosts/<host>/`` prefix.
        """
        if not self.src_dir.is_dir():
            raise ConfigError(
                f"Source directory {self.src_dir} does not exist. "
                "Run `.init()` or set a valid content_dir."
            )
        self._target_base.mkdir(parents=True, exist_ok=True)

        links = dirs = correct = backed_up = skipped = overlays = secrets = 0

        # Pass 1: directory symlinks
        for src in self._dirs_to_symlink():
            rel = src.relative_to(self.src_dir)
            target = self._target_base / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if self._is_correct_link(target, src):
                correct += 1
                continue
            if target.exists() and not target.is_symlink():
                self._warn(
                    f"real-dir-collision:{target}",
                    f"Real directory at {target} — skipping (use `track` to move it in)",
                )
                continue
            if not dry_run:
                self._symlink(src, target)
            dirs += 1

        # Pass 2: per-file
        for src in self._files_to_track(include_overlays=False):
            if self._is_secret(src):
                secrets += 1
                continue
            rel = src.relative_to(self.src_dir)
            # Guard: never link files under projects/<slug>/ except memory/
            if self._is_disallowed_project_path(rel):
                self._warn(
                    f"projects-non-memory:{rel}",
                    f"Skipping {rel} — only `memory/` is tracked under projects/<slug>/",
                )
                continue
            target = self._target_base / rel
            if self._parent_dir_resolves_into_src(target):
                skipped += 1
                continue
            if self._is_correct_link(target, src):
                correct += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and not target.is_symlink():
                backup = target.with_suffix(target.suffix + ".before-claude-config")
                if not dry_run:
                    target.rename(backup)
                self._warn(
                    f"real-file-backup:{target}",
                    f"Real file at {target} backed up to {backup.name}",
                )
                backed_up += 1
            if not dry_run:
                self._symlink(src, target)
            links += 1

        # Pass 3: host overlays
        overlay_dir = self.src_dir / self.HOST_OVERLAY_DIR / self.hostname
        if overlay_dir.is_dir():
            for src in sorted(overlay_dir.rglob("*")):
                if not src.is_file():
                    continue
                if self._is_secret(src) or self._matches_ignore(src.name):
                    continue
                rel = src.relative_to(overlay_dir)
                target = self._target_base / rel
                if self._is_correct_link(target, src):
                    correct += 1
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() and not target.is_symlink():
                    backup = target.with_suffix(target.suffix + ".before-claude-config")
                    if not dry_run:
                        target.rename(backup)
                    backed_up += 1
                if not dry_run:
                    self._symlink(src, target)
                overlays += 1

        return InstallReport(
            links_created=links,
            dir_links_created=dirs,
            already_correct=correct,
            real_files_backed_up=backed_up,
            skipped_via_dir_symlink=skipped,
            host_overlays_linked=overlays,
            secrets_skipped=secrets,
        )

    # ---- uninstall ----------------------------------------------------

    def uninstall(self, restore_backups: bool = True) -> UninstallReport:
        """Remove every symlink in target_base that points into src_dir.

        With ``restore_backups=True`` (default), any ``*.before-claude-config``
        file sitting next to a removed symlink is moved back to the original
        name. The content dir itself is never touched.
        """
        removed = 0
        restored = 0
        for link in self._iter_target_symlinks():
            try:
                resolved = link.resolve(strict=False)
            except OSError:
                continue
            if not self._path_in(resolved, self.src_dir):
                continue
            link.unlink()
            removed += 1
            if restore_backups:
                backup = link.with_suffix(link.suffix + ".before-claude-config")
                if backup.exists() and not link.exists():
                    backup.rename(link)
                    restored += 1
        return UninstallReport(removed=removed, backups_restored=restored)

    # ---- track --------------------------------------------------------

    def track(self, path: Path | str) -> ClaudeConfig:
        """Move ``target_base/<path>`` into the content dir + symlink back.

        Handles both files and directories. Cross-device safe via
        ``shutil.move``. Persists state changes (dir_symlink additions,
        include_sessions / include_history toggles) to the loaded JSON
        config if one was used.
        """
        p = Path(path).expanduser().absolute()
        if p.is_symlink():
            raise ConfigError(f"{p} is already a symlink")
        if not p.exists():
            raise ConfigError(f"{p} does not exist")
        if self._matches_secret(p.name):
            raise ConfigError(
                f"{p.name} matches a secret pattern; refusing to track. "
                "Remove the pattern from secret_patterns or rename the file."
            )
        try:
            rel = p.relative_to(self._target_base)
        except ValueError as e:
            raise ConfigError(f"{p} must live under {self._target_base}") from e

        dest = self.src_dir / rel
        if dest.exists():
            raise ConfigError(f"{dest} already exists in the content dir")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p), str(dest))
        self._symlink(dest, p)

        state_changed = False
        if dest.is_dir() and p.name not in self._dir_syms:
            self._dir_syms = (*self._dir_syms, p.name)
            state_changed = True
            if p.name == "sessions":
                self._include_sessions = True

        if dest.is_file() and p.name == "history.jsonl":
            self._include_history = True
            state_changed = True

        if state_changed and self._loaded_config_path is not None:
            self.save_config(self._loaded_config_path)

        return self

    # ---- cleanup ------------------------------------------------------

    def cleanup(
        self,
        dry_run: bool = True,
        include_ephemeral: bool = False,
    ) -> CleanupReport:
        """Remove noise from the content dir + (optionally) the target.

        Always cleans, in both content_dir and target_base:
        - ``.DS_Store`` / matching ``ignore_patterns`` files
        - Broken symlinks under target_base that pointed into src_dir
        - Orphan ``*.before-claude-config`` files whose primary doesn't exist
          and isn't a symlink

        With ``include_ephemeral=True``, additionally clears the contents of
        each RUNTIME_DIRS entry under target_base (paste-cache/, file-history/,
        etc.). Never touches sessions/ or history.jsonl when
        ``include_sessions`` / ``include_history`` are enabled — those are
        explicitly tracked.
        """
        ds: list[Path] = []
        broken: list[Path] = []
        orphans: list[Path] = []
        ephemerals: list[Path] = []

        # 1. ignore-pattern litter in both content + target
        for root in (self._content_dir, self._target_base):
            if not root.exists():
                continue
            for p in root.rglob("*"):
                if not p.is_file() and not p.is_symlink():
                    continue
                if self._matches_ignore(p.name) and not self._matches_ignore_keep(p.name):
                    ds.append(p)

        # 2. broken symlinks under target pointing into src_dir
        for link in self._iter_target_symlinks():
            try:
                tgt_str = os.readlink(link)
            except OSError:
                continue
            tgt = Path(tgt_str)
            if not tgt.is_absolute():
                tgt = (link.parent / tgt).resolve(strict=False)
            if not self._path_in(tgt, self.src_dir):
                continue
            if not tgt.exists():
                broken.append(link)

        # 3. orphan .before-claude-config backups
        if self._target_base.exists():
            for backup in self._target_base.rglob("*.before-claude-config"):
                if not backup.is_file():
                    continue
                primary = backup.with_suffix("")
                # Backups created by install have the form "<name>.<ext>.before-claude-config"
                # so the "primary" is the same path without the trailing suffix.
                if primary.is_symlink():
                    # Active symlink — backup is shadow data.
                    orphans.append(backup)
                elif not primary.exists():
                    # Primary gone entirely — backup is orphan.
                    orphans.append(backup)

        # 4. optional: clear ephemeral runtime dirs
        if include_ephemeral and self._target_base.exists():
            for name in self.RUNTIME_DIRS:
                if name == "sessions" and self._include_sessions:
                    continue
                d = self._target_base / name
                if not d.is_dir() or d.is_symlink():
                    continue
                for entry in d.rglob("*"):
                    if entry.is_file() or entry.is_symlink():
                        ephemerals.append(entry)
            for fname in self.RUNTIME_FILES:
                if fname == "history.jsonl" and self._include_history:
                    continue
                f = self._target_base / fname
                if f.is_file() and not f.is_symlink():
                    ephemerals.append(f)

        if not dry_run:
            for p in ds:
                self._unlink_quietly(p)
            for p in broken:
                self._unlink_quietly(p)
            for p in orphans:
                self._unlink_quietly(p)
            for p in ephemerals:
                self._unlink_quietly(p)

        return CleanupReport(
            ds_store_removed=ds,
            broken_symlinks_removed=broken,
            orphan_backups=orphans,
            ephemeral_paths_cleaned=ephemerals,
            dry_run=dry_run,
        )

    # ---- list ---------------------------------------------------------

    def list_contents(self) -> ListingReport:
        """Grouped view of everything in src_dir.

        Groups (in order):
          - Top-level config files (CLAUDE.md, settings.json, …)
          - Auto-symlinked dirs (memory, commands, agents, skills, hooks,
            prompts — one entry per dir, with file count + size)
          - Plugin config files (plugins/blocklist.json etc.)
          - Per-project memory (projects/<slug>/memory)
          - Host overlays (hosts/<host>/<file>)
          - Opt-in tracked dirs (sessions/ if include_sessions; history.jsonl
            if include_history)
          - Other tracked files (anything left over)
        """
        if not self.src_dir.exists():
            return ListingReport(
                content_dir=self._content_dir,
                target_base=self._target_base,
                hostname=self.hostname,
                groups=[],
            )

        groups: list[ListingGroup] = []
        consumed: set[Path] = set()

        # Top-level config files
        top_paths: list[Path] = []
        for name in self.KNOWN_CONFIG_FILES:
            p = self.src_dir / name
            if p.is_file():
                top_paths.append(p)
        if any(self.src_dir.glob("*.md")):
            for p in sorted(self.src_dir.glob("*.md")):
                if p.is_file() and p not in top_paths:
                    top_paths.append(p)
        groups.append(self._make_group("Config files (top-level)", top_paths))
        consumed.update(top_paths)

        # Auto-symlinked dirs
        for name in self._dir_syms:
            d = self.src_dir / name
            if name == "memory":
                continue
            if not d.is_dir():
                continue
            paths = [p for p in sorted(d.rglob("*")) if p.is_file()]
            groups.append(self._make_group(f"Auto-grow dir: {name}/", paths))
            consumed.update(paths)

        # Plugin config files
        plug_dir = self.src_dir / "plugins"
        if plug_dir.is_dir():
            plug_paths = [
                plug_dir / name
                for name in self.DEFAULT_PLUGIN_CONFIG_FILES
                if (plug_dir / name).is_file()
            ]
            if plug_paths:
                groups.append(self._make_group("Plugin config files", plug_paths))
                consumed.update(plug_paths)

        # Per-project memory
        projects_dir = self.src_dir / "projects"
        if projects_dir.is_dir():
            mem_paths: list[Path] = []
            for slug_dir in sorted(projects_dir.iterdir()):
                if not slug_dir.is_dir():
                    continue
                memory_dir = slug_dir / "memory"
                if memory_dir.is_dir():
                    mem_paths.extend(p for p in sorted(memory_dir.rglob("*")) if p.is_file())
            groups.append(self._make_group("Per-project memory", mem_paths))
            consumed.update(mem_paths)

        # Host overlays
        overlay_root = self.src_dir / self.HOST_OVERLAY_DIR
        if overlay_root.is_dir():
            ov_paths: list[Path] = []
            for host_dir in sorted(overlay_root.iterdir()):
                if not host_dir.is_dir():
                    continue
                label_paths = [p for p in sorted(host_dir.rglob("*")) if p.is_file()]
                ov_paths.extend(label_paths)
            if ov_paths:
                groups.append(self._make_group("Host overlays", ov_paths))
                consumed.update(ov_paths)

        # Other tracked files
        leftover = [
            p
            for p in self._files_to_track(include_overlays=False)
            if p not in consumed
        ]
        if leftover:
            groups.append(self._make_group("Other tracked files", leftover))

        return ListingReport(
            content_dir=self._content_dir,
            target_base=self._target_base,
            hostname=self.hostname,
            groups=groups,
        )

    def _make_group(self, label: str, paths: list[Path]) -> ListingGroup:
        rels = sorted(str(p.relative_to(self.src_dir)) for p in paths)
        total = 0
        for p in paths:
            with contextlib.suppress(OSError):
                total += p.stat().st_size
        return ListingGroup(label=label, paths=rels, total_bytes=total)

    # ---- view ---------------------------------------------------------

    def view(self, relpath: str | Path) -> str:
        """Return the contents of a tracked file as a string.

        ``relpath`` is interpreted relative to ``src_dir``. The path must
        resolve to a file inside ``src_dir`` (no path-traversal escape).
        """
        rel = Path(relpath)
        if rel.is_absolute():
            raise ConfigError(f"{relpath} must be a path relative to src_dir")
        full = (self.src_dir / rel).resolve(strict=False)
        if not self._path_in(full, self.src_dir):
            raise ConfigError(f"{relpath} resolves outside src_dir")
        if not full.is_file():
            raise ConfigError(f"{relpath} is not a file")
        return full.read_text(encoding="utf-8")

    # ---- doctor -------------------------------------------------------

    def doctor(self) -> DoctorReport:
        """Verify every src file is reachable from target_base via a symlink chain."""
        issues: list[str] = []

        # Forward check: every config file in src_dir resolves at target_base
        for src in self._files_to_track(include_overlays=False):
            if self._is_secret(src):
                continue
            rel = src.relative_to(self.src_dir)
            if self._is_disallowed_project_path(rel):
                continue
            link = self._target_base / rel
            if not link.exists():
                issues.append(f"missing path: {link}")
                continue
            try:
                resolved = link.resolve()
            except OSError as e:
                issues.append(f"unreadable: {link} ({e})")
                continue
            if resolved != src:
                issues.append(f"wrong resolution: {link} -> {resolved} (expected {src})")

        # Orphan-symlink check: target symlinks pointing into a now-missing src
        for link in self._iter_target_symlinks():
            try:
                tgt = Path(os.readlink(link))
            except OSError:
                continue
            tgt_abs = tgt if tgt.is_absolute() else (link.parent / tgt).resolve(strict=False)
            if self._path_in(tgt_abs, self.src_dir) and not link.exists():
                issues.append(f"orphan: {link} -> {tgt} (target missing)")

        # Host-overlay symlinks for *other* hosts pointing at this machine
        overlay_root = self.src_dir / self.HOST_OVERLAY_DIR
        if overlay_root.is_dir():
            for link in self._iter_target_symlinks():
                try:
                    tgt = link.resolve(strict=False)
                except OSError:
                    continue
                if not self._path_in(tgt, overlay_root):
                    continue
                parts = tgt.relative_to(overlay_root).parts
                if parts and parts[0] != self.hostname:
                    issues.append(
                        f"foreign host overlay: {link} -> {tgt} "
                        f"(hostname is {self.hostname}, link points at {parts[0]})"
                    )

        return DoctorReport(issues=issues)

    # ---- status -------------------------------------------------------

    def status(self) -> StatusReport:
        """Report what's tracked, untracked candidates, and git state."""
        tracked = sorted(
            str(p.relative_to(self.src_dir))
            for p in self._files_to_track(include_overlays=True)
            if not self._is_secret(p)
        )

        candidates: list[str] = []
        if self._target_base.exists():
            skip_dirs = set(self.RUNTIME_DIRS)
            skip_files = set(self.RUNTIME_FILES)
            if self._include_sessions:
                skip_dirs.discard("sessions")
            if self._include_history:
                skip_files.discard("history.jsonl")

            for p in self._target_base.rglob("*"):
                if not p.is_file() or p.is_symlink():
                    continue
                try:
                    rel = p.relative_to(self._target_base)
                except ValueError:
                    continue
                if rel.parts and rel.parts[0] in skip_dirs:
                    continue
                # Mixed dirs: drop only the runtime children, keep the config ones
                if rel.parts and rel.parts[0] in self.MIXED_DIRS:
                    runtime_children = self.MIXED_RUNTIME_CHILDREN.get(rel.parts[0], frozenset())
                    if len(rel.parts) >= 2 and rel.parts[1] in runtime_children:
                        continue
                if p.name in skip_files and rel.parent == Path():
                    continue
                if self._matches_ignore(p.name) or self._matches_secret(p.name):
                    continue
                candidates.append(str(rel))

        git_clean = True
        git_summary = ""
        if (self._content_dir / ".git").is_dir():
            r = self._git("status", "--porcelain", cwd=self._content_dir, check=False)
            git_summary = r.stdout.strip()
            git_clean = not git_summary

        return StatusReport(
            content_dir=self._content_dir,
            target_base=self._target_base,
            hostname=self.hostname,
            tracked_files=tracked,
            untracked_candidates=candidates,
            git_clean=git_clean,
            git_summary=git_summary,
        )

    # ---- sync ---------------------------------------------------------

    def sync(self, message: str | None = None, push: bool = False) -> SyncReport:
        """git add + commit + optionally push, scoped to content_dir.

        Detects current branch + first remote rather than hard-coding
        ``origin main``.
        """
        if not (self._content_dir / ".git").is_dir():
            raise ConfigError(
                f"{self._content_dir} is not a git repo. Run `.init()` first."
            )

        porcelain = self._git("status", "--porcelain", cwd=self._content_dir, check=False)
        changes = porcelain.stdout.strip().splitlines()

        committed = False
        sha: str | None = None
        msg = message

        if changes:
            if not msg:
                msg = self._auto_message(changes)
            self._git("add", "-A", cwd=self._content_dir)
            self._git("commit", "-m", msg, cwd=self._content_dir)
            sha = self._git("rev-parse", "HEAD", cwd=self._content_dir).stdout.strip()
            committed = True

        # Detect branch + remote for push (and for the report regardless).
        branch_r = self._git(
            "rev-parse", "--abbrev-ref", "HEAD", cwd=self._content_dir, check=False
        )
        branch = branch_r.stdout.strip() if branch_r.returncode == 0 else None

        remote: str | None = None
        pushed = False
        push_err: str | None = None
        if push:
            r = self._git("remote", cwd=self._content_dir, check=False)
            remotes = [line.strip() for line in r.stdout.splitlines() if line.strip()]
            if not remotes:
                push_err = "no remote configured"
            else:
                remote = "origin" if "origin" in remotes else remotes[0]
                if not branch:
                    push_err = "could not determine current branch"
                else:
                    pr = self._git(
                        "push", remote, branch, cwd=self._content_dir, check=False
                    )
                    if pr.returncode == 0:
                        pushed = True
                    else:
                        push_err = pr.stderr.strip() or "push failed"

        return SyncReport(
            committed=committed,
            commit_sha=sha,
            commit_message=msg,
            pushed=pushed,
            push_error=push_err,
            branch=branch,
            remote=remote,
        )

    # ---- decisions (bundled global decision packs) --------------------

    def _decisions_root(self) -> Any:
        """Return the Traversable root of the bundled decisions resource dir."""
        return resources.files("ai_configurator") / "resources" / "decisions"

    def decisions_list(self) -> DecisionsListReport:
        """Enumerate every decision pack shipped with the installed package."""
        root = self._decisions_root()
        packs: list[DecisionPack] = []
        for entry in sorted(root.iterdir(), key=lambda p: p.name):
            if not entry.is_dir():
                continue
            manifest = entry / "manifest.json"
            if not manifest.is_file():
                continue
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                raise ConfigError(
                    f"pack '{entry.name}': invalid manifest.json: {e.msg}"
                ) from e
            packs.append(self._build_pack(data, entry))
        return DecisionsListReport(packs=packs)

    def decisions_show(self, name: str) -> DecisionPack:
        """Return the manifest + file list for a single pack."""
        root = self._decisions_root()
        pack_dir = root / name
        if not pack_dir.is_dir():
            raise ConfigError(f"unknown decision pack: {name}")
        manifest = pack_dir / "manifest.json"
        if not manifest.is_file():
            raise ConfigError(f"pack '{name}': missing manifest.json")
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ConfigError(
                f"pack '{name}': invalid manifest.json: {e.msg}"
            ) from e
        return self._build_pack(data, pack_dir)

    def decisions_apply(
        self,
        name: str,
        force: bool = False,
        dry_run: bool = False,
    ) -> DecisionsApplyReport:
        """Copy a pack's files into ``src_dir``.

        Refuses to overwrite existing files unless ``force=True``. Refuses
        to apply if any dest matches a secret pattern.
        """
        pack = self.decisions_show(name)
        self.src_dir.mkdir(parents=True, exist_ok=True)
        root = self._decisions_root() / name

        # Pre-flight: refuse if any dest matches a secret pattern.
        for f in pack.files:
            if self._matches_secret(Path(f.dest).name):
                raise ConfigError(
                    f"pack '{name}': dest '{f.dest}' matches a secret pattern; "
                    "refusing to apply"
                )

        written: list[str] = []
        skipped: list[str] = []
        overwritten: list[str] = []
        for f in pack.files:
            src = root / f.src
            if not src.is_file():
                raise ConfigError(
                    f"pack '{name}': missing source file {f.src}"
                )
            target = self.src_dir / f.dest
            exists = target.exists()
            if exists and not force:
                skipped.append(f.dest)
                continue
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(src.read_bytes())
                if f.mode is not None:
                    try:
                        mode_bits = int(f.mode, 8) & 0o7777
                    except ValueError as e:
                        raise ConfigError(
                            f"pack '{name}': invalid mode '{f.mode}' "
                            f"for {f.dest} (expected octal string)"
                        ) from e
                    with contextlib.suppress(OSError):
                        target.chmod(mode_bits)
            if exists:
                overwritten.append(f.dest)
            else:
                written.append(f.dest)

        return DecisionsApplyReport(
            pack=name,
            written=written,
            skipped=skipped,
            overwritten=overwritten,
            dry_run=dry_run,
        )

    def _build_pack(self, data: dict[str, Any], pack_dir: Any) -> DecisionPack:
        files = [
            DecisionFile(
                src=f["src"],
                dest=f["dest"],
                mode=f.get("mode"),
            )
            for f in data.get("files", [])
        ]
        readme_path = pack_dir / "details.md"
        readme = ""
        if readme_path.is_file():
            readme = readme_path.read_text(encoding="utf-8")
        return DecisionPack(
            name=data["name"],
            description=data.get("description", ""),
            version=data.get("version", "0.0.0"),
            files=files,
            readme=readme,
        )

    # ---- reconcile (auto-apply on upgrade) ----------------------------

    def reconcile(self, force_reapply: bool = False) -> ReconcileReport:
        """Apply any auto-apply packs the user is missing since their last upgrade.

        Workflow:
        1. Read ``last_applied_version`` from the loaded JSON config
           (defaults to ``"0.0.0"`` when absent).
        2. Compare to the currently-installed package version.
        3. If they differ (or ``force_reapply``), apply every pack in
           ``DEFAULT_DECISIONS_ON_INIT`` non-clobberingly. Existing
           files stay; new files (added in a newer ``ai-configurator``)
           land.
        4. Write the current version back to the JSON config.

        Designed to be called transparently on every CLI invocation —
        no-op when versions match. Off by default in tests; toggle via
        the ``auto_reconcile`` constructor arg or the ``auto_reconcile``
        JSON config field.

        Returns a ``ReconcileReport`` describing what happened.
        """
        current_version = _package_version()
        last_version = self._read_last_applied_version()

        if not force_reapply and last_version == current_version:
            return ReconcileReport(
                from_version=last_version,
                to_version=current_version,
                upgrade_happened=False,
            )

        applied: list[str] = []
        failed: list[tuple[str, str]] = []
        for pack_name in self.DEFAULT_DECISIONS_ON_INIT:
            try:
                report = self.decisions_apply(pack_name, force=False)
                if report.written or report.overwritten:
                    applied.append(pack_name)
            except (ConfigError, Exception) as e:
                failed.append((pack_name, str(e)))

        self._write_last_applied_version(current_version)

        return ReconcileReport(
            from_version=last_version,
            to_version=current_version,
            upgrade_happened=True,
            packs_applied=applied,
            packs_failed=failed,
        )

    def reconcile_if_enabled(self) -> ReconcileReport | None:
        """Helper for CLI startup. Honours the ``auto_reconcile`` flag.

        Returns ``None`` when auto-reconcile is off or when there's no
        loaded config (e.g., env-var-only invocations in tests).
        """
        if not self._auto_reconcile:
            return None
        if self._loaded_config_path is None:
            # No persistent config to track versions against — skip.
            return None
        try:
            return self.reconcile()
        except Exception:
            return None

    def _read_last_applied_version(self) -> str:
        """Read ``last_applied_version`` from the loaded JSON config."""
        if self._loaded_config_path is None or not self._loaded_config_path.is_file():
            return "0.0.0"
        try:
            data = json.loads(self._loaded_config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return "0.0.0"
        v = data.get("last_applied_version", "0.0.0")
        return str(v) if isinstance(v, str) else "0.0.0"

    def _write_last_applied_version(self, version: str) -> None:
        """Persist ``last_applied_version`` in the loaded JSON config."""
        if self._loaded_config_path is None:
            return
        path = self._loaded_config_path
        path.parent.mkdir(parents=True, exist_ok=True)
        existing: dict[str, Any] = {}
        if path.is_file():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                existing = {}
        existing["last_applied_version"] = version
        path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")

    # ---- fetch --------------------------------------------------------

    DEFAULT_FETCH_MAX_BYTES: ClassVar[int] = 1024 * 1024  # 1 MiB
    DEFAULT_FETCH_TIMEOUT: ClassVar[float] = 60.0
    DEFAULT_FETCH_RETRIES: ClassVar[int] = 2

    def fetch_canonical(
        self,
        url: str,
        dest: Path | str,
        expect_sha256: str | None = None,
        max_bytes: int = DEFAULT_FETCH_MAX_BYTES,
        allow_http: bool = False,
        allow_binary: bool = False,
        timeout: float = DEFAULT_FETCH_TIMEOUT,
        retries: int = DEFAULT_FETCH_RETRIES,
        include_first_line: bool = True,
    ) -> FetchReport:
        """Download a canonical / upstream text file to disk safely.

        Disk-to-disk: the body never enters memory beyond the chunk
        buffer, and never enters the return value beyond the first
        line (intended for canonical files whose first line is a title;
        pass ``include_first_line=False`` to suppress).

        Atomic write via temp-file + rename. Idempotent: if the
        destination already has identical content, status is
        ``unchanged`` and no write happens. HTTPS-only unless
        ``allow_http=True``.

        Raises ``ConfigError`` on validation, size, hash, or network
        failure.
        """
        # URL scheme guard
        if url.startswith("https://"):
            pass
        elif url.startswith("http://"):
            if not allow_http:
                raise ConfigError(
                    "URL must use https:// (pass allow_http=True to permit http)"
                )
        else:
            raise ConfigError("URL must be http(s)://")

        dest_path = Path(dest).expanduser().resolve()
        if not dest_path.parent.exists():
            raise ConfigError(
                f"destination dir does not exist: {dest_path.parent}"
            )

        # Stream to a sibling temp file
        tmp = dest_path.with_name(dest_path.name + ".dl-tmp")
        last_err: Exception | None = None
        for attempt in range(retries + 1):
            try:
                self._stream_to_file(url, tmp, max_bytes=max_bytes, timeout=timeout)
                last_err = None
                break
            except (
                urllib.error.URLError,
                urllib.error.HTTPError,
                TimeoutError,
                ConnectionError,
            ) as e:
                last_err = e
                if tmp.exists():
                    tmp.unlink()
                if attempt < retries:
                    time.sleep(1)
            except ConfigError:
                if tmp.exists():
                    tmp.unlink()
                raise

        if last_err is not None:
            raise ConfigError(f"fetch failed for {url}: {last_err}") from last_err

        bytes_n = tmp.stat().st_size
        if bytes_n == 0:
            tmp.unlink()
            raise ConfigError("downloaded file is empty")
        if bytes_n > max_bytes:
            tmp.unlink()
            raise ConfigError(f"size {bytes_n} exceeds cap {max_bytes}")

        if not allow_binary:
            try:
                tmp.read_text(encoding="utf-8")
            except UnicodeDecodeError as e:
                tmp.unlink()
                raise ConfigError(
                    "not valid UTF-8 (pass allow_binary=True if intended)"
                ) from e

        sha = hashlib.sha256(tmp.read_bytes()).hexdigest()
        if expect_sha256 and sha != expect_sha256:
            tmp.unlink()
            raise ConfigError(
                f"sha256 mismatch: expected {expect_sha256} got {sha}"
            )

        status = "created"
        if dest_path.exists():
            old_sha = hashlib.sha256(dest_path.read_bytes()).hexdigest()
            if old_sha == sha:
                tmp.unlink()
                status = "unchanged"
            else:
                status = "updated"

        if status != "unchanged":
            # Preserve mode if file existed; default 0o644 for new files.
            mode = dest_path.stat().st_mode & 0o777 if dest_path.exists() else 0o644
            shutil.move(str(tmp), str(dest_path))
            with contextlib.suppress(OSError):
                dest_path.chmod(mode)

        text_view = dest_path.read_text(encoding="utf-8", errors="replace")
        lines_n = text_view.count("\n")
        if text_view and not text_view.endswith("\n"):
            lines_n += 1
        first_line = ""
        if include_first_line:
            first_line = text_view.split("\n", 1)[0].rstrip("\r")

        return FetchReport(
            path=dest_path,
            bytes=bytes_n,
            lines=lines_n,
            sha256=sha,
            status=status,
            first_line=first_line,
        )

    def _stream_to_file(
        self,
        url: str,
        dest: Path,
        max_bytes: int,
        timeout: float,
    ) -> None:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": _user_agent()},
        )
        total = 0
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            # ``urlopen`` doesn't raise for non-2xx — it returns the response.
            # http.client / urllib raise HTTPError for 4xx/5xx, so this branch
            # is defensive against odd transports.
            status_code = getattr(resp, "status", None)
            if status_code is not None and not (200 <= int(status_code) < 300):
                raise ConfigError(
                    f"non-2xx response: {status_code} for {url}"
                )
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(64 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise ConfigError(
                            f"download exceeds max-bytes cap {max_bytes}"
                        )
                    f.write(chunk)

    # ---- repair -------------------------------------------------------

    def repair(self, dry_run: bool = False) -> RepairReport:
        """Heal a broken install.

        Performs:
        1. ``cleanup`` (broken symlinks, orphan backups, .DS_Store litter)
        2. ``install`` (rebuilds missing or wrong symlinks)
        3. Doctor walks to surface anything still wrong

        Safe to run repeatedly. ``dry_run`` shows what would happen.
        """
        actions: list[RepairAction] = []
        clean_report = self.cleanup(dry_run=dry_run, include_ephemeral=False)
        # Restore *.before-claude-config backups that protected a now-broken link
        for broken in clean_report.broken_symlinks_removed:
            backup = broken.with_suffix(broken.suffix + ".before-claude-config")
            if backup.exists() and not broken.exists():
                if not dry_run:
                    backup.rename(broken)
                actions.append(
                    RepairAction(kind="backup-restored", target=broken, detail=str(backup))
                )
        for p in clean_report.broken_symlinks_removed:
            actions.append(RepairAction(kind="broken-symlink-removed", target=p))
        for p in clean_report.orphan_backups:
            actions.append(RepairAction(kind="orphan-backup-removed", target=p))
        for p in clean_report.ds_store_removed:
            actions.append(RepairAction(kind="ds-store-removed", target=p))

        install_report: InstallReport | None = None
        if self.src_dir.is_dir():
            install_report = self.install(dry_run=dry_run)
            if install_report.links_created:
                actions.append(
                    RepairAction(
                        kind="link-recreated",
                        target=self._target_base,
                        detail=f"{install_report.links_created} file(s)",
                    )
                )
            if install_report.dir_links_created:
                actions.append(
                    RepairAction(
                        kind="dir-link-recreated",
                        target=self._target_base,
                        detail=f"{install_report.dir_links_created} dir(s)",
                    )
                )
            if install_report.real_files_backed_up:
                actions.append(
                    RepairAction(
                        kind="real-file-backed-up",
                        target=self._target_base,
                        detail=f"{install_report.real_files_backed_up} file(s)",
                    )
                )

        return RepairReport(
            actions=actions,
            install_report=install_report,
            cleanup_report=clean_report,
            dry_run=dry_run,
        )

    # ---- validate -----------------------------------------------------

    def validate(self) -> ValidationReport:
        """Pre-flight environment check used by ``bootstrap``.

        Returns blockers (must fix) and warnings (informational).
        """
        issues: list[str] = []
        warnings_: list[str] = []

        # Python version (we're running, so report any oddity)
        actual = sys.version_info[:2]
        if actual < self.MIN_PYTHON:
            min_str = ".".join(str(n) for n in self.MIN_PYTHON)
            issues.append(
                f"Python {actual[0]}.{actual[1]} is older than the required {min_str}"
            )

        # `python3` on PATH — useful for the generator-script pattern
        if not shutil.which("python3") and not shutil.which("python"):
            warnings_.append(
                "no `python3` or `python` on PATH "
                "(generator scripts require a Python interpreter)"
            )

        if not shutil.which("git"):
            issues.append("git not found on PATH (required for `init` and `sync`)")

        # Target parent must exist (or be creatable) and be writable.
        target_parent = self._target_base.parent
        if not target_parent.exists():
            issues.append(f"target parent does not exist: {target_parent}")
        elif not os.access(target_parent, os.W_OK):
            issues.append(f"target parent not writable: {target_parent}")

        content_parent = self._content_dir.parent
        if not content_parent.exists():
            issues.append(f"content parent does not exist: {content_parent}")
        elif not os.access(content_parent, os.W_OK):
            issues.append(f"content parent not writable: {content_parent}")

        # If target_base exists and is a regular file, that's fatal.
        if self._target_base.exists() and not self._target_base.is_dir():
            issues.append(f"target {self._target_base} exists and is not a directory")

        # Warn if content_dir exists with content already + no git
        if (
            self._content_dir.exists()
            and self.src_dir.exists()
            and any(self.src_dir.iterdir())
            and not (self._content_dir / ".git").exists()
        ):
            warnings_.append(
                f"{self._content_dir} has content but no .git/ — `init` will add it"
            )

        # Warn if a foreign symlink already exists at the target
        for known in self.KNOWN_CONFIG_FILES:
            t = self._target_base / known
            if t.is_symlink():
                try:
                    tgt = t.resolve(strict=False)
                except OSError:
                    continue
                if not self._path_in(tgt, self.src_dir):
                    warnings_.append(
                        f"{t} is a symlink pointing outside content_dir "
                        f"({tgt}); install will not touch it"
                    )

        return ValidationReport(issues=issues, warnings=warnings_)

    # ---- bootstrap ----------------------------------------------------

    def bootstrap(
        self,
        push: bool = False,
        remote_url: str | None = None,
        with_settings: bool = False,
        init_git: bool = True,
        commit_message: str | None = None,
        dry_run: bool = False,
        prompt: Prompter | None = None,
        apply_decisions: Iterable[str] | None = None,
    ) -> BootstrapReport:
        """One-shot first-time setup: validate, init, install, [push], doctor.

        Designed to be safe to re-run. Each step short-circuits if the work
        is already done. Failures stop the sequence and surface in the
        report; later steps are marked skipped.

        ``prompt`` is a callable used for confirmation prompts. When
        ``None``, no prompts are issued (non-interactive default). The CLI
        passes a TTY-aware prompter; tests pass a recording stub.
        """
        steps: list[BootstrapStep] = []

        def _step(name: str, ok: bool, detail: str = "", skipped: bool = False) -> bool:
            steps.append(BootstrapStep(name=name, ok=ok, detail=detail, skipped=skipped))
            return ok

        # 1. Validate
        val = self.validate()
        if val.issues:
            _step("validate", ok=False, detail=val.summary())
            return BootstrapReport(steps=steps, dry_run=dry_run)
        _step(
            "validate",
            ok=True,
            detail=val.summary() if val.warnings else "environment ok",
        )

        # 2. Vendor selection (interactive only; non-interactive keeps default)
        if prompt is not None and not dry_run:
            chosen = self.select_vendors_interactively(
                prompt, defaults=self._vendors,
            )
            if chosen != self._vendors:
                self.with_vendors(chosen)
                if self._loaded_config_path is not None:
                    self.save_config(self._loaded_config_path)
                unsupp = self.unsupported_vendors()
                detail = f"vendors: {', '.join(chosen)}"
                if unsupp:
                    detail += f"  (planned, not yet wired: {', '.join(unsupp)})"
                _step("vendors", ok=True, detail=detail)
            else:
                _step("vendors", ok=True, detail=f"vendors: {', '.join(self._vendors)}")
        else:
            _step("vendors", ok=True, detail=f"vendors: {', '.join(self._vendors)}")

        # 3. Confirm clobber-over-existing-content
        already_initialized = self.src_dir.exists() and any(self.src_dir.iterdir())
        if (
            already_initialized
            and prompt is not None
            and not prompt(
                f"content dir {self.src_dir} already has files. continue?",
                default=True,
            )
        ):
            _step("init", ok=False, detail="aborted by user", skipped=True)
            _step("install", ok=False, detail="aborted by user", skipped=True)
            _step("doctor", ok=False, detail="aborted by user", skipped=True)
            return BootstrapReport(steps=steps, dry_run=dry_run)

        # 3. Init
        if dry_run:
            _step("init", ok=True, detail="[dry-run] would init content dir + git")
        else:
            try:
                self.init(
                    with_examples=True,
                    init_git=init_git,
                    with_settings=with_settings,
                    apply_decisions=apply_decisions,
                )
                packs = (
                    self.DEFAULT_DECISIONS_ON_INIT
                    if apply_decisions is None
                    else tuple(apply_decisions)
                )
                detail_parts = ["content dir ready"]
                if init_git:
                    detail_parts.append("git initialised")
                if packs:
                    detail_parts.append(
                        f"decision packs applied: {', '.join(packs)}"
                    )
                _step("init", ok=True, detail="; ".join(detail_parts))
            except ConfigError as e:
                _step("init", ok=False, detail=str(e))
                return BootstrapReport(steps=steps, dry_run=dry_run)

        # 4. Install
        if dry_run:
            # In dry-run, init was a no-op so src_dir may not exist.
            # Don't call install() — just describe what it would do.
            _step(
                "install",
                ok=True,
                detail=f"[dry-run] would symlink {self.src_dir}/* into {self._target_base}/*",
            )
        else:
            try:
                report = self.install(dry_run=False)
                _step("install", ok=True, detail=report.summary())
            except ConfigError as e:
                _step("install", ok=False, detail=str(e))
                return BootstrapReport(steps=steps, dry_run=dry_run)

        # 5. Optional: set up remote
        if remote_url and not dry_run:
            try:
                existing = self._git("remote", cwd=self._content_dir, check=False).stdout
                if "origin" in existing.split():
                    self._git(
                        "remote", "set-url", "origin", remote_url, cwd=self._content_dir
                    )
                    _step("remote", ok=True, detail=f"origin updated -> {remote_url}")
                else:
                    self._git(
                        "remote", "add", "origin", remote_url, cwd=self._content_dir
                    )
                    _step("remote", ok=True, detail=f"origin added -> {remote_url}")
            except ConfigError as e:
                _step("remote", ok=False, detail=str(e))
                return BootstrapReport(steps=steps, dry_run=dry_run)
        elif remote_url and dry_run:
            _step("remote", ok=True, detail=f"[dry-run] would point origin -> {remote_url}")

        # 6. Optional: sync (commit + push)
        if push:
            if (
                prompt is not None
                and not dry_run
                and not prompt(
                    "push committed content to remote? (changes will be visible to anyone "
                    "with read access to the remote)",
                    default=True,
                )
            ):
                _step("sync", ok=False, detail="push declined by user", skipped=True)
                self._add_doctor_step(steps, dry_run)
                return BootstrapReport(steps=steps, dry_run=dry_run)
            if dry_run:
                _step("sync", ok=True, detail="[dry-run] would commit + push")
            else:
                try:
                    sync = self.sync(message=commit_message, push=True)
                    _step("sync", ok=sync.push_error is None, detail=sync.summary())
                    if sync.push_error:
                        self._add_doctor_step(steps, dry_run)
                        return BootstrapReport(steps=steps, dry_run=dry_run)
                except ConfigError as e:
                    _step("sync", ok=False, detail=str(e))
                    self._add_doctor_step(steps, dry_run)
                    return BootstrapReport(steps=steps, dry_run=dry_run)

        # 7. Doctor
        self._add_doctor_step(steps, dry_run)
        return BootstrapReport(steps=steps, dry_run=dry_run)

    def _add_doctor_step(self, steps: list[BootstrapStep], dry_run: bool) -> None:
        if dry_run:
            steps.append(BootstrapStep(name="doctor", ok=True, detail="[dry-run] would verify"))
            return
        try:
            report = self.doctor()
            steps.append(
                BootstrapStep(
                    name="doctor", ok=report.healthy, detail=report.summary()
                )
            )
        except ConfigError as e:
            steps.append(BootstrapStep(name="doctor", ok=False, detail=str(e)))

    # ---- internals ----------------------------------------------------

    def _files_to_track(self, include_overlays: bool) -> list[Path]:
        """Files in src_dir matching neither ignore nor secret patterns.

        With ``include_overlays=False``, files under ``hosts/<host>/`` are
        excluded (they're handled by the install host-overlay pass).
        """
        if not self.src_dir.exists():
            return []
        out: list[Path] = []
        overlay_root = self.src_dir / self.HOST_OVERLAY_DIR
        for p in self.src_dir.rglob("*"):
            if not p.is_file() or p.is_symlink():
                continue
            if any(self._matches_ignore(part) for part in p.parts):
                continue
            if not include_overlays and self._path_in(p, overlay_root):
                continue
            out.append(p)
        return sorted(out)

    def _dirs_to_symlink(self) -> list[Path]:
        """Directories in src_dir whose basename is in dir_symlink_names."""
        if not self.src_dir.exists():
            return []
        results: list[Path] = []
        for p in sorted(self.src_dir.rglob("*")):
            if not p.is_dir() or p.is_symlink():
                continue
            if p.name not in self._dir_syms:
                continue
            results.append(p)
        return results

    def _iter_target_symlinks(self) -> list[Path]:
        if not self._target_base.exists():
            return []
        results: list[Path] = []

        def _walk(d: Path) -> None:
            try:
                entries = list(d.iterdir())
            except OSError:
                return
            for entry in entries:
                if entry.is_symlink():
                    results.append(entry)
                    continue  # don't descend
                if entry.is_dir() and entry.name not in self.RUNTIME_DIRS:
                    _walk(entry)

        _walk(self._target_base)
        return results

    def _is_correct_link(self, target: Path, src: Path) -> bool:
        if not target.is_symlink():
            return False
        try:
            stored = Path(os.readlink(target))
        except OSError:
            return False
        if stored.is_absolute():
            return stored == src
        # Relative — resolve against the link's parent.
        return (target.parent / stored).resolve(strict=False) == src.resolve(strict=False)

    def _parent_dir_resolves_into_src(self, target: Path) -> bool:
        parent = target.parent
        if not parent.exists():
            return False
        try:
            return self._path_in(parent.resolve(), self.src_dir)
        except OSError:
            return False

    def _is_secret(self, path: Path) -> bool:
        return any(self._matches_secret(part) for part in path.parts)

    def _matches_secret(self, name: str) -> bool:
        return any(fnmatch.fnmatch(name, pat) for pat in self._secrets)

    def _matches_ignore(self, name: str) -> bool:
        return any(fnmatch.fnmatch(name, pat) for pat in self._ignores)

    def _matches_ignore_keep(self, name: str) -> bool:
        """Ignore patterns that also indicate 'don't actively delete' on cleanup."""
        return fnmatch.fnmatch(name, "*.before-claude-config")

    def _is_disallowed_project_path(self, rel: Path) -> bool:
        """``projects/<slug>/<not-memory>`` is disallowed — only memory/ is tracked."""
        parts = rel.parts
        if len(parts) < 3 or parts[0] != "projects":
            return False
        return parts[2] != "memory" and not (len(parts) >= 3 and "memory" in parts[2:])

    def _symlink(self, src: Path, target: Path) -> None:
        """Create a symlink at ``target`` pointing to ``src``.

        Internal helper. Callers MUST have already handled any pre-existing
        real file at ``target`` (backup, refuse, etc.) — this helper unlinks
        whatever is there before re-linking.
        """
        if target.is_symlink() or target.exists():
            target.unlink()
        if self._relative_symlinks:
            try:
                rel = os.path.relpath(src, start=target.parent)
                target.symlink_to(rel)
                return
            except ValueError:
                pass  # different drives on Windows — fall back to absolute
        target.symlink_to(src)

    def _unlink_quietly(self, p: Path) -> None:
        try:
            if p.is_symlink() or p.is_file():
                p.unlink()
            elif p.is_dir() and not p.is_symlink():
                shutil.rmtree(p)
        except OSError as e:
            self._warn(f"unlink-fail:{p}", f"could not remove {p}: {e}")

    @staticmethod
    def _path_in(child: Path, parent: Path) -> bool:
        """True if ``child`` is at or below ``parent``. Uses ``is_relative_to``."""
        try:
            return child.resolve(strict=False).is_relative_to(parent.resolve(strict=False))
        except (OSError, ValueError):
            return False

    def _git(
        self,
        *args: str,
        cwd: Path,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        if not shutil.which("git"):
            raise ConfigError("git not found on PATH")
        try:
            return subprocess.run(
                ["git", *args],
                cwd=str(cwd),
                text=True,
                capture_output=True,
                check=check,
            )
        except subprocess.CalledProcessError as e:
            raise ConfigError(
                f"git {' '.join(args)} failed (exit {e.returncode}): "
                f"{e.stderr.strip() or e.stdout.strip()}"
            ) from e

    def _auto_message(self, changes: list[str]) -> str:
        """Generate a short commit message from the change list.

        Subject is imperative + ≤ 72 chars. Body lists changed paths.
        """
        labels = {
            "CLAUDE.md": "CLAUDE.md",
            "settings.json": "settings",
            "settings.local.json": "host settings",
            "memory/": "memory",
            "commands/": "commands",
            "agents/": "agents",
            "skills/": "skills",
            "hooks/": "hooks",
            "prompts/": "prompts",
            "hosts/": "host overlay",
            "plugins/": "plugins",
        }
        seen: list[str] = []
        for line in changes:
            file = line[3:].strip() if len(line) > 3 else line
            for needle, label in labels.items():
                if needle in file and label not in seen:
                    seen.append(label)
        subject = "update " + ", ".join(seen) if seen else "update content"
        if len(subject) > 72:
            subject = subject[:69] + "..."
        body_lines = [f"  {line}" for line in changes[:20]]
        if len(changes) > 20:
            body_lines.append(f"  ... ({len(changes) - 20} more)")
        return f"{subject}\n\nFiles:\n" + "\n".join(body_lines)

    def _warn(self, key: str, msg: str) -> None:
        """Print a warning at most once per ``key`` per ClaudeConfig lifetime."""
        if key in self._warned_keys:
            return
        self._warned_keys.add(key)
        print(f"warning: {msg}", file=sys.stderr, flush=True)
