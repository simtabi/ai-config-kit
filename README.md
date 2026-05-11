# claude-config

Manage [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)'s
`~/.claude/` directory via symlinks from a **versioned content directory**.

```bash
pip install claude-config

claude-config init             # create the content dir at ~/.config/claude-config/content/
claude-config install          # symlink content/claude/* into ~/.claude/*
claude-config sync --push      # commit + push your content dir
claude-config doctor           # verify symlinks resolve
```

## What problem this solves

`~/.claude/` mixes config (`CLAUDE.md`, `settings.json`, custom skills,
accumulated memory files) with caches and session state (`sessions/`,
`history.jsonl`, `paste-cache/`, `file-history/`, often hundreds of MB).

Versioning `~/.claude/` directly is awkward — you'd version-control caches
or fight with `.gitignore` constantly. **claude-config** keeps your
canonical config files in a clean directory you fully control, then
symlinks them into `~/.claude/` at the paths Claude Code expects.

Edit `~/.claude/CLAUDE.md` from any tool — you're editing the file in
your content dir. Run `claude-config sync` to commit. Clone your content
dir on a new machine and `claude-config install` puts everything back.

## Design

One class, one config file, one CLI.

```
~/.config/claude-config/         your content dir (default, configurable)
├── .git/                         your own private repo (optional)
├── claude/                       mirrors ~/.claude/ structure
│   ├── CLAUDE.md                 → ~/.claude/CLAUDE.md
│   ├── settings.json             → ~/.claude/settings.json
│   └── projects/<slug>/memory/   → ~/.claude/projects/<slug>/memory/  (dir symlink)
└── .gitignore                    secret patterns auto-populated

~/.config/claude-config/config.json    persistent settings (optional)
```

The single `ClaudeConfig` Python class manages this. The CLI is a thin
wrapper.

## Install

```bash
pip install claude-config
# or
pipx install claude-config
# or
uv tool install claude-config
```

## First-time setup

```bash
# Create content dir + git repo + example CLAUDE.md + .gitignore for secrets
claude-config init

# Symlink everything in <content>/claude/ into ~/.claude/
claude-config install

# Save your settings to a config file for future use
claude-config init --save
```

To put your content dir somewhere other than `~/.config/claude-config/content`:

```bash
claude-config --content ~/dotfiles/claude init --save
claude-config install
```

The `--save` writes the choice to `~/.config/claude-config/config.json` so
future invocations don't need the flag.

## On a new machine

```bash
pip install claude-config

# Clone your content dir from your private repo (replace URL):
git clone git@github.com:you/my-claude-config.git ~/.config/claude-config/content

# Install symlinks:
claude-config install
```

That's it — `~/.claude/CLAUDE.md` etc. now point at your content.

## Daily flow

```bash
# Edit any tracked file through ~/.claude/ — it's a symlink, edits flow
# straight to the content repo.

claude-config sync                       # commit (auto-message)
claude-config sync -m "tighten rules"    # custom message
claude-config sync --push                # commit + push
claude-config status                     # what's tracked + git state
claude-config doctor                     # verify symlinks resolve
```

## Add new files (or directories) to tracking

```bash
# Single file:
claude-config track ~/.claude/skills/my-skill.md

# Whole directory (sessions/, custom subdirs, etc.):
claude-config track ~/.claude/sessions
```

`track` works on both files and directories. For a directory, it
moves the directory into the content dir, replaces the original with
a directory-level symlink, and adds the dir's basename to
`dir_symlink_names` so future files added inside auto-propagate
without re-running `install`.

## Tracking Claude sessions and history (opt-in)

By default, `~/.claude/sessions/` and `~/.claude/history.jsonl` are
excluded — Claude Code writes to them constantly and they grow fast
(typically tens to hundreds of MB). Tracking them is fully supported
but **opt-in**, with two flags:

```jsonc
// ~/.config/claude-config/config.json
{
  "include_sessions": true,
  "include_history":  true
}
```

Or via the fluent API:

```python
ClaudeConfig().with_sessions(True).with_history(True).install()
```

Or directly via `track`:

