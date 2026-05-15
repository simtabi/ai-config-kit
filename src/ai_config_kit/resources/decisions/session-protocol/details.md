# session-protocol

A disciplined shape for every Claude Code session: audit on start,
track progress + log failures + research before guessing during work,
self-improve on end. Anti-hallucination throughout.

## Why this matters

Without a session protocol, common failure modes:

- **Drift between docs and reality**: last-session's claims aren't
  re-verified, the model paraphrases stale facts.
- **Hallucinated APIs / paths / line numbers**: the model invents
  what it doesn't know.
- **Half-applied changes**: tests aren't re-run after each edit,
  failures surface late.
- **Silent retries**: a step fails, the model retries once with no
  signal, then proceeds as if everything is fine.
- **Outdated knowledge baked in**: the model uses a 2-year-old API
  shape because it didn't bother to check the current docs.
- **Scope drift**: the user's ask was ambiguous, the model picked the
  wrong interpretation, 30 minutes later the work is wrong.

This pack ships a `CLAUDE.md` fragment that codifies the protocol, plus
five slash commands the user (or the model itself) can invoke at the
right moments.

## What ships

| File | Purpose |
|---|---|
| `CLAUDE.md.session-protocol.fragment` | Global rules to add to your `CLAUDE.md` so the protocol fires every session, even without an explicit slash command. |
| `commands/session-start.md` | `/session-start`: run at the top of a session. Audit, restate goal, scan memory. |
| `commands/session-end.md` | `/session-end`: close-out: hand-off summary + suggested SPEC/prompt improvements. |
| `commands/track-progress.md` | `/track-progress`: set up a task list for a non-trivial multi-step request. |
| `commands/research-source.md` | `/research-source <topic>`: official docs first, then trusted blogs, never content farms. |
| `commands/clarify.md` | `/clarify`: ask one focused clarifying question when the request is ambiguous. |

## Apply

```bash
ai-config-kit decisions apply session-protocol
```

Then optionally append the fragment to your live `CLAUDE.md`:

```bash
cat ~/.config/claude-config/content/claude/CLAUDE.md.session-protocol.fragment \
  >> ~/.config/claude-config/content/claude/CLAUDE.md
ai-config-kit sync -m "adopt session-protocol"
```

This pack is **auto-applied** by `ai-config-kit init`: new
content dirs get the slash commands automatically. Re-running `init`
on an existing dir skips files that already exist; pass `--force` to
overwrite.
