# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.0] - 2026-05-16

### Added

- **Claude Code permission profiles** (`7cf9cc4`): six built-in
  profiles ship as JSON resources: `global` (inspection-only
  baseline), `python`, `laravel`, `node`, `go`, `mixed` (default).
  Each project profile extends `global`; the resolver unions
  allow + deny lists and de-duplicates while preserving order.

  New CLI verbs:
  - `ai-config-kit profiles list [--json]`
  - `ai-config-kit profiles show [NAME]`
  - `ai-config-kit profiles apply [NAME] [--scope project|global] [--apply]`

  Library: `ClaudeConfig.profiles_list()`, `profiles_show()`,
  `profiles_apply()`. Existing `settings.json` is backed up to
  `.before-profile` before overwrite. Audit-logged event:
  `profiles_apply`.

  See `docs/profiles.md` for the full design + design principles
  (deny beats allow, publishing always prompts, global is
  inspection-only).

- **S3 sync scaffold** (Phase E, Round 3 #18, `9976632`): opt-in
  `[s3]` extras + `ClaudeConfig.sync_to_s3` skeleton. Dry-run
  returns; apply raises NotImplementedError pointing at the
  pending auth-design ADR.

### Changed

- **Refactor C1** (`ada41bb`): decisions data types extracted to
  `ai_config_kit/decisions.py` (150 lines moved out of
  manager.py). Public API preserved via re-export.

- **Integration tests** (C6, `4b70c83`): new `tests/test_integration.py`
  with 8 real-FS symlink scenarios.

- **Shared session-protocol template** (C5, `af07e92`): the
  duplicated SPEC §"Session protocol" + "Audit checklist" sections
  now have a canonical source at
  `docs/session-protocol.template.md`.

## [0.5.0] - 2026-05-16

### Project rename

- GitHub repo: `simtabi/claude-configs` → `simtabi/ai-configurator`
  → `simtabi/ai-config-kit` (this is final).
- PyPI dist: `ai-configurator` → `aicfg` → `ai-config-kit` (this is final).
- CLI binary, Python module, all import paths: `ai-configurator` /
  `ai_configurator` → `ai-config-kit` / `ai_config_kit`.
- All `pip install ai-configurator` invocations in docs become
  `pip install ai-config-kit`.

### Added — SPEC §4 phases

- **Phase A** — `settings validate`: lightweight allowlist + shape
  validation of `<src_dir>/settings.json`. Forward-compatible
  warnings for unrecognised keys.
- **Phase B** — `decisions install <https-url>`: fetch + extract
  + apply a community/private decision pack from a tarball.
  HTTPS-only, 5MB cap, optional `--sha256` verification before
  extract, path-traversal guard, audit-logged.
- **Phase C** — `memory clean --older-than DAYS`: prune project
  memory dirs older than the freshness threshold. Dry-run by
  default; `--apply` deletes and audits.
- **Phase D** — `settings migrate`: framework for schema-drift
  migrations. v0.5 ships an empty migration table; future schema
  drift gets a one-entry change.
- **Phase F** — `install --only NAME[,NAME...]`: restrict install
  to specific top-level entries (e.g., `--only commands,agents`).
- **Phase G** — JSONL audit log: every mutating verb appends an
  event to `<content_dir>.parent/audit.log` with `ts`, `event`,
  `content_dir`, `target`, and per-event fields.

### Added — SPEC §5 issues closed

- **C2** — `--json` output on read-only commands: `status`,
  `doctor`, `validate`, `decisions list/show` now emit a single
  JSON document via the new `.to_json_dict()` methods.
- **C3** — `bootstrap --remote URL` validated against a transport
  allowlist (https / http / ssh / git / `git@` / file) and a
  shell-metachar blocklist before being passed to git.
- **C4** — `decisions apply --force` on a TTY shows a unified diff
  + y/N prompt before clobbering files. `--yes` / `--dry-run` /
  non-tty bypass.

### Changed

- Node.js 20-deprecated actions bumped past the 2026-06-02 cutoff.
- CodeQL workflow added (weekly + push/PR scan).
- README badges (CI, PyPI, Python, license).
- Repository security toggles enabled.

### Tests

- 241 → 276 (+35 across the session).

## [0.4.2] - 2026-05-15

### Added: `capacity` verb + `ClaudeConfig.capacity_check` Python API

The `/capacity-check` slash command shipped in 0.4.1 teaches an
agent how to do the timezone-aware lookup. This release adds the
programmatic counterpart so cron jobs, dashboards, SDKs, and CI
gates can consume the same verdict structurally.

- `ClaudeConfig.capacity_check(timezone=None, providers=None) ->
  CapacityVerdict`: computes per-provider GREEN/AMBER/UNKNOWN
  verdict against the user's local time.
- Two new public types: `CapacityVerdict` and `ProviderCapacity`.
- Timezone resolution: explicit arg > `$TZ` env > resolved
  `/etc/localtime` symlink target > `UTC`.
- Window parser handles seasonal qualifiers (`(winter)`/`(summer)`
  ignored), midnight-wrapping windows (`22:00-06:00`), and the
  `all weekend` clause.
- Data load order: user-editable `<content_dir>/claude/data/off-peak-windows.json`
  first, then package-resource fallback so the verb works before
  `init` has dropped the file into the content dir.
- New CLI verb: `ai-config-kit capacity [--timezone IANA_ZONE]
  [--provider NAME ...]`. Exit `0` unless every reported provider
  is RED (a deferral signal for CI; currently never produced by
  the synchronous path: hot-day detection lives in the slash
  command).
- 11 new manager tests + 2 CLI tests. 229 -> 241 pass; ruff +
  mypy clean.

## [0.4.1] - 2026-05-14

### Added: `model-overload-resilience` decision pack (auto-applied)

Universal playbook for handling AI-model provider overload across
Anthropic (529), OpenAI / Codex / Azure (503), Google / Cohere /
Mistral (429 + 503), and local backends (Ollama, vLLM). Multi-
provider from day one; no Claude-specific assumptions.

Pack ships:

- `CLAUDE.md.model-overload-resilience.fragment`: the 7-point
  playbook (retry with backoff + jitter, respect `Retry-After`,
  cap concurrency, fallback model, prompt caching, off-peak
  scheduling, Batch API), the 529-vs-429 distinction, a
  per-provider status-code table, when-not-to-retry guidance, and
  an inline minimum Python pattern.
- `commands/capacity-check.md`: `/capacity-check` slash command
  that detects the user's IANA timezone (via `/etc/localtime` or
  `$TZ`), reads `data/off-peak-windows.json`, and prints a per-
  provider peak/off-peak verdict for the user's local time. Hot-day
  flags (post-model-launch, US-quarter-end, active incidents)
  override the clock to AMBER/RED. Informational only; never
  reschedules cron / changes registry without user confirmation.
