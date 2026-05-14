---
description: Walk through adding a new MCP server safely. Verify publisher, pick a scope, vet config.
argument-hint: <server-name>
---

Walk through adding the MCP server "$1" safely.

### Step 1: Identify the server

Ask the user (or infer if obvious):

- What does this server do? (one sentence)
- Where does it come from? (npm package, GitHub repo, self-hosted
  binary)
- Is it listed in the Anthropic Directory at
  <https://claude.ai/directory>?

If the user can't answer the publisher question, STOP. Ask them to
read the source first.

### Step 2: Pick the scope

| If… | Scope |
|---|---|
| Just-you, useful across all projects | user (`~/.claude/settings.json`) |
| Team-shared, project-specific | project (`<project>/.mcp.json`) |
| Just-you on this project (sandboxing testing) | local (`<project>/.claude/settings.local.json`) |
| Org-wide policy | managed |

### Step 3: Compose the config

Draft a config block. Pin the version. Move secrets to env vars.

```json
{
  "mcpServers": {
    "$1": {
      "command": "<binary or npx>",
      "args": ["-y", "<package>@<exact-version>", "<scope-args>"],
      "env": {
        "<TOKEN_VAR>": "${HOST_ENV_VAR_NAME}"
      }
    }
  }
}
```

For `server-filesystem`, scope tightly: pass a single subtree, not
`/` or `~`.

### Step 4: Security checklist (must all be yes before adding)

- [ ] Publisher vetted (`@modelcontextprotocol`, `@anthropic`, or
      manually-read source).
- [ ] Version pinned to a known-good release.
- [ ] No secrets in the JSON (only env-var references).
- [ ] Filesystem scope is bounded.
- [ ] Network egress is bounded if applicable.
- [ ] Database creds are least-privilege.
- [ ] User understands the permissions this server gets.

### Step 5: Show the diff, ask for confirmation

Print the proposed change to the settings file. Highlight what's
new vs what was there. **Wait for explicit confirmation** before
writing.

### Step 6: Add via the CLI

After confirmation, prefer the official CLI over manual JSON edit
where possible:

```bash
claude mcp add $1 <command> <args...>
```

…or edit the JSON if the CLI doesn't cover the scope you need.

### Step 7: Test

```bash
claude mcp list   # or whichever subcommand lists MCP servers
```

Verify the new server appears. Try one query. Confirm it works.

### Step 8: Suggest a checkpoint

If the project is a git repo and `.mcp.json` was committed-relevant:

```bash
git diff .mcp.json
```

Suggest a commit: `git commit .mcp.json -m "mcp: add $1 server (pinned to <ver>)"`. **Wait for explicit verb** before committing.
