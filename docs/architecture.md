# Architecture

## The problem

`~/.claude/` is the directory Claude Code reads its config from. It also
gets a lot of runtime writes from the harness — session transcripts,
paste caches, edit history, telemetry IDs. Versioning the whole
directory means versioning hundreds of MB of caches; carefully
gitignoring inside the directory means fighting the tool every release.

## The approach

Two directories, joined by symlinks:

```
~/.config/claude-config/content/      versioned by you
├── .git/                              your private repo
├── .gitignore                          secret patterns
└── claude/                             mirrors ~/.claude/ layout
    ├── CLAUDE.md                       -> ~/.claude/CLAUDE.md
    ├── settings.json                   -> ~/.claude/settings.json
    ├── commands/                       (dir symlink — auto-grow)
    ├── agents/                         (dir symlink — auto-grow)
    ├── skills/                         (dir symlink — auto-grow)
    ├── hooks/                          (dir symlink — auto-grow)
    ├── prompts/                        (dir symlink — auto-grow)
    ├── projects/<slug>/memory/         (dir symlink — auto-grow)
    ├── plugins/blocklist.json          (file symlink)
    ├── plugins/known_marketplaces.json (file symlink)
    └── hosts/<hostname>/               (host-overlay source — installs per-machine)
```

Editing `~/.claude/CLAUDE.md` opens the file in the content dir.
Committing the content dir's git repo versions every change.

## Classification table

Every entry in `~/.claude/` falls into one of four buckets:

| Bucket | Examples | Behaviour |
|---|---|---|
| **config** (always tracked) | `CLAUDE.md`, `settings.json`, `commands/`, `agents/`, `skills/`, `hooks/`, `prompts/`, `projects/*/memory/`, `plugins/{blocklist,known_marketplaces}.json` | Symlinked by `install`. |
| **opt-in** | `sessions/`, `history.jsonl` | Off by default. Enable via config or `track`. |
| **runtime** (never tracked) | `paste-cache/`, `file-history/`, `shell-snapshots/`, `session-env/`, `tasks/`, `todos/`, `plans/`, `cache/`, `backups/`, `downloads/`, `ide/`, `telemetry/`, `statsig/`, `plugins/marketplaces/`, `.last-cleanup` | Skipped by `install` / `status`. Cleared by `cleanup --include-ephemeral`. |
| **secret** (refused) | `.credentials.json`, `*.key`, `*.token`, `.env`, `id_rsa`, `.netrc`, `.npmrc`, `.pypirc`, … | `install` skips; `track` refuses. |

The full classification lives in `ClaudeConfig`'s class constants
(`DEFAULT_DIR_SYMLINK_NAMES`, `RUNTIME_DIRS`, `MIXED_DIRS`,
`DEFAULT_SECRET_PATTERNS`).

## Why dir symlinks for some, file symlinks for others

Two-mode design:

- **Whole-directory symlink** (`commands/`, `agents/`, `memory/`, …): one
  link, then every file inside the linked dir is reachable without
  re-running install. Files added after install propagate immediately.
- **Per-file symlink** (`CLAUDE.md`, `settings.json`, …): the harness
  may rewrite these in place; file-level links give a clear 1:1 mapping
  and keep the diff small.

`install` does directory symlinks first, then per-file. Files whose
parent dir resolves into the content dir (already reachable via a
parent symlink) are skipped in the file pass.

## Host overlays

`hosts/<hostname>/<file>` in the content dir installs as `<target>/<file>`
on the matching host. The matching is done by `socket.gethostname()` at
install time, with `CLAUDE_CONFIG_HOSTNAME` as an override.

Use cases:

- Machine-specific `settings.local.json` with different MCP servers per
  host.
- Per-machine hook commands that point at host-specific tool paths.

`doctor` flags a symlink pointing into another host's overlay — typically
the result of restoring a config dir on a new machine where install
hasn't been re-run.

## Idempotency and safety

- `install` is idempotent. Re-runs are no-ops; matching links are counted
  as `already-correct`.
- Colliding real files at the target get moved to `<file>.before-claude-config`
  before the symlink lands. `uninstall` restores them by default.
- `cleanup` is dry-run by default. `--apply` to actually delete.
- Path containment uses `Path.is_relative_to`; symlink follow is bounded.

## What `~/.config/claude-config/content/` MUST contain

```
content/
├── .git/                        (optional but recommended)
├── .gitignore                    (auto-seeded by `init`)
└── claude/                       (required — install fails without it)
    └── ...                        (your tracked content)
```

The `claude/` subdir wraps the actual content so non-symlinked things
(`.git/`, `.gitignore`, future per-machine state files) can live
alongside without leaking into `~/.claude/`.