- `data/off-peak-windows.json`: structured data with off-peak
  windows for 7 providers across 17 IANA timezones. JSON so cron
  jobs, CI, and dashboards can consume programmatically without
  parsing Markdown. Includes shift-modifiers (US holiday weeks,
  quarter-end, post-launch heat).
- `scripts/api-retry.py`: stdlib-only Python retry helper.
  Provider-agnostic dispatch via `PROVIDER_RETRY_CODES` dict
  (anthropic = {429, 529}; openai/codex/azure = {429, 503};
  google/cohere/mistral = {429, 503}; local = {503}; generic =
  all of them). Extracts status via the SDK shape used by
  anthropic, openai, httpx, requests. Honours `Retry-After` in
  either delta-seconds or RFC 7231 HTTP-date form via stdlib
  `email.utils.parsedate_to_datetime`. Includes `OverloadError`
  with per-attempt history for clear failure surfacing. `__main__`
  block self-tests a 529-then-success retry path (subprocess-
  invoked in the test suite).

Tests: 17 new (parametrized pack-listed + 7 focused). 220 -> 229
pass; ruff + mypy clean.

`DEFAULT_DECISIONS_ON_INIT` grows from 12 to 13. `decisions list`
now shows 14 (1 opt-in + 13 auto).

## [0.4.0] - 2026-05-14

