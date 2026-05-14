# vendor-portability

Most teams use more than one AI coding tool. Engineers swap between
Claude Code, Cursor, Cline, Aider, Codex, Copilot, Windsurf: and the
project rules want to apply to all of them. This pack codifies the
"write once, target many" pattern.

## What ships

| File | Purpose |
|---|---|
| `CLAUDE.md.vendor-portability.fragment` | The pattern. AGENTS.md is canonical; each vendor's native config file imports or symlinks it. Per-vendor config locations table. |
| `commands/audit-vendor-config.md` | `/audit-vendor-config` audits the current repo for vendor-config drift (e.g., CLAUDE.md says one thing, .cursorrules says another). |

Auto-applied on `init`.

## Per-vendor configuration paths

| Vendor | Config file | Status |
|---|---|---|
| Claude Code | `CLAUDE.md` (project) + `~/.claude/` (user) | current |
| Claude.ai | `CLAUDE.md` (manually pasted into the web UI) | partial |
| OpenAI Codex | `AGENTS.md` (project root) | planned |
| Cursor | `.cursorrules` (project root) | planned |
| Cline | `.clinerules` (project root) | planned |
| Aider | `AGENTS.md` + `.aider.conf.yml` | planned |
| Windsurf | `.windsurfrules` (project root) | planned |
| GitHub Copilot | `.github/copilot-instructions.md` | planned |

The pattern: keep the source-of-truth in `AGENTS.md` (the open
standard at <https://agentskills.io>). Each vendor's file imports
or symlinks it.
