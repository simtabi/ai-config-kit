---
description: Propose a .claude/rules/ layout when CLAUDE.md is too big. Read the file, group rules by topic + path, propose a diff.
---

The project's `CLAUDE.md` has grown past the 200-line guidance from
<https://code.claude.com/docs/en/memory#write-effective-instructions>.
Propose a `.claude/rules/` layout that splits it into topic-scoped
files.

### Step 1: Read + classify

Read the project's `CLAUDE.md`. For each top-level section (h2 or
h3), classify it as one of:

- **Always-on**: applies everywhere; stays in `CLAUDE.md`.
- **Path-scoped**: applies only to files matching some glob.
  Becomes a `.claude/rules/<topic>.md` with `paths:` frontmatter.
- **Procedure**: multi-step workflow. Should be a
  `.claude/skills/<name>/SKILL.md`, not a rule.

### Step 2: Propose a layout

Output a tree:

```
.claude/
├── rules/
│   ├── code-style.md       (paths: ["**/*.{ts,tsx,js,jsx}"])
│   ├── testing.md          (paths: ["**/tests/**", "**/*.test.*"])
│   ├── security.md         (paths: ["src/auth/**", "src/api/**"])
│   └── git-workflow.md     (always-on; no paths frontmatter)
├── skills/
│   └── deploy/
│       └── SKILL.md        (was: §"Deployment" in CLAUDE.md)
└── CLAUDE.md               (slimmed to ~80 lines: identity, hierarchy, top-level rules)
```

For each new file, show:

- The proposed path
- The `paths:` frontmatter (when scoped)
- The section(s) from the existing `CLAUDE.md` that move into it
- An estimated line count

### Step 3: Validate

Check the proposed layout:

- Does every line from the original `CLAUDE.md` land somewhere?
  (Anti-loss check.)
- Does the resulting `CLAUDE.md` come in under 200 lines? Aim for
  120 or fewer.
- Are any rules so unique they shouldn't be path-scoped? (Some are
  cross-cutting: keep them top-level.)

### Step 4: Pause

**Stop here.** Print the proposal. Ask me to confirm before writing
any files. The reorganisation should be a single reviewable diff,
not a series of mid-conversation file edits.

### Reference

- `.claude/rules/` schema: <https://code.claude.com/docs/en/memory#organize-rules-with-claude/rules/>
- Skills schema: <https://code.claude.com/docs/en/skills>
- Path-specific rules: <https://code.claude.com/docs/en/memory#path-specific-rules>