### Added: render-env.sh post-write mode verification

`chmod 600` on the rendered output file can silently no-op on
filesystems that don't honour POSIX mode bits (FAT, exFAT, some
SMB mounts, certain Docker bind-mounts). After write, the script
reads back the actual mode via `stat -c` (GNU) or `stat -f` (BSD)
and emits a loud `WARNING` to stderr if the file ended up
world-readable. Belt-and-suspenders for secret protection.

### Added: permission self-heal (`heal` verb, `doctor --heal` shortcut)

- `ai-config-kit heal [--yes] [--dry-run]`: audits permission +
  mode-bit issues on the content dir and (with `--yes`) applies
  fixes. Four issue classes:
  - `sensitive-mode-too-open`: a secret-pattern file with mode
    looser than `0o600` (narrows to `0o600`).
  - `world-writable`: any path with `S_IWOTH` set (narrows to
    `0o644` / `0o755`).
  - `not-executable`: a shell script under `scripts/` without
    user-exec (sets `0o755`).
  - `orphan-owner`: a file owned by a different uid. Always
    flagged, never fixed. The tool refuses to escalate.
- `ai-config-kit doctor --heal`: doctor + permission audit in one
  shot, dry-run only.
- New public types: `PermissionFinding`, `HealReport`. Defaults to
  dry-run; CI-friendly nonzero exit when findings exist but no
  `--yes`.
- Symlinks are skipped (their mode bits are ignored by most
  filesystems and `chmod()` follows them); `.git/` subtrees are
  skipped entirely.

11 new manager tests + 3 CLI tests. 206 → 220.

## [0.3.0] - 2026-05-14

### Added: Homebrew tap distribution channel

- `templates/homebrew-formula/ai-config-kit.rb`: ready-to-ship
  live formula for the `simtabi/homebrew-tap` repository. Stdlib-only,
  depends_on python@3.13. The `test do` block exercises:
  - `--version` returns the expected version string.
  - `decisions list` reports the bundled-packs surface (proves the
    wheel preserved its resources directory).
  - `--help` includes the multi-vendor verbs `compose-agents-md` and
    `project-install`.
- `docs/distribution/homebrew.md`: one-time tap setup (`brew tap-new`,
  `brew create --python`, `brew update-python-resources`) and the
  release-time auto-bump workflow.
- SPEC adds Phase I "Homebrew tap distribution" (✔ this release).

### Added: multi-vendor wiring (`VendorAdapter` + four slices)

The configurator now actually targets vendors beyond `claude-code`.
The data model is in `VendorAdapter` / `ProjectFile`; the verbs are
`compose-agents-md`, `project-install`, and an extended `install`.

- **`VendorAdapter` registry**: each known vendor declares its
  `global_target` (path under `$HOME` for vendors that support it)
  and `project_files` (per-project paths it reads). Adapter style is
  one of `copy` / `symlink-canonical` / `import-stub`.
- **Adapters wired**: `claude-code` (global only),
  `aider` (project `AGENTS.md`), `cursor` (project `.cursorrules` +
  global `~/.cursor/rules`), `windsurf` (project `.windsurfrules`),
  `copilot` (project `.github/copilot-instructions.md`),
  `codex` (project `AGENTS.md` + global `~/.codex/instructions`),
  `cline` (project `.clinerules`). All non-`claude-code` adapters
  copy from the canonical `AGENTS.md`.
- **`VENDOR_STATUS` promotions**: every CLI-based vendor in
  `SUPPORTED_VENDORS` is now `current`. Only `claude` (web/desktop,
  partial CLAUDE.md sharing) remains non-current.
