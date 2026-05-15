# Decisions

A **decision** is a small, opinionated bundle of `CLAUDE.md`
fragments, slash commands, hooks, or settings that distils a
battle-tested practice into a drop-in.

Each pack ships inside the package at
`ai_configurator/resources/decisions/<name>/` and is accessible
through three CLI verbs:

| Command | Purpose |
|---|---|
| `ai-configurator decisions list` | Show every bundled pack with its one-line description. |
| `ai-configurator decisions show <name>` | Print the pack's manifest + embedded details. |
| `ai-configurator decisions apply <name> [--force] [--dry-run]` | Copy a pack's files into the content dir. Refuses to overwrite existing files unless `--force`. |

## Pack layout

```
<name>/
├── manifest.json          metadata + file map
├── details.md             text shown by `decisions show <name>`
└── files/                 the actual content shipped into <content>/claude/
    └── ...
```

### `manifest.json` schema

```json
{
  "name": "pack-name",
  "description": "One-line summary shown by `decisions list`.",
  "version": "1.0.0",
  "files": [
    { "src": "files/CLAUDE.md", "dest": "CLAUDE.md.fragment" },
    { "src": "files/commands/foo.md", "dest": "commands/foo.md" }
  ]
}
```

`dest` is relative to `<content>/claude/`. Files with a
`.fragment` suffix are **not** auto-applied: they're meant to be
read, copy-pasted, or appended manually.

## Bundled packs

Auto-applied by `ai-configurator init` (skip with `--no-decisions`):

| Pack | What it ships |
|---|---|
| `script-generation-pattern` | Slash command + `CLAUDE.md` fragment teaching the model to write a generator script for many-file or content-filter-risky tasks. |
| `fetch-canonical-pattern` | `/fetch-canonical` slash command + `CLAUDE.md` fragment routing canonical-file downloads disk-to-disk via `ai-configurator fetch` or `curl -o`. |
| `session-protocol` | Five slash commands (`/session-start`, `/session-end`, `/track-progress`, `/research-source`, `/clarify`) + fragment codifying audit-on-start / track-progress / self-improve-on-end. |
| `docker-multiarch` | `/docker-multiarch-check` slash command + self-gating fragment. Requires every published image to build for `linux/amd64` and `linux/arm64`. |
| `docker-env-interpolation` | POSIX shell script (`scripts/render-env.sh`) that flattens layered `.env` files into one resolved output; `/render-env` slash command walks invocation. |
| `claude-best-practices` | Best-practices fragment distilled from `code.claude.com/docs` + `/audit-claude-md` and `/init-rules` commands. |
| `humanistic-style` | Banned-phrase list + doc-block conventions + `/audit-prose` and `/audit-docblocks` commands. Bans em-dash sandwich and other AI tells. |
| `docs-structure` | One README at root, rest under `docs/`. `/audit-docs-structure` and `/migrate-readmes-to-docs` commands. |
| `mcp-best-practices` | Model Context Protocol configuration fragment + `/audit-mcp-config` and `/add-mcp-server` commands. |
| `safety-net-commits` | Prompts the user to commit a checkpoint at safe moments. `/checkpoint-now` and `/review-changes`. |
| `vendor-portability` | AGENTS.md canonical pattern + `/audit-vendor-config`. Now points at `compose-agents-md` + `project-install` as the automated path. |
| `polling-discipline` | "Don't chain sleeps" rule + `/wait-for` slash command. Heads off the runtime block that catches `sleep N; check` patterns. |
| `model-overload-resilience` | Multi-provider playbook for Anthropic 529, OpenAI/Codex 503, generic 429. Ships per-timezone off-peak data (`data/off-peak-windows.json`), `/capacity-check` slash command, and `scripts/api-retry.py` retry helper. |

Opt-in:

| Pack | What it ships |
|---|---|
| `core` | Skeleton `CLAUDE.md` + `settings.json` for a fresh content dir. Apply with `--force` if you want to overwrite the default seed. |

Run `ai-configurator decisions show <name>` to see a pack's full
details (the embedded `details.md`).

## Adding a new pack

1. Create `src/ai_configurator/resources/decisions/<name>/`
   with `manifest.json`, `details.md`, and a `files/` subtree.
2. Wheel builds include it automatically: no `pyproject.toml`
   change needed.
3. (Optional) Add the pack to `DEFAULT_DECISIONS_ON_INIT` in
   `manager.py` so `init` auto-applies it.
4. Add a row to the bundled-packs table above.

## Safety

- `decisions apply` refuses to write a file whose destination
  matches a `secret_patterns` entry.
- It refuses to overwrite an existing file unless `--force`.
- `--dry-run` prints what would be written without writing.

Behaviour is identical for end users and developers: the same
`resources/decisions/` directory ships in the wheel and is read in
editable installs.
