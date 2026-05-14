# safety-net-commits

Prompts the user to commit a git checkpoint before significant
operations so every state-changing action stays in history.

## What ships

| File | Purpose |
|---|---|
| `CLAUDE.md.safety-net-commits.fragment` | Rules for when to suggest a checkpoint commit. Lists the trigger events (before destructive ops, after multi-step work, on session-end). |
| `commands/checkpoint-now.md` | `/checkpoint-now` performs a git add + commit with a generated message. Prompts before running. |
| `commands/review-changes.md` | `/review-changes` shows the current uncommitted diff in a reviewable format. |

Auto-applied on `init`.

## Rules at a glance

The fragment instructs agents to suggest a commit (never to make one
without explicit instruction) at these moments:

1. **Before any destructive operation** in any tracked directory:
   `git reset --hard`, branch deletes, force-push, large refactor,
   bulk-rename.
2. **After every milestone** in multi-step work: every 3-5 successful
   tool calls in a chain.
3. **At session end** as part of the hand-off summary.
4. **Before `ai-configurator install` / `repair` / `decisions apply
   --force`**: anything that rewrites the content dir non-trivially.
5. **When the working tree gets > 10 uncommitted files**: review
   debt accumulates fast.

The agent ALWAYS asks first. Per the user's standing CLAUDE.md rule:
no `git add` / `commit` / `push` without an explicit verb.

## Apply

Auto-applied. Manual:

```bash
ai-configurator decisions apply safety-net-commits
```