- **New verb `ai-config-kit project-install <path>`**: writes
  per-vendor files into a project repo. Respects the configured
  vendors list when `--vendor` isn't passed. Skips existing files
  unless `--force`. Reports failed / skipped / written per file.
- **New verb `ai-config-kit compose-agents-md`**: synthesizes a
  single `AGENTS.md` from `CLAUDE.md` plus every
  `CLAUDE.md.*.fragment` (decision-pack output, sorted). Output
  starts with `<!-- ai-config-kit:autogenerated -->`; future
  composes overwrite when the marker is present and refuse to clobber
  hand-edited files when it's not.
- **Auto-compose on demand**: `project_install` lazy-composes
  `AGENTS.md` if it isn't on disk yet (disable with
  `auto_compose=False`). `install` does the same for vendor
  global-target writes.
- **`install` extension**: drops the canonical `AGENTS.md` into each
  configured non-`claude-code` vendor's `global_target` (currently
  only cursor benefits). New `InstallReport.global_writes` field
  reports per-vendor writes.
- **Instance-level adapter overrides**:
  `cfg.with_vendor_adapter(name, adapter)` redirects an adapter on
  this instance only. Used by tests to point `global_target` at a
  tmp_path so the suite never writes to the real `~/.cursor/rules/`.
- 24 new tests; total moves from 176 to 200.

### Renamed

- **Project: `claude-configurator` → `ai-config-kit`.** Hard rename
  (no shim, no backwards compat). Python module
  `claude_configurator` → `ai_config_kit`. CLI command
  `claude-configurator` → `ai-config-kit`. Wheel + sdist name
  `claude-configurator` → `ai-config-kit`. PyPI page will live at
  `pypi.org/project/ai-config-kit/` on next release.
- Reason: the configurator now ships rules for any AI coding agent,
  not just Claude. `claude-best-practices` is one pack; future
  vendors (Codex, Cursor, Cline, Windsurf, Aider) get their own.
- **Unchanged for back-compat**: the on-disk content directory
  remains at `~/.config/claude-config/` (path predates the rename;
  renaming would orphan every existing install). The
  `*.before-claude-config` backup-file suffix also stays.
- `SPEC.md` moved from repo root to `docs/SPEC.md` per the new
  docs-structure standard.

### Added: four new auto-applied decision packs

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
- **`docker-env-interpolation`** (auto-applied): ships a POSIX
  shell script (`scripts/render-env.sh`) that flattens layered
  `.env` files into a fully-resolved output. Handles `$VAR`,
  `${VAR}`, `${VAR:-default}`, `${VAR-default}`, `${VAR:?error}`,
  `${VAR?error}`, and `$$` escapes. Layered precedence matches
  Docker Compose: shell env > `--local` > `--input` > `--example`.
  For non-Docker consumers of `.env`, CI shells, and pre-deploy
  validation. Shell, not Python, because Docker can't natively
  invoke Python scripts. Includes `/render-env` slash command.
- **`vendor-portability`** (auto-applied): AGENTS.md canonical
  pattern for cross-vendor portability between Claude / Codex /
  Cursor / Cline / Aider / Windsurf / Copilot.
- **`polling-discipline`** (auto-applied): stops the chained-sleep
  polling anti-pattern before the Claude Code runtime blocks it.
  Documents the three correct primitives (Monitor + until-loop,
  Bash `run_in_background`, `ScheduleWakeup`) and which to reach
  for in each waiting scenario. Ships a `/wait-for` slash command
  that proposes the right primitive without executing. Reaches
  existing installs on next CLI run because the pack is brand-new
  and reconcile's non-clobbering apply ships new dest files freely.

### Added: decision-pack `mode` field

- Each entry in a pack's `manifest.json::files` may now specify
  `"mode": "0755"` (or any octal string). Applied with `chmod`
  after copy. Used by `docker-env-interpolation` so the rendered
  `render-env.sh` lands executable. Default (mode omitted) leaves
  the dest at umask.

### Changed

