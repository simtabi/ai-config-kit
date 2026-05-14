# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Renamed

- **Project: `claude-configurator` → `ai-configurator`.** Hard rename
  (no shim, no backwards compat). Python module
  `claude_configurator` → `ai_configurator`. CLI command
  `claude-configurator` → `ai-configurator`. Wheel + sdist name
  `claude-configurator` → `ai-configurator`. PyPI page will live at
  `pypi.org/project/ai-configurator/` on next release.
- Reason: the configurator now ships rules for any AI coding agent,
  not just Claude. `claude-best-practices` is one pack; future
  vendors (Codex, Cursor, Cline, Windsurf, Aider) get their own.
- **Unchanged for back-compat**: the on-disk content directory
  remains at `~/.config/claude-config/` (path predates the rename;
  renaming would orphan every existing install). The
  `*.before-claude-config` backup-file suffix also stays.
- `SPEC.md` moved from repo root to `docs/SPEC.md` per the new
  docs-structure standard.

### Added — four new auto-applied decision packs

- **`humanistic-style`** (auto-applied): strips AI tells from prose
  and codifies code-comment conventions. Ships a banned-phrase list
  (`delve into`, `leverage`, `robust and scalable`, em-dash sandwich,
  etc.), PHPDoc / JSDoc / Sphinx doc-block templates, SOLID / DRY /
  KISS / fluent-chain reminders. Two new slash commands:
  `/audit-prose` and `/audit-docblocks`.
- **`docs-structure`** (auto-applied): industry-standard repo layout.
  One authoritative `README.md` at root; every other prose file
  under `docs/`. Required-files set per Simtabi-org rules. Two slash
  commands: `/audit-docs-structure` and `/migrate-readmes-to-docs`.
- **`mcp-best-practices`** (auto-applied): Model Context Protocol
  configuration. Cited from `code.claude.com/docs/en/mcp`. Covers
  settings.json + `.mcp.json` scopes, version pinning, secrets
  hygiene, safe-to-trust server list. Two slash commands:
  `/audit-mcp-config` and `/add-mcp-server`.
- **`safety-net-commits`** (auto-applied): prompts the user to
  commit a checkpoint at safe moments (before destructive ops,
  after milestones, at session end). Honours the standing "no
  commit without an explicit verb" rule. Two slash commands:
  `/checkpoint-now` and `/review-changes`.

### Changed

- `DEFAULT_DECISIONS_ON_INIT` now includes 9 packs (was 5):
  `script-generation-pattern`, `fetch-canonical-pattern`,
  `session-protocol`, `docker-multiarch`, `claude-best-practices`,
  `humanistic-style`, `docs-structure`, `mcp-best-practices`,
  `safety-net-commits`. The `core` pack stays opt-in.
- `decisions list` now shows 10 bundled packs (1 opt-in + 9 auto).

### Added — auto-reconcile-on-upgrade

- `ClaudeConfig.reconcile()` — compares the package version against
  `last_applied_version` stored in the JSON config. On mismatch,
  applies every pack in `DEFAULT_DECISIONS_ON_INIT` non-clobberingly,
  so users who `pip install --upgrade ai-configurator` automatically
  pick up new packs without re-running `init`. Writes the new version
  back to disk.
- `ClaudeConfig.reconcile_if_enabled()` — CLI-startup helper; honours
  `auto_reconcile` flag + skips when no JSON config is loaded.
- `ai-configurator reconcile [--force]` — explicit subcommand for
  manual or scripted use.
- CLI auto-invokes reconcile on every command. Prints a single-line
  notice to stderr when an upgrade actually happened.
- New `auto_reconcile` config field (default `true`). Opt-out path
  for users who manage packs manually.
- `ReconcileReport` dataclass exported at the package surface.

### Added — `claude-best-practices` decision pack (auto-applied)

- Distilled from the live <https://code.claude.com/docs> as of
  May 2026. Every claim cites a `code.claude.com` URL so future
  agents can verify against the official source.
