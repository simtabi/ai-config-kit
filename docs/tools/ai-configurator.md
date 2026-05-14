# `ai-configurator` CLI reference

```
ai-configurator [GLOBAL FLAGS] COMMAND [COMMAND FLAGS]
```

## Global flags

| Flag | Effect |
|---|---|
| `--config <path>` | Path to JSON config (default: `~/.config/claude-config/config.json`) |
| `--content <path>` | Override content dir (precedence over JSON config) |
| `--target <path>` | Override target dir (default: `~/.claude`) |
| `-y`, `--yes` | Skip prompts; assume default answer to every question |
| `-q`, `--quiet` | Print only essential output |
| `-V`, `--version` | Print version and exit |
| `-h`, `--help` | Show help and exit |

## Commands

### `bootstrap` — one-shot first-time setup

```bash
ai-configurator bootstrap [--push] [--remote URL] [--no-git] [--with-settings] [-m MSG] [--dry-run]
```

Runs validate, init, install, optional sync `--push`, and doctor in
sequence with prompts and clean error reporting. Idempotent — safe to
re-run.

Flags:

- `--push` — after install, commit + push to the remote.
- `--remote URL` — set `origin` to this URL before the push (fresh setup).
- `--no-git` — skip `git init`.
- `--with-settings` — also seed a starter `settings.json` template.
- `-m, --message MSG` — commit message for the sync step.
- `--dry-run` — print the steps that would run; touch nothing.

Exit code: 0 if every non-skipped step succeeded; 1 otherwise.

### `init` — create the content dir

```bash
ai-configurator init [--no-examples] [--no-git] [--with-settings] [--save]
```

- `--no-examples` — skip seeding a starter CLAUDE.md.
- `--no-git` — skip `git init` in the content dir.
- `--with-settings` — seed a starter `settings.json` template.
- `--save` — write the resolved config to the JSON config file.

### `install` — symlink into target

```bash
ai-configurator install [--dry-run]
```

Three passes: directory symlinks for auto-grow dirs, per-file symlinks
for everything else, then host-overlay files. See
[architecture.md](architecture.md) for details.

### `uninstall` — remove symlinks

```bash
ai-configurator uninstall [--no-restore]
```

Removes every symlink in the target that points into the content dir.
By default restores `*.before-claude-config` backups created by `install`.

### `sync` — commit + optionally push

```bash
ai-configurator sync [-m MESSAGE] [--push]
```

Detects current branch and first remote automatically — works with
non-`origin` remotes and non-`main` branches.

### `track` — move a real path into the content dir

```bash
ai-configurator track <path>
```

Works on both files and directories. For directories, adds the basename
to `dir_symlink_names` so future installs treat it as a dir-level
symlink and persists this change to the JSON config (if one was used).

Refuses paths matching any `secret_patterns` entry.

### `status` — what's tracked / git state

```bash
ai-configurator status
```

Shows content dir, target, hostname, tracked file count, untracked
candidates under target, and git porcelain state if the content dir is
a git repo.

### `doctor` — verify symlink health

```bash
ai-configurator doctor
```

Walks every tracked file and confirms the symlink chain resolves
correctly. Also flags:

- Orphan symlinks (target gone).
- Foreign host-overlay symlinks (point into another host's `hosts/` subdir).

Exit code: 0 if healthy; 1 otherwise.

### `validate` — pre-flight check

```bash
ai-configurator validate
```

Used internally by `bootstrap`. Checks: git on PATH, target parent
writable, content parent writable, target is a directory (not a file).
Warns about existing-but-untracked content and foreign symlinks.

### `list` — grouped view of content

```bash
ai-configurator list
```

Groups: top-level config files, auto-grow dirs, plugin config files,
per-project memory, host overlays, opt-in tracked dirs, other.
Counts and total size per group.

### `view` — print a tracked file

```bash
ai-configurator view <relpath> [--with-line-numbers]
```

`<relpath>` is relative to `<content>/claude/`. Path-traversal is
rejected — the resolved path must be inside the content dir.

### `fetch` — disk-to-disk download

```bash
ai-configurator fetch <url> <dest> [--expect-sha256 HEX] [--max-bytes N]
                                  [--allow-http] [--allow-binary]
                                  [--no-first-line]
```

Streams a URL to disk via `urllib.request` (Python stdlib, no
external dependencies). HTTPS-only unless `--allow-http`. Atomic
write (temp file + rename). Idempotent — re-running with the same
URL on an unchanged file reports `status=unchanged` and writes
nothing.

**Why it exists.** When the model is asked to add a canonical /
upstream file (`LICENSE`, `CODE_OF_CONDUCT.md`, a `.gitignore`
template), its file-write tool streams the body bytes through the
response. Content filters watch that stream, and on long
well-known texts they fire mid-flight, leaving a half-written file.
`fetch` routes bytes URL → disk via a child process. The
model's reply contains only the metadata (`bytes=`, `sha256=`,
`first_line=`, `status=`), never the body.

**Cross-platform.** Pure stdlib. Works identically on macOS, Linux,
and Windows (PowerShell or cmd) wherever Python 3.10+ is available.

Exit code: 0 on success; 2 on any validation / network / hash failure.

### `cleanup` — remove noise

```bash
ai-configurator cleanup [--apply] [--include-ephemeral]
```

Dry-run by default. Lists:

- `.DS_Store` / swap-file litter (in both content + target).
- Broken symlinks pointing into the content dir.
- Orphan `*.before-claude-config` backups (primary missing or now a symlink).
- With `--include-ephemeral`: contents of every runtime dir under target
  (`paste-cache/`, `file-history/`, etc.). Respects `include_sessions` /
  `include_history` — never clears those when tracked.

`--apply` to actually delete.

### `repair` — heal a broken install

```bash
ai-configurator repair [--dry-run]
```

Runs `cleanup` followed by `install` to fix a half-applied state:
broken symlinks removed, `*.before-claude-config` backups restored
where they protected a now-missing source, missing or wrong
symlinks rebuilt. Reports per-action detail.

`--dry-run` describes what would happen without touching anything.

### `decisions` — bundled global rules

```bash
ai-configurator decisions list
ai-configurator decisions show <name>
ai-configurator decisions apply <name> [--force] [--dry-run]
```

`list` enumerates every bundled pack. `show` prints a pack's
manifest + embedded `details.md`. `apply` copies the pack's files
into `<content>/claude/`; refuses to overwrite existing files
unless `--force`.

See [`docs/decisions.md`](../decisions.md) for the full catalogue
and pack-authoring schema.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Operation completed but reported failures (doctor unhealthy, push failed, bootstrap step failed) |
| 2 | Config / argument error |
| 130 | Interrupted (Ctrl-C) |
