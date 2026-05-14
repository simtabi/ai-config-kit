---
description: Run at the top of every session. Audit, restate goal, scan memory + git state.
---

Run the session-start protocol. Do **not** touch any code or write
any reply text until this is done.

1. **Read project state files** if they exist:
   - `SPEC.md` (project spec + standing prompt)
   - `STATUS.md` (current sprint state)
   - `CLAUDE.md` (project conventions)
   - The latest entry in `CHANGELOG.md`

2. **Read project memory**:
   - `~/.claude/projects/<slug>/memory/MEMORY.md`
   - Spot-check the most relevant per-file memories

3. **Run the project's quality gates** (whichever apply):
   ```bash
   pytest -q          # or the project's test command
   ruff check .       # or eslint / phpcs / golangci-lint
   mypy .             # or tsc --noEmit / phpstan
   git status --short
   ```

4. **Check the most recent commits** to understand what shipped last:
   ```bash
   git log --oneline -5
   ```

5. **Restate the user's goal in one sentence**. If anything is
   ambiguous, ask one clarifying question with options BEFORE
   touching code.

6. **Report a 5-line summary** as the top of your first reply:
   - Test/lint/type-check status
   - Last commit subject + sha
   - Anything red on disk (failing tests, dirty tree)
   - Your restated understanding of the user's goal
   - The first concrete tool call you'll make

Only after this six-step start do you begin the actual work.