- Ships:
  - `CLAUDE.md.claude-best-practices.fragment` — global rules:
    200-line size guidance, hierarchy (managed/user/project/local),
    `@path` imports, `.claude/rules/` with `paths:` frontmatter,
    skills replacing custom slash commands, AGENTS.md compat,
    hooks vs CLAUDE.md, auto memory, anti-patterns, HTML-comment
    trick.
  - `commands/audit-claude-md.md` — `/audit-claude-md` slash command
    that audits an existing CLAUDE.md against the rules.
  - `commands/init-rules.md` — `/init-rules` slash command that
    proposes a `.claude/rules/` split when CLAUDE.md exceeds the
    200-line guidance.
- 4 new tests covering pack discovery, init auto-application, and
  documentation citation integrity (every URL in the fragment
  must point at `code.claude.com`).

### Added
- New decision pack **`docker-multiarch`** (auto-applied on `init`):
  ships a `CLAUDE.md` fragment + `/docker-multiarch-check` slash
  command. The fragment **self-gates** — explicitly tells the model
  to skip its rules if the current project has no `Dockerfile` /
  `docker-compose.yml`. When Docker IS present: every image must
  build for both `linux/amd64` and `linux/arm64` (Apple Silicon, AWS
  Graviton, ARM SBCs all run the same image). The slash command
  audits an existing Dockerfile + CI for multi-arch readiness.
- New decision pack **`session-protocol`** (auto-applied on `init`):
  ships a `CLAUDE.md` fragment + five slash commands
  (`/session-start`, `/session-end`, `/track-progress`,
  `/research-source`, `/clarify`) that codify a disciplined session
  shape — audit on start, track progress + log failures + research
  before guessing during work, self-improve on end. Anti-hallucination
  throughout.
- New `SPEC.md` at the repo root, mirroring the sibling
  `get-installer/SPEC.md` pattern: identity, mission, current state,
  7 phases, audit checklist, session protocol, agent-loop instructions.
- 4 new tests verifying the pack ships in the wheel and is
  auto-applied by `init`.

### Changed
- `DEFAULT_DECISIONS_ON_INIT` now includes `session-protocol` and
  `docker-multiarch` alongside `script-generation-pattern` and
  `fetch-canonical-pattern`.
- Added `MANIFEST.in` (belt-and-braces for sdist-consuming tools
  that pre-date the `pyproject.toml`-only era).

## [0.2.0] — 2026-05-14

### Installer (new, ships in this release)

- `installer/` folder: a **reusable, registry-driven installer** for
  Simtabi dev tools. Stdlib-only Python core (`installer/core/`),
  POSIX shell + PowerShell bootstrap launchers (`installer/bootstrap/`),
  JSON registry of products + versions (`installer/registry.json`),
  JSON Schema (`installer/schemas/install.schema.json`), and a 43-case
  pytest suite (`installer/tests/`).
- **Registry format (schema v2)**: many products, many versions per
  product, each with a `status` (`current` / `deprecated` /
  `unsupported` / `yanked`). The installer validates the product +
  version selector, refuses yanked releases unconditionally, refuses
  unsupported without `--allow-unsupported`, and warns on deprecated.
- **One-liner UX**: `sh -c "$(curl -fsSL .../install.sh)"` or
  `irm .../install.ps1 | iex`. Bootstrap layer verifies Python ≥ 3.10
  is on PATH, downloads `installer.py` + `registry.json` into a
  0700-mode temp dir, optionally SHA256-pins `installer.py`, hands
  off to Python.
- **Garbage collector**: `Journal` records every state-changing action
  with an `undo` callback. `SIGINT` / `SIGTERM` / unhandled exception
  triggers reverse-order rollback. Worst-case the installer leaves the
  machine in the state it found it.
