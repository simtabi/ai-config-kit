"""One class to manage Claude Code's ~/.claude/ via symlinks from a content dir.

Design:
- Single class (ClaudeConfig) with a fluent API.
- JSON config persisted at ~/.config/claude-config/config.json by default;
  every field has a sensible default if config is absent.
- Symlinks files from <content_dir>/claude/* into <target>/* (default ~/.claude).
- Directory symlinks for "auto-grow" subdirs (e.g. memory/) so new files
  appear automatically without re-running install.
- Defence in depth against secrets: refuses to track files matching
  configured patterns (.credentials.json, *.key, *.token, *.pem, *.p12,
  .env, .env.*).
- Operations on the CONTENT dir's git repo (not the tool's repo) —
  ensures personal content stays isolated.
"""

from __future__ import annotations

import fnmatch
import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Errors and result types
# ---------------------------------------------------------------------------


class ConfigError(Exception):
    """Raised on configuration parse, validation, or environment failure."""


@dataclass(frozen=True)
class InstallReport:
    """Outcome of `.install()`."""

    links_created: int = 0
    dir_links_created: int = 0
    already_correct: int = 0
    real_files_backed_up: int = 0
    skipped_via_dir_symlink: int = 0

    def summary(self) -> str:
        return (
            f"installed {self.links_created} link(s), "
            f"{self.dir_links_created} dir link(s), "
            f"{self.already_correct} already-correct, "
            f"{self.real_files_backed_up} backed up, "
            f"{self.skipped_via_dir_symlink} reachable via dir symlink"
        )


@dataclass(frozen=True)
class UninstallReport:
    removed: int = 0

    def summary(self) -> str:
        return f"removed {self.removed} symlink(s); repo files untouched"


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
    tracked_files: list[str] = field(default_factory=list)
    untracked_candidates: list[str] = field(default_factory=list)
    git_clean: bool = True
    git_summary: str = ""

    def to_text(self) -> str:
        lines: list[str] = [
            f"Content dir:  {self.content_dir}",
            f"Target base:  {self.target_base}",
            f"Tracked files: {len(self.tracked_files)}",
        ]
        lines.extend(f"  {p}" for p in self.tracked_files[:30])
        if len(self.tracked_files) > 30:
            lines.append(f"  ... ({len(self.tracked_files) - 30} more)")
        lines.append("")
        lines.append(f"Untracked candidates in {self.target_base}:")
        if self.untracked_candidates:
            lines.extend(f"  {p}" for p in self.untracked_candidates)
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

    def summary(self) -> str:
        parts: list[str] = []
        if self.committed:
            short = (self.commit_sha or "")[:8]
            parts.append(f"committed {short}: {(self.commit_message or '').splitlines()[0]}")
        else:
            parts.append("nothing to commit")
        if self.pushed:
            parts.append("pushed")
        elif self.push_error:
            parts.append(f"push failed: {self.push_error}")
        return "; ".join(parts)


# ---------------------------------------------------------------------------
# The class
# ---------------------------------------------------------------------------


