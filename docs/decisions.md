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
`.fragment` suffix are **not** auto-applied — they're meant to be
read, copy-pasted, or appended manually.

## Bundled packs

Auto-applied by `ai-configurator init` (skip with `--no-decisions`):

| Pack | What it ships |
|---|---|
| `script-generation-pattern` | Slash command + `CLAUDE.md` fragment teaching the model to write a generator script for many-file or content-filter-risky tasks. |
| `fetch-canonical-pattern` | `/fetch-canonical` slash command + `CLAUDE.md` fragment routing canonical-file downloads disk-to-disk via `ai-configurator fetch` or `curl -o`. |

Opt-in:

| Pack | What it ships |
|---|---|
| `core` | Skeleton `CLAUDE.md` + `settings.json` for a fresh content dir. Apply with `--force` if you want to overwrite the default seed. |

Run `ai-configurator decisions show <name>` to see a pack's full
details (the embedded `details.md`).

## Adding a new pack

1. Create `src/ai_configurator/resources/decisions/<name>/`
   with `manifest.json`, `details.md`, and a `files/` subtree.
2. Wheel builds include it automatically — no `pyproject.toml`
   change needed.
3. (Optional) Add the pack to `DEFAULT_DECISIONS_ON_INIT` in
   `manager.py` so `init` auto-applies it.
4. Add a row to the bundled-packs table above.

## Safety

- `decisions apply` refuses to write a file whose destination
  matches a `secret_patterns` entry.
- It refuses to overwrite an existing file unless `--force`.
- `--dry-run` prints what would be written without writing.

Behaviour is identical for end users and developers — the same
`resources/decisions/` directory ships in the wheel and is read in
editable installs.
