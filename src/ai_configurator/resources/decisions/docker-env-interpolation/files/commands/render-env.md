---
description: Walk the project's env files + propose the render-env.sh invocation that resolves all ${VAR} references. Don't execute without confirmation.
---

Walk the current project's env-file setup, then propose how to use
`render-env.sh` (shipped at `~/.claude/scripts/render-env.sh`).

### Step 1: Inventory

```bash
ls -la .env* env/*.env 2>/dev/null
```

Identify:
- The primary input (usually `.env`)
- Any local override (`.env.local` — should be gitignored)
- Any example template (`.env.example` — committed)
- Any per-stage variants (`.env.production`, `.env.staging`)
- Whether `.env` is in `.gitignore`

If `.env` is NOT gitignored and contains values that look like
secrets, FLAG IT before proceeding.

### Step 2: Detect the consumer

```bash
grep -lE "(docker-compose|compose\.yml|compose\.yaml)" -r . --max-depth=3 2>/dev/null | head -5
grep -lE "(env_file:|environment:)" docker-compose*.yml compose*.yml 2>/dev/null
```

Is the project using:
- **docker-compose only** → Compose interpolates `${VAR}` natively
  in `.env` already; rendering may be unnecessary. Suggest
  `docker compose config` to inspect the resolved view instead.
- **A mix of Docker + non-Docker tools** that read `.env` directly →
  rendering is justified.
- **Kubernetes / Nomad / raw env loading** → rendering is the right
  call.

### Step 3: Propose the command

```bash
~/.claude/scripts/render-env.sh \
    --example .env.example \      # defaults (lowest)
    --input .env \                # primary
    --local .env.local \          # per-machine overrides (highest non-shell)
    --output .env.resolved \
    --strict                       # fail on any unresolved ${VAR}
```

Show the exact command for THIS project. If a layer file doesn't
exist, omit that flag. Don't include `--local` if `.env.local`
isn't gitignored.

### Step 4: Document the wire-in

Propose where the rendered file feeds into:

- **docker-compose**: `docker compose --env-file .env.resolved up`
- **CI**: rendering step before any deploy job. Validate `! grep -E '\\$\\{[A-Z_]+\\}' .env.resolved`.
- **Kubernetes**: ConfigMap from the resolved file.

### Step 5: Gitignore

Always add the output to `.gitignore` if it isn't already:

```
.env.resolved
.env.local
```

Don't commit a rendered env — it almost always contains secrets
that were resolved from the shell environment.

### Step 6: Pause for confirmation

Don't run `render-env.sh` yourself. Print the proposed command and
the gitignore additions. The user runs it when they're ready.

If the user says "go": run it, confirm exit code 0, show a one-line
summary (`<N> keys resolved, output at <path>`). Suggest a
checkpoint commit per the `safety-net-commits` rule.