class ClaudeConfig:
    """Manage Claude Code's ~/.claude/ via symlinks from a content directory.

    Construction:
        cfg = ClaudeConfig()                              # defaults
        cfg = ClaudeConfig(content_dir="/path/to/content")
        cfg = ClaudeConfig.from_config()                  # reads config.json
        cfg = (
            ClaudeConfig()
            .with_content_dir("/path/to/content")
            .with_target("/home/x/.claude")
        )

    Operations (all return self for chaining where the result is the side
    effect; methods that produce data return a Report dataclass):

        cfg.init().install().doctor()
        cfg.sync(message="updated rules", push=True)
        cfg.track("/home/x/.claude/skills/foo.md")
        report = cfg.status()
        print(report.to_text())
    """

    # ---- defaults -----------------------------------------------------

    DEFAULT_TARGET: Path = Path.home() / ".claude"
    DEFAULT_CONFIG: Path = Path(
        os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    ) / "claude-config" / "config.json"
    DEFAULT_CONTENT: Path = Path(
        os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    ) / "claude-config" / "content"

    DEFAULT_SECRET_PATTERNS: tuple[str, ...] = (
        ".credentials.json",
        ".credentials.json.*",
        "*.secret",
        "*.key",
        "*.pem",
        "*.p12",
        "*.token",
        ".env",
        ".env.*",
    )
    DEFAULT_IGNORE_PATTERNS: tuple[str, ...] = (
        ".DS_Store",
        "*.swp",
        "*.swo",
        "*.before-claude-config",
    )

    # Subdirectories inside <content>/claude/ that should be symlinked at
    # directory level (so new files inside them auto-appear in ~/.claude/).
    DEFAULT_DIR_SYMLINK_NAMES: tuple[str, ...] = ("memory",)

    # Directories under ~/.claude/ that are normally ephemeral (sessions,
    # caches, etc.) and excluded from status() candidate listings. Becomes
    # interesting only when the user opts in to tracking sessions/history
    # via the include_sessions / include_history flags.
    EPHEMERAL_DIRS: frozenset[str] = frozenset({
        "sessions", "cache", "paste-cache", "shell-snapshots",
        "backups", "tasks", "todos", "telemetry", "statsig", "ide",
        "file-history", "downloads", "plugins", "session-env",
    })

    # Single files at the top of ~/.claude/ that are normally ephemeral.
    EPHEMERAL_FILES: frozenset[str] = frozenset({"history.jsonl"})

    # Environment variables consulted as a precedence layer between
    # an explicit argument and the JSON config / class default.
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
    #
    # Env vars only kick in when nothing more specific was passed — they
    # never override an explicit arg.

    def __init__(
        self,
        content_dir: Path | str | None = None,
        target_base: Path | str | None = None,
        secret_patterns: list[str] | tuple[str, ...] | None = None,
        ignore_patterns: list[str] | tuple[str, ...] | None = None,
        dir_symlink_names: list[str] | tuple[str, ...] | None = None,
        include_sessions: bool = False,
        include_history: bool = False,
    ) -> None:
        # Env var fallbacks when nothing was passed.
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
        base_dirs = (
            dir_symlink_names if dir_symlink_names is not None else self.DEFAULT_DIR_SYMLINK_NAMES
        )
        # When include_sessions is on, sessions/ joins the auto-symlinked dirs.
        if include_sessions and "sessions" not in base_dirs:
            base_dirs = (*base_dirs, "sessions")
        self._dir_syms: tuple[str, ...] = tuple(base_dirs)
        self._include_sessions: bool = include_sessions
        self._include_history: bool = include_history

    @classmethod
    def from_config(cls, config_path: Path | str | None = None) -> ClaudeConfig:
        """Load config from JSON. Falls back to defaults when file is absent.

        Env-var precedence: ``CLAUDE_CONFIG_FILE`` overrides the path
        argument; ``CLAUDE_CONFIG_CONTENT_DIR`` / ``CLAUDE_CONFIG_TARGET``
        override the JSON values for those fields. CLI flags / explicit
        arguments to subsequent fluent setters still win.
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

        # Env vars override JSON for the two fields they cover.
        content = os.environ.get(cls.ENV_CONTENT_DIR) or data.get("content_dir")
        target = os.environ.get(cls.ENV_TARGET_BASE) or data.get("target_base")

        return cls(
            content_dir=content,
            target_base=target,
            secret_patterns=data.get("secret_patterns"),
            ignore_patterns=data.get("ignore_patterns"),
            dir_symlink_names=data.get("dir_symlink_names"),
            include_sessions=bool(data.get("include_sessions", False)),
            include_history=bool(data.get("include_history", False)),
        )

    # ---- fluent setters -----------------------------------------------

    def with_content_dir(self, path: Path | str) -> ClaudeConfig:
        self._content_dir = Path(path).expanduser().resolve()
        return self

    def with_target(self, path: Path | str) -> ClaudeConfig:
        self._target_base = Path(path).expanduser().resolve()
        return self

    def with_secret_patterns(self, patterns: list[str]) -> ClaudeConfig:
        self._secrets = tuple(patterns)
        return self

    def with_ignore_patterns(self, patterns: list[str]) -> ClaudeConfig:
        self._ignores = tuple(patterns)
        return self

    def with_dir_symlinks(self, names: list[str]) -> ClaudeConfig:
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

    # ---- config persistence -------------------------------------------

    def save_config(self, config_path: Path | str | None = None) -> ClaudeConfig:
        """Write current settings to a JSON config file."""
        path = Path(config_path).expanduser() if config_path else self.DEFAULT_CONFIG
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "content_dir": str(self._content_dir),
                    "target_base": str(self._target_base),
                    "secret_patterns": list(self._secrets),
                    "ignore_patterns": list(self._ignores),
                    "dir_symlink_names": list(self._dir_syms),
                    "include_sessions": self._include_sessions,
                    "include_history": self._include_history,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return self

    # ---- init ---------------------------------------------------------

    def init(self, with_examples: bool = True, init_git: bool = True) -> ClaudeConfig:
        """Create the content dir + claude/ subdir; optionally seed examples + git."""
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

        if init_git and not (self._content_dir / ".git").exists():
            self._git("init", "-b", "main", cwd=self._content_dir)

        return self

    # ---- install ------------------------------------------------------

    def install(self, dry_run: bool = False) -> InstallReport:
        """Symlink src_dir/* into target_base/ at matching relative paths.

        Two passes:
        1. Whole-directory symlinks for names in dir_symlink_names (e.g.
           memory/) so new files inside auto-propagate.
        2. Per-file symlinks for everything else. Skips files whose parent
           dir already resolves into src_dir (reachable via dir symlink).
        """
        if not self.src_dir.is_dir():
            raise ConfigError(
                f"Source directory {self.src_dir} does not exist. "
                "Run `.init()` or set a valid content_dir."
            )
        self._target_base.mkdir(parents=True, exist_ok=True)

        links = dirs = correct = backed_up = skipped = 0

        # Pass 1: directory symlinks
        for src in self._dirs_to_symlink():
            rel = src.relative_to(self.src_dir)
            target = self._target_base / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if self._is_correct_link(target, src):
                correct += 1
                continue
            if target.exists() and not target.is_symlink():
                self._warn(f"Real directory at {target} — skipping (use track for files)")
                continue
            if not dry_run:
                self._symlink(src, target)
            dirs += 1

        # Pass 2: file symlinks (skip files whose parent is dir-symlinked into src_dir)
        for src in self._files_to_track():
            rel = src.relative_to(self.src_dir)
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
                self._warn(f"Real file at {target} backed up to {backup.name}")
                backed_up += 1
            if not dry_run:
                self._symlink(src, target)
            links += 1

        return InstallReport(
            links_created=links,
            dir_links_created=dirs,
            already_correct=correct,
            real_files_backed_up=backed_up,
            skipped_via_dir_symlink=skipped,
        )

    # ---- uninstall ----------------------------------------------------

    def uninstall(self) -> UninstallReport:
        """Remove every symlink in target_base that points into src_dir."""
        removed = 0
        for link in self._iter_target_symlinks():
            if str(link.resolve()).startswith(str(self.src_dir)):
                link.unlink()
                removed += 1
        return UninstallReport(removed=removed)

    # ---- track --------------------------------------------------------

    def track(self, path: Path | str) -> ClaudeConfig:
        """Move ``target_base/<path>`` into the content dir + symlink back.

        Handles both regular files and directories (e.g. ``sessions/``).
        For directories, also adds the dir's basename to ``dir_symlink_names``
        so subsequent installs treat it as a single dir-level symlink (new
        files inside auto-propagate without re-running install).

        Check ordering matters — ``is_symlink`` is checked before any
        resolve so a path already managed by this tool reports the right
        error.
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
        p.rename(dest)
        self._symlink(dest, p)

        # If we just moved a directory, make sure future installs treat
        # it as a dir-level symlink (so files added inside auto-propagate).
        if dest.is_dir() and p.name not in self._dir_syms:
            self._dir_syms = (*self._dir_syms, p.name)
            if p.name == "sessions":
                self._include_sessions = True
            elif p.name == "history.jsonl":  # never a dir but kept for symmetry
                self._include_history = True

        # File-level: flag history.jsonl tracking explicitly.
        if dest.is_file() and p.name == "history.jsonl":
            self._include_history = True

        return self

    # ---- doctor -------------------------------------------------------

    def doctor(self) -> DoctorReport:
        """Verify every src file is reachable from target_base via a symlink chain."""
        issues: list[str] = []
        for src in self._files_to_track():
            rel = src.relative_to(self.src_dir)
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
                issues.append(f"wrong resolution: {link} → {resolved} (expected {src})")

        # Orphan symlinks pointing into content dir but src is gone
        for link in self._iter_target_symlinks():
            target_str = os.readlink(link)
            if str(self.src_dir) in target_str and not link.exists():
                issues.append(f"orphan: {link} → {target_str} (target missing)")

        return DoctorReport(issues=issues)

    # ---- status -------------------------------------------------------

    def status(self) -> StatusReport:
        """Report what's tracked, untracked candidates, and git state."""
        tracked = sorted(
            str(p.relative_to(self.src_dir)) for p in self._files_to_track()
        )

        candidates: list[str] = []
        if self._target_base.exists():
            skip_dirs = set(self.EPHEMERAL_DIRS)
            skip_files = set(self.EPHEMERAL_FILES)
            # When sessions/history are explicitly tracked, surface them
            # in the candidates listing if they happen to still live as
            # real files (e.g. before the user runs `track`).
            if self._include_sessions:
                skip_dirs.discard("sessions")
            if self._include_history:
                skip_files.discard("history.jsonl")

            for p in self._target_base.rglob("*"):
                if not p.is_file() or p.is_symlink():
                    continue
                rel = p.relative_to(self._target_base)
                if rel.parts and rel.parts[0] in skip_dirs:
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
            tracked_files=tracked,
            untracked_candidates=candidates,
            git_clean=git_clean,
            git_summary=git_summary,
        )

    # ---- sync ---------------------------------------------------------

    def sync(self, message: str | None = None, push: bool = False) -> SyncReport:
        """git add + commit + optionally push, scoped to content_dir."""
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

        pushed = False
        push_err: str | None = None
        if push:
            r = self._git("remote", "get-url", "origin", cwd=self._content_dir, check=False)
            if r.returncode != 0:
                push_err = "no origin remote configured"
            else:
                pr = self._git("push", "origin", "main", cwd=self._content_dir, check=False)
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
        )

    # ---- internals ----------------------------------------------------

    def _files_to_track(self) -> list[Path]:
        """Files in src_dir matching neither ignore nor secret patterns."""
        if not self.src_dir.exists():
            return []
        out: list[Path] = []
        for p in self.src_dir.rglob("*"):
            if not p.is_file():
                continue
            if any(
                self._matches_ignore(part) or self._matches_secret(part) for part in p.parts
            ):
                continue
            out.append(p)
        return sorted(out)

    def _dirs_to_symlink(self) -> list[Path]:
        """Directories in src_dir whose basename is in dir_symlink_names."""
        if not self.src_dir.exists():
            return []
        return sorted(
            p
            for p in self.src_dir.rglob("*")
            if p.is_dir() and p.name in self._dir_syms
        )

    def _iter_target_symlinks(self) -> list[Path]:
        if not self._target_base.exists():
            return []
        return [p for p in self._target_base.rglob("*") if p.is_symlink()]

    def _is_correct_link(self, target: Path, src: Path) -> bool:
        return target.is_symlink() and Path(os.readlink(target)) == src

    def _parent_dir_resolves_into_src(self, target: Path) -> bool:
        parent = target.parent
        if not parent.exists():
            return False
        try:
            return str(parent.resolve()).startswith(str(self.src_dir))
        except OSError:
            return False

    def _matches_secret(self, name: str) -> bool:
        return any(fnmatch.fnmatch(name, pat) for pat in self._secrets)

    def _matches_ignore(self, name: str) -> bool:
        return any(fnmatch.fnmatch(name, pat) for pat in self._ignores)

    def _symlink(self, src: Path, target: Path) -> None:
        if target.is_symlink() or target.exists():
            target.unlink()
        target.symlink_to(src)

    def _git(
        self,
        *args: str,
        cwd: Path,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        if not shutil.which("git"):
            raise ConfigError("git not found on PATH")
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            text=True,
            capture_output=True,
            check=check,
        )

    def _auto_message(self, changes: list[str]) -> str:
        """Generate a commit message from the staged change list."""
        kinds = {
            "CLAUDE.md": "CLAUDE.md",
            "settings.json": "settings",
            "memory": "memory",
            "skills": "skills",
        }
        seen: list[str] = []
        for line in changes:
            file = line[3:] if len(line) > 3 else line
            for needle, label in kinds.items():
                if needle in file and label not in seen:
                    seen.append(label)
        subject = "update " + ", ".join(seen) if seen else "update content"
        body = "\n".join("  " + line for line in changes[:20])
        if len(changes) > 20:
            body += f"\n  ... ({len(changes) - 20} more)"
        return f"{subject}\n\nFiles:\n{body}"

    @staticmethod
    def _warn(msg: str) -> None:
        print(f"warning: {msg}", flush=True)
