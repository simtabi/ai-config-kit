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
| `XDG_CONFIG_HOME` | Affects the JSON config file default path (`$XDG_CONFIG_HOME/ai-configurator/config.json`). |

## JSON config file

Default path: `${XDG_CONFIG_HOME:-~/.config}/ai-configurator/config.json`.

```json
{
  "content_dir":        "/Users/you/.config/claude-config/content",
  "target_base":        "/Users/you/.claude",
  "secret_patterns":    [".credentials.json", "*.key", "*.token", ".env"],
  "ignore_patterns":    [".DS_Store", "*.swp"],
  "dir_symlink_names":  ["memory", "commands", "agents", "skills", "hooks", "prompts"],
  "include_sessions":   false,
  "include_history":    false,
  "relative_symlinks":  true
}
```

| Field | Default | Purpose |
|---|---|---|
| `content_dir` | `${XDG_CONFIG_HOME:-~/.config}/ai-configurator/content` | Canonical file home |
| `target_base` | `~/.claude` | Where Claude Code reads from |
| `secret_patterns` | credentials, keys, tokens, env, SSH keys, .netrc, .npmrc, .pypirc, .kdbx | Refuses to track / symlink matching |
| `ignore_patterns` | `.DS_Store`, swap files, `*~`, `Thumbs.db` | Excluded from install / status / doctor |
| `dir_symlink_names` | `memory`, `commands`, `agents`, `skills`, `hooks`, `prompts` | These directories get a single dir-level symlink so new files inside auto-propagate |
| `include_sessions` | `false` | Track `~/.claude/sessions/` (opt-in; sessions grow fast) |
| `include_history` | `false` | Track `~/.claude/history.jsonl` (opt-in; grows fast) |
| `relative_symlinks` | `true` | Use path-relative symlinks (survives content-dir relocation) |

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
ai-configurator track ~/.claude/sessions
ai-configurator track ~/.claude/history.jsonl
```

Trade-offs covered in [architecture.md](architecture.md).