- **Configurable rate-limiting + DDoS protection**: `rate_limits`
  block in the registry caps retries, sets exponential backoff
  with jitter, enforces a wall-clock deadline, respects HTTP 429
  Retry-After.
- **Access control**: `access_control.allowed_origins` is an https://
  prefix allowlist; Python-side fetches refuse anything else.
  `log_mode` / `tmp_mode` set 0600 on the installer's own files;
  `O_CREAT | O_EXCL` prevents TOCTOU symlink hijacks.
- **Refuses to run as root / Administrator** by default. Override only
  via explicit `--allow-root` flag.
- **Prompts** in `registry.json` ask the user yes/no, string, or
  choice questions; `post_install` commands can gate on the answers
  via `"if": "key=value"` (DRY — no hardcoded special cases).
- **Python bootstrap** via `--with-python` flag installs Python ≥
  required version via `uv python install` when missing (does not
  touch system Python).
- **Independence**: zero changes to the parent project's
  `pyproject.toml`. The installer is **vendorable** — copy
  `installer/` into any project, swap `registry.json`, ship.



### Renamed
- Package: `claude-config` → **`ai-configurator`**.
- Python module: `claude_config` → `ai_configurator`.
- CLI: `claude-config` → `ai-configurator`.
- The on-disk config path stays `~/.config/claude-config/` (unchanged
  XDG dotfile location). The backup-file suffix
  `*.before-claude-config` stays (marker on disk for existing installs).

### Structure
- Bundled data moved from `src/claude_config/data/decisions/` to
  `src/ai_configurator/resources/decisions/`.
- Per-pack `README.md` → `details.md` to disambiguate from the
  single authoritative top-level README. `decisions show` reads
  `details.md`.
- Docs index `docs/README.md` removed — folded into the top-level
  README's TOC.
- `data/decisions/README.md` (pack-author schema) moved to
  `docs/decisions.md`.
- New `docs/decisions.md` documents the pack catalogue + manifest
  schema for authors.
- README redesigned with a TOC linking every subdoc and command-doc
  anchor.

### Added
- `bootstrap` subcommand wraps init + install + optional sync --push +
  doctor in one validated, prompted sequence. Idempotent. Useful for
  first-time setup on a fresh machine.
- `bootstrap --no-decisions` flag — skip the auto-applied decision
  packs (mirrors `init --no-decisions`).
- `repair` now restores `*.before-claude-config` backups whose
  symlink got broken (the source file disappeared from the content
  dir). Mirrors `uninstall`'s restore behaviour.
- `init`'s step summary now lists which decision packs were applied
  (visible in both CLI output and `BootstrapStep.detail`).
- `pyproject.toml` classifiers now include
  `Operating System :: Microsoft :: Windows`.
- `fetch` subcommand: disk-to-disk download of canonical / upstream
  text files. Pure Python (`urllib.request`), HTTPS-only by default,
  atomic write, idempotent, size cap, sha256 verification, UTF-8
  validation. **Body bytes never enter the response stream** — solves
  the content-filter block that hits when the model's file-write tool
  tries to emit a long well-known text (LICENSE, code of conduct, etc.).
- New decision pack `fetch-canonical-pattern` — slash command +
  CLAUDE.md fragment that teaches the model to use `ai-configurator fetch`
  (or `curl -o` as fallback) and to never reach for file-write/edit
  tools on canonical files. Auto-applied on `init`.
- `validate` now checks the running Python version meets `MIN_PYTHON`
  (3.10) and warns if no `python3` is on PATH for generator scripts.
- `cleanup` subcommand removes `.DS_Store` litter, broken symlinks,
  orphan `*.before-claude-config` backups. Dry-run by default; `--apply`
  to delete. `--include-ephemeral` also clears paste-cache / file-history
  / todos / etc. under target.
- `list` subcommand prints a grouped tree of content_dir: top-level
  config files, auto-grow dirs, plugin config files, per-project
  memory, host overlays, opt-in tracked dirs, other.
