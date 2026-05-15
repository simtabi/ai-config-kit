---
description: Audit the current project's CLAUDE.md against the 2026 best-practices fragment. Report concrete fixes; do not edit.
---

Audit the project's `CLAUDE.md` file(s) against the rules from the
`claude-best-practices` decision pack. **Report findings only: do
not change any file** until I confirm a fix.

### Step 1: Locate every CLAUDE.md in scope

```bash
ls -la CLAUDE.md .claude/CLAUDE.md CLAUDE.local.md ~/.claude/CLAUDE.md 2>/dev/null
find . -name "CLAUDE.md" -not -path "*/node_modules/*" -not -path "*/.venv/*" 2>/dev/null
```

For each file found, report path + line count.

### Step 2: Size audit

For every CLAUDE.md > 200 lines, flag it as **violates size guidance**.
Cited: <https://code.claude.com/docs/en/memory#write-effective-instructions>

### Step 3: Hierarchy audit

- Is there a project-level CLAUDE.md (`./CLAUDE.md` or
  `./.claude/CLAUDE.md`)? If not, suggest `claude /init`.
- Is there a `CLAUDE.local.md` that's NOT in `.gitignore`? Flag it.
  It's about to be committed by accident.
- Are there sibling subdirectory CLAUDE.md files that contradict
  each other? Read both and report any directly conflicting rule.

### Step 4: Anti-pattern grep

In each CLAUDE.md, look for:

- **Secrets**: API keys (regex: `(api[_-]?key|secret|token|password)`,
  hex strings ≥ 20 chars). Flag with severity = **critical**.
- **Multi-step procedures**: numbered lists with > 5 steps. Suggest
  moving to a skill.
- **Conversation paste**: "User said X, I replied Y, then…" patterns.
  Suggest moving to auto memory.
- **Outdated references**: `commands/` mentioned for new work: the
  modern path is `skills/<name>/SKILL.md`.

### Step 5: Structural fixes

- Are headings used? Long flat lists hurt scanning.
- Are bullets specific enough? "Use 2-space indentation" beats
  "Format code properly".
- Block-level HTML comments are stripped before reaching the
  model: confirm the user knows they cost nothing.

### Step 6: Report

Output a markdown table:

```
| File | Line | Finding | Severity | Suggested fix |
|---|---|---|---|---|
| ./CLAUDE.md | 247 | violates 200-line cap | medium | move §"Build commands" to `.claude/rules/build.md` |
| ./CLAUDE.md | 89 | hex-looking secret? | critical | move to `.env`; this is sent to every Claude session |
| ./CLAUDE.md | 156 | 12-step deployment procedure | medium | extract to `.claude/skills/deploy/SKILL.md` with `disable-model-invocation: true` |
```

Then propose the **smallest diff** that resolves each high-severity
finding. Pause for confirmation before applying.

### Do not

- Don't edit any file.
- Don't `git add` / `git commit`.
- Don't paraphrase file contents: cite `path:line` only.
- Don't grep arbitrary files outside the CLAUDE.md set.
