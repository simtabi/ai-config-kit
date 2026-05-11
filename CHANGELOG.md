# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — Initial release

### Added
- Single `ClaudeConfig` Python class with fluent API for managing
  Claude Code's `~/.claude/` via symlinks from a versioned content
  directory.
- Subcommands: `init`, `install`, `uninstall`, `sync`, `track`,
  `status`, `doctor`.
- JSON config at `~/.config/claude-config/config.json` (XDG-aware).
  Every field optional, defaults applied for anything missing.
- Three-layer precedence — CLI flags > env vars
  (`CLAUDE_CONFIG_FILE`, `CLAUDE_CONFIG_CONTENT_DIR`,
  `CLAUDE_CONFIG_TARGET`) > JSON config > class defaults.
- Opt-in Claude sessions + history tracking via `include_sessions` /
  `include_history` config fields (or `.with_sessions(True)` /
  `.with_history(True)` fluent setters). Off by default — these
  paths grow fast and the user should choose to ingest them.
- `track` accepts both files **and directories**. For a directory,
  it moves the dir into content + creates a directory-level symlink
  + adds the dir's basename to `dir_symlink_names` so subsequent
  files inside auto-propagate.
- Defence-in-depth secret guards via configurable
  `secret_patterns` — refuses to track or symlink matching files.
  `init` pre-populates `.gitignore` with the same patterns.
- Directory-level symlinks (configurable via `dir_symlink_names`,
  defaults to `memory`) so new files inside auto-propagate without
  re-running `install`.
- Idempotent `install` — re-running reports already-correct counts;
  collisions with real files back up to `<file>.before-claude-config`.
- `track` workflow: move a real file into the content dir + replace
  original with absolute symlink.
- `doctor` walks every source file and validates the symlink chain
  via `realpath`-style resolution (handles file-level and dir-level
  symlinks transparently).
- Pure stdlib — no runtime dependencies beyond Python 3.10+.
- PEP 561 typed (`py.typed` ships with the wheel).
- CLI installable via `pip` / `pipx` / `uv tool install`.

[0.1.0]: https://github.com/simtabi/claude-configs/releases/tag/v0.1.0