- `DEFAULT_DECISIONS_ON_INIT` now includes 12 packs (was 9):
  `script-generation-pattern`, `fetch-canonical-pattern`,
  `session-protocol`, `docker-multiarch`,
  `docker-env-interpolation`, `claude-best-practices`,
  `humanistic-style`, `docs-structure`, `mcp-best-practices`,
  `safety-net-commits`, `vendor-portability`,
  `polling-discipline`. The `core` pack stays opt-in.
- `decisions list` now shows 13 bundled packs (1 opt-in + 12 auto).

### Added: auto-reconcile-on-upgrade

- `ClaudeConfig.reconcile()`: compares the package version against
  `last_applied_version` stored in the JSON config. On mismatch,
  applies every pack in `DEFAULT_DECISIONS_ON_INIT` non-clobberingly,
  so users who `pip install --upgrade ai-config-kit` automatically
  pick up new packs without re-running `init`. Writes the new version
  back to disk.
- `ClaudeConfig.reconcile_if_enabled()`: CLI-startup helper; honours
  `auto_reconcile` flag + skips when no JSON config is loaded.
- `ai-config-kit reconcile [--force]`: explicit subcommand for
  manual or scripted use.
- CLI auto-invokes reconcile on every command. Prints a single-line
  notice to stderr when an upgrade actually happened.
- New `auto_reconcile` config field (default `true`). Opt-out path
  for users who manage packs manually.
- `ReconcileReport` dataclass exported at the package surface.

### Added: `claude-best-practices` decision pack (auto-applied)

- Distilled from the live <https://code.claude.com/docs> as of
  May 2026. Every claim cites a `code.claude.com` URL so future
  agents can verify against the official source.
- Ships:
  - `CLAUDE.md.claude-best-practices.fragment`: global rules:
    200-line size guidance, hierarchy (managed/user/project/local),
    `@path` imports, `.claude/rules/` with `paths:` frontmatter,
    skills replacing custom slash commands, AGENTS.md compat,
    hooks vs CLAUDE.md, auto memory, anti-patterns, HTML-comment
    trick.
  - `commands/audit-claude-md.md`: `/audit-claude-md` slash command
    that audits an existing CLAUDE.md against the rules.
  - `commands/init-rules.md`: `/init-rules` slash command that
    proposes a `.claude/rules/` split when CLAUDE.md exceeds the
    200-line guidance.
- 4 new tests covering pack discovery, init auto-application, and
  documentation citation integrity (every URL in the fragment
  must point at `code.claude.com`).

### Added
- New decision pack **`docker-multiarch`** (auto-applied on `init`):
  ships a `CLAUDE.md` fragment + `/docker-multiarch-check` slash
  command. The fragment **self-gates**: explicitly tells the model
  to skip its rules if the current project has no `Dockerfile` /
  `docker-compose.yml`. When Docker IS present: every image must
  build for both `linux/amd64` and `linux/arm64` (Apple Silicon, AWS
  Graviton, ARM SBCs all run the same image). The slash command
  audits an existing Dockerfile + CI for multi-arch readiness.
- New decision pack **`session-protocol`** (auto-applied on `init`):
  ships a `CLAUDE.md` fragment + five slash commands
  (`/session-start`, `/session-end`, `/track-progress`,
  `/research-source`, `/clarify`) that codify a disciplined session
  shape: audit on start, track progress + log failures + research
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

## [0.2.0] - 2026-05-14

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
  via `"if": "key=value"` (DRY: no hardcoded special cases).
- **Python bootstrap** via `--with-python` flag installs Python ≥
  required version via `uv python install` when missing (does not
  touch system Python).
- **Independence**: zero changes to the parent project's
  `pyproject.toml`. The installer is **vendorable**: copy
  `installer/` into any project, swap `registry.json`, ship.



