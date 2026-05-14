---
description: Audit configured MCP servers (user + project scope). Flag unpinned versions, secrets in repo files, overly-broad filesystem scopes.
---

Audit Model Context Protocol (MCP) configuration. Reports only — no
edits.

### Step 1: Enumerate

```bash
# User-level
cat ~/.claude/settings.json 2>/dev/null | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print(json.dumps(d.get('mcpServers',{}), indent=2))" 2>/dev/null

# Project-level
cat .mcp.json 2>/dev/null
cat .claude/settings.local.json 2>/dev/null | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print(json.dumps(d.get('mcpServers',{}), indent=2))" 2>/dev/null
```

### Step 2: Per-server checks

For each configured MCP server, flag:

- **Unpinned version**: `args` includes a package spec ending in `@latest`
  or no `@` pin at all. Production deployments should pin.
- **Secret in committed file**: `.mcp.json` contains a value that
  looks like a secret (long hex / base64 string, or a known token
  prefix like `ghp_`, `sk-`, `xoxp-`, `xoxb-`). Critical.
- **Overly broad filesystem scope**: `server-filesystem` arg is `/`
  or `~` or another huge subtree. Suggest scoping.
- **Network egress server pointed at internal URLs**: `server-fetch`
  configured with internal-only base URLs (looks like SSRF target).
- **Database server with non-read-only credentials**: connection
  string includes `postgres:` or `mysql:` with what looks like an
  admin user. Recommend least-privilege.
- **Unknown publisher**: source isn't `@modelcontextprotocol/*`,
  `@anthropic/*`, or a known-trusted org. Recommend manual vet.

### Step 3: Permissions audit

Check `~/.claude/settings.json`'s `permissions.allow` / `.deny` for
MCP-related rules. Are any MCP tools auto-allowed without scope?
Flag if `mcp__*` is in `allow` without per-server narrowing.

### Step 4: Report

```
| Server | Scope | Finding | Severity |
|---|---|---|---|
| github | project | GITHUB_PAT inlined in .mcp.json | critical |
| filesystem-fs | user | scoped to / (entire FS) | high |
| custom-internal | project | unknown publisher; not in known-good list | medium |
```

### Step 5: Do not edit

Print the report. Pause for the user. Adding / removing MCP servers
is `/add-mcp-server` or manual editing — not this audit's job.
