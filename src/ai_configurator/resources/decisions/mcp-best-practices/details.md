# mcp-best-practices

Rules for safe MCP (Model Context Protocol) server configuration.
Cited from <https://code.claude.com/docs/en/mcp> and
<https://modelcontextprotocol.io>.

## What ships

| File | Purpose |
|---|---|
| `CLAUDE.md.mcp-best-practices.fragment` | What MCP is, the scope model (user vs project vs managed), security caveats, common safe-to-trust servers, how to add and audit. |
| `commands/audit-mcp-config.md` | `/audit-mcp-config` audits user-level + project-level MCP setup. |
| `commands/add-mcp-server.md` | `/add-mcp-server <name>` walks through adding a new MCP server safely. |

Auto-applied. The fragment is short on purpose; full details live in
the official docs that the fragment cites.

## Why this matters

MCP servers run as separate processes that Claude Code talks to over
JSON-RPC. They can read files, hit APIs, query databases, send
notifications — anything they're built to do. A malicious or buggy
MCP server has the same access the user grants it.

The pack's hard rules:

- Pin MCP servers by exact name + version. No latest-tag installs.
- Only enable MCP servers from sources you've vetted (Anthropic
  Directory at <https://claude.ai/directory>, official npm
  organisations, etc.).
- Keep secrets out of `.mcp.json` (gitignored project file) — load
  them from env vars.
- Treat project-level `.mcp.json` like any third-party config:
  review every PR that touches it; never auto-accept.