### Renamed
- Package: `claude-config` → **`ai-config-kit`**.
- Python module: `claude_config` → `ai_config_kit`.
- CLI: `claude-config` → `ai-config-kit`.
- The on-disk config path stays `~/.config/claude-config/` (unchanged
  XDG dotfile location). The backup-file suffix
  `*.before-claude-config` stays (marker on disk for existing installs).

### Structure
- Bundled data moved from `src/claude_config/data/decisions/` to
  `src/ai_config_kit/resources/decisions/`.
- Per-pack `README.md` → `details.md` to disambiguate from the
  single authoritative top-level README. `decisions show` reads
  `details.md`.
- Docs index `docs/README.md` removed: folded into the top-level
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
- `bootstrap --no-decisions` flag: skip the auto-applied decision
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
  validation. **Body bytes never enter the response stream**: solves
  the content-filter block that hits when the model's file-write tool
  tries to emit a long well-known text (LICENSE, code of conduct, etc.).
- New decision pack `fetch-canonical-pattern`: slash command +
  CLAUDE.md fragment that teaches the model to use `ai-config-kit fetch`
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
- `save_config` merges with the on-disk JSON rather than overwriting:
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
  `tools/ai-config-kit.md`.
- `.github/` scaffolding added: `workflows/{ci,release}.yml`,
  `dependabot.yml`, issue templates, PR template.
- `Makefile` with `check / lint / test / format / build / clean` targets.

### Security
- `decisions apply` refuses to write a file whose destination matches
  a secret pattern.
- `view` refuses path-traversal (`../`).

[0.4.2]: https://github.com/simtabi/ai-config-kit/releases/tag/v0.4.2
[0.4.1]: https://github.com/simtabi/ai-config-kit/releases/tag/v0.4.1
[0.4.0]: https://github.com/simtabi/ai-config-kit/releases/tag/v0.4.0
[0.3.0]: https://github.com/simtabi/ai-config-kit/releases/tag/v0.3.0
[0.2.0]: https://github.com/simtabi/ai-config-kit/releases/tag/v0.2.0

## [0.1.0] - Initial release

### Added
- Single `ClaudeConfig` Python class with fluent API for managing
  Claude Code's `~/.claude/` via symlinks from a versioned content
  directory.
- Subcommands: `init`, `install`, `uninstall`, `sync`, `track`,
  `status`, `doctor`.
- JSON config at `~/.config/claude-config/config.json` (XDG-aware).
  Every field optional, defaults applied for anything missing.
- Three-layer precedence: CLI flags > env vars
  (`CLAUDE_CONFIG_FILE`, `CLAUDE_CONFIG_CONTENT_DIR`,
  `CLAUDE_CONFIG_TARGET`) > JSON config > class defaults.
- Opt-in Claude sessions + history tracking via `include_sessions` /
  `include_history` config fields (or `.with_sessions(True)` /
  `.with_history(True)` fluent setters). Off by default: these
  paths grow fast and the user should choose to ingest them.
- `track` accepts both files **and directories**. For a directory,
  it moves the dir into content + creates a directory-level symlink
  + adds the dir's basename to `dir_symlink_names` so subsequent
  files inside auto-propagate.
- Defence-in-depth secret guards via configurable
  `secret_patterns`: refuses to track or symlink matching files.
  `init` pre-populates `.gitignore` with the same patterns.
- Directory-level symlinks (configurable via `dir_symlink_names`,
  defaults to `memory`) so new files inside auto-propagate without
  re-running `install`.
- Idempotent `install`: re-running reports already-correct counts;
  collisions with real files back up to `<file>.before-claude-config`.
- `track` workflow: move a real file into the content dir + replace
  original with absolute symlink.
- `doctor` walks every source file and validates the symlink chain
  via `realpath`-style resolution (handles file-level and dir-level
  symlinks transparently).
- Pure stdlib: no runtime dependencies beyond Python 3.10+.
- PEP 561 typed (`py.typed` ships with the wheel).
- CLI installable via `pip` / `pipx` / `uv tool install`.

[0.1.0]: https://github.com/simtabi/ai-config-kit/releases/tag/v0.1.0
