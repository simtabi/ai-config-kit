# Configuration

Every setting has a default. Per-user / per-machine overrides happen
through four layers, applied in precedence order (highest first):

1. **CLI flag**: `--content` / `--target` / `--config`
2. **Environment variable**: see table below
3. **JSON config file**: `~/.config/claude-config/config.json`
4. **Class default** (built in)

## Environment variables

| Variable | Effect |
|---|---|
| `CLAUDE_CONFIG_FILE` | Path to the JSON config file. Overrides `--config` and the XDG default. |
| `CLAUDE_CONFIG_CONTENT_DIR` | Override the content directory. |
| `CLAUDE_CONFIG_TARGET` | Override the target directory (default `~/.claude`). |
| `CLAUDE_CONFIG_HOSTNAME` | Override the hostname for host-overlay matching (mostly useful in tests). |
| `CLAUDE_CONFIG_PLACEMENTS_ROOT` | Override the directory placements are linked under (default: your home directory). |
| `CODEX_HOME` | Where the codex adapter writes `AGENTS.md` (default `~/.codex`), matching Codex itself. |
| `XDG_CONFIG_HOME` | Affects the JSON config file default path (`$XDG_CONFIG_HOME/ai-config-kit/config.json`). |

## JSON config file

Default path: `${XDG_CONFIG_HOME:-~/.config}/ai-config-kit/config.json`.

```json
{
  "content_dir":        "/Users/you/.config/claude-config/content",
  "target_base":        "/Users/you/.claude",
  "secret_patterns":    [".credentials.json", "*.key", "*.token", ".env"],
  "ignore_patterns":    [".DS_Store", "*.swp"],
  "dir_symlink_names":  ["memory", "commands", "agents", "skills", "hooks", "prompts"],
  "include_sessions":   false,
  "include_history":    false,
  "relative_symlinks":  true,
  "vendors":            ["claude-code", "codex", "gemini"],
  "placements_root":    "~"
}
```