```bash
claude-config track ~/.claude/sessions          # whole dir
claude-config track ~/.claude/history.jsonl     # single file
```

The tool flips `include_sessions` / `include_history` automatically
when you `track` the corresponding path.

### Trade-offs

| Concern | Impact |
|---------|--------|
| **Repo size** | Sessions can be hundreds of MB. Every commit grows the repo. Consider [git LFS](https://git-lfs.com/) or periodic squash-and-reset on a separate branch. |
| **Privacy** | Transcripts contain every prompt and response, including pasted code, file paths, and project context. **Always keep the content repo private.** |
| **Commit churn** | Sessions append on every Claude run. `claude-config sync` after each session means dozens of commits per day. Practical pattern: nightly cron `claude-config sync -m "nightly snapshot"`. |
| **Restore semantics** | Cloning the content repo on a new machine and running `install` restores history as Claude Code expects — but past sessions reference paths that may not exist on the new host. Treat as a backup, not a perfect replay. |

### Recommended cadence

```bash
# In a launchd plist / systemd timer / cron, run nightly:
claude-config sync -m "nightly snapshot" --push
```

Skip entirely if cross-machine session continuity isn't a goal —
they're fine being ephemeral.

## Use cases

### 1. Solo developer, single machine

Default setup. `init` then `install`. Content dir in
`~/.config/claude-config/content/`. Optional git for backup.

```bash
claude-config init
claude-config install
```

### 2. Solo developer, multiple machines (laptop + desktop)

Push content to a **private** GitHub repo. On each new machine:

```bash
pip install claude-config
git clone git@github.com:you/my-claude.git ~/.config/claude-config/content
claude-config install
```

Edit `~/.claude/CLAUDE.md` on machine A → `sync --push`.
On machine B: `git pull` (in content dir) → no install needed since
symlinks already point at the cloned files.

### 3. Team shared baseline + per-developer overrides

Team agrees on a baseline `CLAUDE.md` that lives in a *public* team
repo. Each developer maintains their own *private* content repo for
personal additions.

```bash
# Team-shared baseline (public):
git clone https://github.com/team/team-claude-baseline.git ~/baseline

# Personal content (private, layered on top — your CLAUDE.md can
# `## include`-style reference the baseline if you want):
claude-config init
cp ~/baseline/CLAUDE.md ~/.config/claude-config/content/claude/CLAUDE.md
# … then edit to add your personal sections
claude-config install
```

### 4. CI / ephemeral environment

For tests that need Claude Code with a specific config, point env
vars at a checked-out content dir:

```bash
git clone https://github.com/you/claude-content /tmp/cc
CLAUDE_CONFIG_CONTENT_DIR=/tmp/cc \
CLAUDE_CONFIG_TARGET=/tmp/runtime-claude \
  claude-config install
```

No global state mutated; the runtime `~/.claude/` equivalent lives
at `/tmp/runtime-claude/` only for that process tree.

### 5. Programmatic use (inside another tool)

```python
from claude_config import ClaudeConfig

cfg = (
    ClaudeConfig()
    .with_content_dir("./vendored-claude-config")
    .with_target("./.runtime-claude")
    .with_sessions(False)  # explicitly ephemeral for tests
)

report = cfg.install(dry_run=True)
print(report.summary())
```

The `ClaudeConfig` class is the full surface — every CLI capability
is a method. Wrap it inside your own CLI or test fixture without
shelling out.

### 6. Multi-tenant per-project content

Different content dirs per Claude project:

```bash
# Project-specific config
cd ~/projects/project-a
CLAUDE_CONFIG_CONTENT_DIR=./.claude-content claude-config install

# Different project, different content
cd ~/projects/project-b
CLAUDE_CONFIG_CONTENT_DIR=./.claude-content claude-config install
```

Use a direnv-style `.envrc` per project so the env var follows the cwd.

## Configuration

Every setting has a default. Per-user / per-machine overrides happen
through **three layers, applied in precedence order** (highest first):

1. **CLI flag** — `--content` / `--target` / `--config`
2. **Environment variable** — see table below
3. **JSON config file** — `~/.config/claude-config/config.json`
4. **Class default** (built in)

Each layer overrides the one beneath it. Most users only need the
JSON file. Env vars are useful for shell-script automation or
multi-environment setups. CLI flags are for one-off overrides.

### Environment variables

| Variable | Effect |
|----------|--------|
| `CLAUDE_CONFIG_FILE` | Path to the JSON config file. Overrides `--config` and the XDG default. |
| `CLAUDE_CONFIG_CONTENT_DIR` | Override the content directory. |
| `CLAUDE_CONFIG_TARGET` | Override the target directory (default `~/.claude`). |
| `XDG_CONFIG_HOME` | Affects the JSON config file default path (`$XDG_CONFIG_HOME/claude-config/config.json`). |

Example: per-shell content dir for testing without touching your real
config:

```bash
CLAUDE_CONFIG_CONTENT_DIR=/tmp/test-content claude-config install --dry-run
```

### JSON config file

Default path: `${XDG_CONFIG_HOME:-~/.config}/claude-config/config.json`.
Every field optional — anything missing falls back to a sensible
default.

```json
{
  "content_dir":      "/Users/you/.config/claude-config/content",
  "target_base":      "/Users/you/.claude",
  "secret_patterns":  [".credentials.json", "*.key", "*.token", ".env"],
  "ignore_patterns":  [".DS_Store", "*.swp"],
  "dir_symlink_names": ["memory"]
}
```

| Field | Default | Purpose |
|-------|---------|---------|
| `content_dir` | `${XDG_CONFIG_HOME:-~/.config}/claude-config/content` | Where your canonical files live |
| `target_base` | `~/.claude` | Where Claude Code reads from |
| `secret_patterns` | credentials, keys, tokens, .env | Refuses to track or symlink anything matching |
| `ignore_patterns` | `.DS_Store`, swap files | Excluded from install / status / doctor |
| `dir_symlink_names` | `memory` | These directories get a single dir-level symlink so new files inside auto-propagate |

**Tip — sharing the tool across team members:** the tool itself is
public and contains no personal data. Each developer keeps their own
`content_dir` in their own (private) location. The JSON config file
and the env vars are what distinguishes one user's setup from
another — neither lives inside the public tool repo.

## Programmatic use

```python
from claude_config import ClaudeConfig

cfg = (
    ClaudeConfig()
    .with_content_dir("~/my-dotfiles/claude")
    .with_target("~/.claude")
)
cfg.init().install()

report = cfg.doctor()
if not report.healthy:
    print(report.summary())

cfg.sync(message="bumped CLAUDE.md", push=True)
```

The class is fluent: every mutator returns `self`. Operations that produce
data return small frozen dataclasses (`InstallReport`, `DoctorReport`,
`StatusReport`, `SyncReport`) — single-source-of-truth result types, no
parsing CLI output.

## Security

- **Secret patterns are blocking, not advisory.** `track` refuses to
  ingest a file matching any pattern. `install` skips them. `init`
  pre-populates `.gitignore` in the content dir with the same patterns.
- **No personal info in this repo.** This package contains only the
  tool. Your content (CLAUDE.md, memory files, settings.json) lives in
  *your* directory under *your* git repo. The tool never reads, copies,
  or transmits content outside the local filesystem operations you ask
  for.
- **Keep your content dir's git repo private** — `CLAUDE.md` and memory
  files typically contain personal identifiers, internal URLs, project
  context.

## Subcommand reference

```
claude-config init [--no-examples] [--no-git] [--save]
claude-config install [--dry-run]
claude-config uninstall
claude-config sync [-m "message"] [--push]
claude-config track <path>
claude-config status
claude-config doctor

Common options:
  --config <path>     path to JSON config (default: ~/.config/claude-config/config.json)
  --content <path>    override content dir
  --target <path>     override target dir (default: ~/.claude)
  -V, --version
```

## Development

```bash
git clone https://github.com/simtabi/claude-configs
cd claude-configs
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
ruff check src tests
mypy src/claude_config
```

## License

MIT — see [`LICENSE`](LICENSE).
