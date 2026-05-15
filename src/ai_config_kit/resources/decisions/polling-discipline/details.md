# polling-discipline

Stops the "sleep N seconds then check" anti-pattern before the Claude
Code runtime blocks it.

## Why this exists

The Claude Code harness refuses to run chained `sleep` commands used
as a polling primitive. Symptom:

```
Blocked: sleep 25 followed by: gh run list --limit 3 --workflow=CI
To wait for a condition, use Monitor with an until-loop (e.g.
`until <check>; do sleep 2; done`). To wait for a command you
started, use run_in_background: true. Do not chain shorter sleeps
to work around this block.
```

The block exists because chained sleeps burn the prompt cache TTL
(5 min) repeatedly without amortizing the cost. The runtime offers
purpose-built primitives that do this correctly; agents need to know
to reach for them.

This pack ships a `CLAUDE.md` fragment that documents the right
primitive per situation, and a `/wait-for` slash command that walks
through picking one.

## What ships

| File | Purpose |
|---|---|
| `CLAUDE.md.polling-discipline.fragment` | Rule: never chain sleeps. Tells agents which tool to reach for per waiting scenario. |
| `commands/wait-for.md` | `/wait-for` slash command that proposes the right primitive for the user's situation. |

## Apply

Auto-applied on `ai-config-kit init` (added to
`DEFAULT_DECISIONS_ON_INIT`). Existing installs receive it on the
next CLI invocation via `reconcile()`: the pack is new, so the
non-clobbering apply ships it without overwriting anything.