| Field | Default | Purpose |
|---|---|---|
| `content_dir` | `${XDG_CONFIG_HOME:-~/.config}/ai-config-kit/content` | Canonical file home |
| `target_base` | `~/.claude` | Where Claude Code reads from |
| `secret_patterns` | credentials, keys, tokens, env, SSH keys, .netrc, .npmrc, .pypirc, .kdbx | Refuses to track / symlink matching |
| `ignore_patterns` | `.DS_Store`, swap files, `*~`, `Thumbs.db` | Excluded from install / status / doctor |
| `dir_symlink_names` | `memory`, `commands`, `agents`, `skills`, `hooks`, `prompts` | These directories get a single dir-level symlink so new files inside auto-propagate |
| `include_sessions` | `false` | Track `~/.claude/sessions/` (opt-in; sessions grow fast) |
| `include_history` | `false` | Track `~/.claude/history.jsonl` (opt-in; grows fast) |
| `relative_symlinks` | `true` | Use path-relative symlinks (survives content-dir relocation) |
| `vendors` | `["claude-code"]` | Agents `install` writes global files for (see [vendor global paths](#vendor-global-paths)) |
| `placements_root` | your home directory | Where `content/placements/*` is linked. Only written by `save_config` when it differs from the home directory |

### Using a content dir somewhere else

The content dir can be any git checkout, for example a private
`agent-config` repo kept with your other projects:

```bash
ai-config-kit --content ~/code/agent-config install     # one run
export CLAUDE_CONFIG_CONTENT_DIR=~/code/agent-config      # every run
ai-config-kit --content ~/code/agent-config init --save # persist in config.json
```

It must hold `claude/` (mirrors `~/.claude/`) and may hold
`placements/`.

Unknown fields in the file on disk are preserved by `save_config`:
forward-compat for future versions.

## Secrets

The patterns in `secret_patterns` are **blocking, not advisory**:

- `track` refuses any file matching a pattern.
- `install` skips them and reports the count.
- `init` pre-populates `.gitignore` in the content dir with the same patterns.

Default coverage: `.credentials.json*`, `*.secret`, `*.key`, `*.pem`, `*.p12`,
`*.pfx`, `*.kdbx`, `*.token`, `.netrc`, `*.netrc`, `.npmrc`, `.pypirc`,
`.env`, `.env.*`, `id_rsa*`, `id_ed25519*`, `id_ecdsa*`.

Never narrow this list without a corresponding `secret_patterns` override
in your JSON config.

## Host overlays

For per-machine files (typically `settings.local.json`), use the
host-overlay pattern:

```
<content>/claude/hosts/<hostname>/settings.local.json
```

On host `laptop`, that file installs as `~/.claude/settings.local.json`.
On host `desktop`, it doesn't. Each host can have its own
`hosts/<host>/` directory with whatever files differ between machines.

`doctor` warns if it finds a symlink at the target that points into a
foreign host's overlay dir: protecting against a symlink left over
from a different machine's install.

## Placements

Any file in your content repo that belongs somewhere under your home
directory, rather than in `~/.claude/`, goes under `placements/` at its
home-relative path:

```
<content>/placements/Artisan/projects/opensource/CLAUDE.md  ->  ~/Artisan/projects/opensource/CLAUDE.md
<content>/placements/.codex/AGENTS.override.md              ->  ~/.codex/AGENTS.override.md
```

`install` symlinks each file and creates missing parent directories.

- A real file already at the destination is moved to
  `<file>.before-claude-config` first, exactly as for `~/.claude/` files;
  `uninstall` moves it back.
- Refused, and reported in the install summary, `status` and `doctor`:
  a path that is absolute or contains `..`, a destination outside
  `placements_root`, inside the content dir, or inside `target_base`
  (put those under `claude/`), a real directory at the destination, and
  a symlink at the destination that points anywhere but `placements/`.
- `secret_patterns` and `ignore_patterns` apply, as they do to `claude/`.
- If a placement and a vendor adapter want the same file (say
  `placements/.codex/AGENTS.md` and the `codex` vendor), the placement
  wins: the vendor write sees the symlink and leaves it alone.

## Vendor global paths

Each adapter writes the canonical `AGENTS.md` to the one user-level file
the agent reads. Verified 2026-11-10 against each tool's documentation
or source:

| Vendor | File `install` writes | Status | Source |
|---|---|---|---|
| codex | `$CODEX_HOME/AGENTS.md` (default `~/.codex/AGENTS.md`) | current | [OpenAI: AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md) (`AGENTS.override.md` takes precedence; place it with a placement if you use one) |
| gemini | `~/.gemini/GEMINI.md` | current | [Gemini CLI: GEMINI.md](https://google-gemini.github.io/gemini-cli/docs/cli/gemini-md.html) |
| junie | `~/.junie/AGENTS.md` | current | [Junie: guidelines and memory](https://junie.jetbrains.com/docs/guidelines-and-memory.html) (documented for Junie CLI) |
| kiro | `~/.kiro/steering/agents.md` | current | [Kiro: steering](https://kiro.dev/docs/steering/) (no front matter means "always included") |
| continue | `~/.continue/rules/agents.md` | current | [Continue source: `getPromptFiles.ts`](https://github.com/continuedev/continue/blob/main/core/promptFiles/getPromptFiles.ts) reads `<global dir>/rules`; the current [rules page](https://docs.continue.dev/customize/deep-dives/rules) documents only project rules |
| opencode | `~/.config/opencode/AGENTS.md` | current | [opencode: rules](https://opencode.ai/docs/rules/) |
| grok | `~/.grok/AGENTS.md` | partial | [xAI: project rules](https://docs.x.ai/build/features/project-rules) says only "Global rules in `~/.grok/`"; the filename is inferred from the `AGENTS.md` family it reads elsewhere |
| cursor | `~/.cursor/rules/agents.md` | current | unchanged |

> Before 0.5.0 the codex adapter wrote `~/.codex/instructions/agents.md`,
> which Codex does not read. `install` no longer writes it; an old copy
> there is left untouched and can be deleted.

## Sessions and history (opt-in)

Tracking `~/.claude/sessions/` and `~/.claude/history.jsonl` is **opt-in**
because they grow fast (hundreds of MB) and contain every prompt and
response. To enable:

```json
{
  "include_sessions": true,
  "include_history":  true
}
```

Or via the fluent API:

```python
ClaudeConfig().with_sessions(True).with_history(True).install()
```

Or directly via `track` (auto-sets the flag):

```bash
ai-config-kit track ~/.claude/sessions
ai-config-kit track ~/.claude/history.jsonl
```

Trade-offs covered in [architecture.md](architecture.md).
