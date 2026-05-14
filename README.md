# ai-configurator

Version your `~/.claude/` directory without versioning your caches.
Author rules once, ship them to every AI coding agent you use.

`ai-configurator` symlinks a content directory you control into
`~/.claude/` at the paths [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)
expects, ships opinionated "decision packs" that bake in
content-filter-safe practices, and gives you one verb each for
setting up a fresh machine and dropping cross-vendor rules into any
project repo. Wired adapters: claude-code, aider, cursor, windsurf,
copilot, codex, cline.

```bash
pip install ai-configurator
ai-configurator bootstrap        # validate + init + install + doctor, one shot
```

---

## Table of contents

- [Why it exists](#why-it-exists)
- [Install](#install)
- [Quick start](#quick-start)
- [Commands at a glance](#commands-at-a-glance)
- [Decisions: bundled global rules](#decisions-bundled-global-rules)
- [The fetch command + canonical-file pattern](#the-fetch-command--canonical-file-pattern)
- [Multi-machine setup](#multi-machine-setup)
- [Documentation](#documentation)
- [Project layout](#project-layout)
- [Contributing](#contributing)
- [License](#license)

---

## Why it exists

`~/.claude/` is a mixed bag:

| Kind | Examples | Worth versioning? |
|---|---|---|
| **Config** | `CLAUDE.md`, `settings.json`, `commands/`, `agents/`, `skills/`, `hooks/`, `prompts/`, `projects/*/memory/`, `plugins/blocklist.json` | yes |
| **Opt-in** | `sessions/`, `history.jsonl` | maybe (grow fast) |
| **Runtime** | `paste-cache/`, `file-history/`, `tasks/`, `todos/`, `cache/`, `plans/`, `statsig/`, `telemetry/` | no |
| **Secret** | `.credentials.json`, SSH keys, `.npmrc`, `.netrc`, `.env*` | never |

Putting the whole directory under git means versioning hundreds of MB
of caches and fighting `.gitignore` every time Claude Code adds a new
runtime path. `ai-configurator` solves this by keeping your
canonical config in a content directory (default
`~/.config/claude-config/content/`), symlinked into `~/.claude/` at
the right paths. Edit a file in `~/.claude/` and you're editing the
content dir; commit and push to share across machines.

The classification above is enforced by the install command. See
[`docs/architecture.md`](docs/architecture.md) for the full table.

---

## Install

```bash
pip install ai-configurator
# or:  pipx install ai-configurator
# or:  uv tool install ai-configurator
```

Requirements: Python 3.10+, `git` on `PATH` (only for `init` and
`sync`). Works on macOS, Linux, and Windows (Windows symlinks need
either Administrator or Developer Mode). Full install notes in
[`docs/installation.md`](docs/installation.md).

---

## One-liner install (any platform)

If you have neither `pip` nor `ai-configurator` yet, use the
[`get-installer`](https://github.com/simtabi/get-installer) bootstrap
(a sibling Simtabi project):

```bash
# POSIX (macOS / Linux / WSL / Git-Bash)
sh -c "$(curl -fsSL https://get.simtabi.com/install.sh)" -- \
  --product ai-configurator

# PowerShell (Windows)
irm https://get.simtabi.com/install.ps1 | iex
```

`get-installer` is registry-driven, version-aware, journals every
action for clean rollback on failure, and refuses to run as root. It
previously shipped inside this repo at `installer/`; it now lives as
its own project so other Simtabi tools (and third parties) can vendor
it. Full design + threat model: <https://github.com/simtabi/get-installer>.

## Quick start (after pip install)

```bash
ai-configurator bootstrap
```

Runs validate → init → install → doctor with prompts. Idempotent:
safe to re-run on a machine that's already set up. Pass `--push` to
also commit + push the content dir to its remote, `--remote URL` to
configure `origin` on a fresh machine, `--dry-run` to see what would
happen.

Once installed:

```bash
ai-configurator status              # what's tracked, what's not, git state
ai-configurator list                # grouped view of everything in content
ai-configurator view CLAUDE.md      # print a tracked file
ai-configurator sync -m "tighten X" # commit changes in the content dir
```

---

## Multi-vendor: one rules source, every AI agent

`ai-configurator` ships adapters for seven CLI-based AI coding agents.
Authored rules live once in your content dir; each vendor's expected
file format gets generated on demand.

```bash
# Compose the cross-vendor canonical from CLAUDE.md + decision packs
ai-configurator compose-agents-md

# Drop AGENTS.md, .cursorrules, .windsurfrules, .clinerules, and
# .github/copilot-instructions.md into a project repo in one shot
ai-configurator project-install ~/code/my-app \
    --vendor=aider --vendor=cursor --vendor=windsurf \
    --vendor=copilot --vendor=codex --vendor=cline
```

The supported vendors and their conventions:

| Vendor | Project file | Global target |
|---|---|---|
| claude-code | — | `~/.claude/` |
| aider | `AGENTS.md` | — |
| codex | `AGENTS.md` (native) | `~/.codex/instructions/` |
| cursor | `.cursorrules` | `~/.cursor/rules/` |
| cline | `.clinerules` | — |
| windsurf | `.windsurfrules` | — |
| copilot | `.github/copilot-instructions.md` | — |

`install` also writes the canonical `AGENTS.md` into each configured
vendor's global target (currently only cursor benefits). Existing
per-project files are never overwritten without `--force`.

---

## Commands at a glance

| Verb | What it does |
|---|---|
| [`bootstrap`](docs/tools/ai-configurator.md#bootstrap--one-shot-first-time-setup) | One-shot setup (validate + init + install + optional push + doctor). |
| [`init`](docs/tools/ai-configurator.md#init--create-the-content-dir) | Create the content dir + git repo + apply default decision packs. |
| [`install`](docs/tools/ai-configurator.md#install--symlink-into-target) | Symlink `content/claude/*` into `~/.claude/`; also drops `AGENTS.md` into each non-claude-code vendor's global target (e.g., `~/.cursor/rules/`). |
| [`compose-agents-md`](docs/tools/ai-configurator.md#compose-agents-md-synthesize-the-canonical-cross-vendor-file) | Synthesize a single `AGENTS.md` from `CLAUDE.md` + decision-pack fragments. |
| [`project-install`](docs/tools/ai-configurator.md#project-install-per-vendor-files-for-a-project-repo) | Write per-vendor files (`AGENTS.md`, `.cursorrules`, `.windsurfrules`, ...) into a project repo. |
| [`uninstall`](docs/tools/ai-configurator.md#uninstall--remove-symlinks) | Remove symlinks; restore pre-install backups. |
| [`sync`](docs/tools/ai-configurator.md#sync--commit--optionally-push) | `git add` + commit + optionally push, scoped to the content dir. |
| [`track`](docs/tools/ai-configurator.md#track--move-a-real-path-into-the-content-dir) | Move a real `~/.claude/` path into content + symlink back. |
| [`status`](docs/tools/ai-configurator.md#status--whats-tracked--git-state) | Tracked + untracked candidates + git state. |
| [`doctor`](docs/tools/ai-configurator.md#doctor--verify-symlink-health) | Verify every symlink resolves to a tracked source. |
| [`validate`](docs/tools/ai-configurator.md#validate--pre-flight-check) | Pre-flight environment check (Python, git, writability). |
| [`list`](docs/tools/ai-configurator.md#list--grouped-view-of-content) | Grouped tree of content with size + count per group. |
| [`view`](docs/tools/ai-configurator.md#view--print-a-tracked-file) | Print a tracked file's contents (path-traversal-safe). |
| [`cleanup`](docs/tools/ai-configurator.md#cleanup--remove-noise) | Remove `.DS_Store`, broken symlinks, orphan backups. |
| [`repair`](docs/tools/ai-configurator.md#repair--heal-a-broken-install) | Cleanup + rebuild symlinks + restore protected backups. |
| [`decisions`](docs/decisions.md) | List / show / apply bundled global-decision packs. |
| [`fetch`](docs/tools/ai-configurator.md#fetch--disk-to-disk-download) | Disk-to-disk download of a canonical / upstream text file. |

Every subcommand has `--help`. The full reference lives in
[`docs/tools/ai-configurator.md`](docs/tools/ai-configurator.md).

---

## Decisions: bundled global rules

`ai-configurator` ships **decision packs**: opinionated bundles
of `CLAUDE.md` fragments and slash commands that bake in proven
patterns. Two are auto-applied on `init` (skip with `--no-decisions`):

| Pack | What it ships |
|---|---|
| `script-generation-pattern` | Slash command + `CLAUDE.md` fragment that tells the model to use a generator script for many-file / content-filter-risky tasks. |
| `fetch-canonical-pattern` | `/fetch-canonical` slash command + `CLAUDE.md` fragment for canonical-file downloads (license, code of conduct, etc.) that route URL → disk and never through the response stream. |

```bash
ai-configurator decisions list                # show all bundled packs
ai-configurator decisions show <name>         # print pack details
ai-configurator decisions apply <name>        # copy into content dir (non-clobbering)
```

Full guide and pack-authoring schema:
[`docs/decisions.md`](docs/decisions.md).

---

## The `fetch` command + canonical-file pattern

Asking Claude Code to add a `LICENSE`, `CODE_OF_CONDUCT.md`, or any
other well-known upstream text often trips a content-filter policy
block. The model's file-write tool streams the body through the
response, and the filter watches that stream.

`ai-configurator fetch` routes the bytes URL → disk via Python's
stdlib (`urllib.request`). The response only contains the metadata:

```bash
ai-configurator fetch https://example.com/license.txt ./LICENSE
# path=…  bytes=11357  lines=202  sha256=…  status=created  first_line=Apache License
```

Atomic write, idempotent, HTTPS-only by default, size cap (1 MiB),
UTF-8 validation, optional `--expect-sha256`. The bundled
`fetch-canonical-pattern` decision pack teaches the model to use this
verb (or `curl -o` as a fallback) automatically.

---

## Multi-machine setup

Push the content dir to a private git repo from machine A, then on
machine B:

```bash
pip install ai-configurator
git clone git@github.com:you/my-claude-content.git ~/.config/claude-config/content
ai-configurator bootstrap
```

The on-disk path stays `~/.config/claude-config/` (not
`ai-configurator/`) so existing installs keep working. The
package name is what changed.

---

## Documentation

| Doc | Covers |
|---|---|
| [`docs/installation.md`](docs/installation.md) | Install, requirements, CI setup, Windows note |
| [`docs/configuration.md`](docs/configuration.md) | JSON config schema, env vars, secret patterns, host overlays |
| [`docs/architecture.md`](docs/architecture.md) | Symlink design, content-dir layout, classification table |
| [`docs/tools/ai-configurator.md`](docs/tools/ai-configurator.md) | Per-subcommand reference with all flags |
| [`docs/decisions.md`](docs/decisions.md) | Decision-pack catalogue + schema for authors |
| [`docs/release.md`](docs/release.md) | Tag-driven release flow, OIDC trusted publishing |
| [`docs/shipping-checklist.md`](docs/shipping-checklist.md) | One-time + ongoing release prep |
| Installer (sibling repo) | `https://github.com/simtabi/get-installer`. Reusable cross-platform one-liner installer; was here at `installer/` through v0.2.0 |

---

## Project layout

```
ai-configurator/
├── README.md                       you are here (the single authoritative readme)
├── docs/                           subdocs (lowercase-kebab, linked from README)
├── src/ai_configurator/        the package
│   ├── manager.py                  ClaudeConfig class + all report types
│   ├── cli.py                      thin argparse wrapper
│   ├── __init__.py                 public API
│   └── resources/decisions/        bundled decision packs (ships in wheel)
│       ├── core/
│       ├── script-generation-pattern/
│       └── fetch-canonical-pattern/
├── tests/                          pytest suite (manager + CLI)
├── pyproject.toml
├── CHANGELOG.md
├── CONTRIBUTING.md
├── SECURITY.md
├── CODE_OF_CONDUCT.md
└── LICENSE
```

Per-pack details live next to each pack as `details.md` (shown by
`ai-configurator decisions show <name>`). No per-pack README.md
files to disambiguate from this one.

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Quality gates: `pytest`,
`ruff check`, `mypy --strict`. All four pass on PR; CI runs them on
macOS + Ubuntu × Python 3.10–3.13.

---

## License

MIT. See [`LICENSE`](LICENSE).