- `view` subcommand prints the contents of a tracked file with
  optional line numbers. Refuses path-traversal.
- `validate` subcommand: pre-flight environment check (git on PATH,
  parents writable, target not a regular file). Used internally by
  `bootstrap`.
- `decisions` subcommand: `list`, `show`, `apply`. Bundled global
  decision packs ship with the wheel and can be applied into the
  content dir. Initial packs: `core` (skeleton CLAUDE.md +
  settings.json) and `script-generation-pattern` (instructs the model
  to use a generator script for many-file or content-filter-risky
  tasks).
- `repair` subcommand: heals a broken install by running cleanup +
  install in sequence. Reports per-action detail.
- Host-overlay pattern: files under
  `<content>/claude/hosts/<hostname>/X` install as `<target>/X` on the
  matching host only. `doctor` flags foreign-host symlinks.
- `--yes` global flag skips all confirmation prompts.
- `--no-restore` flag on `uninstall` keeps the `*.before-claude-config`
  backups instead of restoring them.

### Changed
- `dir_symlink_names` default now includes `commands`, `agents`,
  `skills`, `hooks`, `prompts` in addition to `memory`. Files added to
  these dirs after install auto-propagate without re-running `install`.
- `secret_patterns` default expanded to cover SSH keys (`id_rsa*`,
  `id_ed25519*`, `id_ecdsa*`), `*.pfx`, `*.kdbx`, `*.netrc`, `.netrc`,
  `.npmrc`, `.pypirc`.
- `save_config` merges with the on-disk JSON rather than overwriting —
  unknown future fields are preserved.
- Symlinks are now relative by default (`relative_symlinks: true`).
  Survives a content-dir relocation. Toggle via `with_relative_symlinks`.
- `init` auto-applies the `script-generation-pattern` decision pack by
  default. `--no-decisions` (or `apply_decisions=()` programmatically)
  opts out. Non-clobbering: existing files in content_dir are skipped.
- `sync --push` detects current branch + first remote instead of
  hard-coding `origin main`. Works with non-default branches / remotes.
- `track` uses `shutil.move` for cross-device safety; persists state
  changes (e.g., new dir_symlink, `include_sessions=true`) to the JSON
  config when one was loaded.
- `uninstall` restores `*.before-claude-config` backups by default
  (was: orphaned them).
- Plugin config files (`plugins/blocklist.json`,
  `plugins/known_marketplaces.json`) tracked by default;
  `plugins/marketplaces/` cache still excluded.
- `~/.claude/projects/<slug>/` walk now restricted: only `memory/` is
  tracked under each project slug. Stray files at the slug root are
  skipped with a warning.
- `_auto_message` commit messages now follow imperative ≤ 72-char
  subject convention.
- `__version__` reads from `importlib.metadata` instead of a duplicate
  string literal.

### Fixed
- Path containment checks use `Path.is_relative_to()` instead of
  string `startswith()` (was fragile to trailing slashes / case).
- `_iter_target_symlinks` no longer walks into directory symlinks
  (avoids re-scanning the content tree).
- `_git` failures wrap `CalledProcessError` as `ConfigError`, giving
  the CLI a clean error path.
- `RUNTIME_DIRS` now includes `plans/` (was tracked accidentally).

### Documentation
- README slimmed to tagline + install + command index + doc links.
- `docs/` tree created: `installation.md`, `configuration.md`,
  `architecture.md`, `release.md`, `shipping-checklist.md`,
  `tools/ai-configurator.md`.
- `.github/` scaffolding added: `workflows/{ci,release}.yml`,
  `dependabot.yml`, issue templates, PR template.
- `Makefile` with `check / lint / test / format / build / clean` targets.

### Security
- `decisions apply` refuses to write a file whose destination matches
  a secret pattern.
- `view` refuses path-traversal (`../`).

[0.2.0]: https://github.com/simtabi/claude-configs/releases/tag/v0.2.0

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
