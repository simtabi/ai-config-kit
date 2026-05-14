---
description: Close out a session — quality gates, hand-off summary, suggested SPEC/prompt updates, memory writes.
---

Run the session-end protocol before signing off.

1. **Final quality-gate sweep**:
   ```bash
   pytest -q          # or project equivalent
   ruff check .
   mypy .
   git status --short
   git log --oneline @{u}.. 2>/dev/null || git log --oneline -3
   ```
   All four must be green. If anything is red, fix it or flag it
   explicitly in the hand-off.

2. **Self-improvement scan** — propose, but do NOT apply without my
   green-light:
   - SPEC.md updates: new issues to log in §5; phases to mark `[x]`.
   - Prompt updates: patterns you'd want the next agent to follow
     that aren't in the current `CLAUDE.md` / session-protocol pack.
   - Test gaps you noticed but didn't close.
   - Memory entries: write any non-obvious facts you learned to
     `~/.claude/projects/<slug>/memory/` so the next session has them.

3. **Hand-off summary** — last paragraph of your reply covers:
   - **What changed** (list of files touched, cite `path:line` for the
     most important hunks)
   - **What's still open** (cite issue / task / spec-phase ids)
   - **What the next session should pick up first**
   - **Anything uncommitted** that needs an explicit verb from me to
     commit / push / tag

Keep it tight — one paragraph max for the hand-off; the gate output
+ self-improvement proposals can be longer.
