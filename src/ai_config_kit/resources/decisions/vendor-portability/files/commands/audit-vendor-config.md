---
description: Audit AI-vendor config files for drift. Flag CLAUDE.md / .cursorrules / .clinerules / .windsurfrules / AGENTS.md that disagree.
---

Find every AI-vendor config file in the project and audit for drift
against the canonical `AGENTS.md`. Reports only: no edits.

### Step 1: Inventory

```bash
ls -la AGENTS.md CLAUDE.md .cursorrules .clinerules .windsurfrules \
      .aider.conf.yml .github/copilot-instructions.md \
      .claude/CLAUDE.md 2>/dev/null
```

For each file found, record:
- Path
- Line count
- Whether it imports `@AGENTS.md`
- Whether it's a symlink (where its target points)

### Step 2: Canonical-source check

If `AGENTS.md` is missing: flag it. The recommended pattern needs
a canonical source. Suggest creating one (`/init-rules` can help).

If `AGENTS.md` exists but **no other vendor file imports or
symlinks to it**: every vendor file is drifting independently. Flag
each.

### Step 3: Content-drift check

For each non-canonical vendor file:

- Does it `@AGENTS.md`-import? If yes, drift is limited to its
  vendor-specific additions. Skip diff.
- Is it a symlink to `AGENTS.md`? If yes, no drift possible. Skip.
- Otherwise: diff against `AGENTS.md`. Report sections in the
  vendor file that aren't in `AGENTS.md` (and vice versa).

```bash
diff -u <(head -200 AGENTS.md) <(head -200 .cursorrules) | head -40
```

Flag content that should hoist to `AGENTS.md` (rule applies to all
vendors) versus content that's legitimately vendor-specific (slash
commands, vendor-specific skills, etc.).

### Step 4: Symlink integrity

For any symlinks: `readlink <file>` to confirm the target exists +
points where expected. Broken symlinks → flag.

### Step 5: Report

```
| File | Status | Finding | Suggested fix |
|---|---|---|---|
| AGENTS.md | present | 87 lines | (canonical, ok) |
| CLAUDE.md | imports @AGENTS.md | (ok) |: |
| .cursorrules | regular file, 124 lines | drifted from AGENTS.md (12 sections differ) | replace with symlink OR add `@AGENTS.md` import |
| .windsurfrules | symlink to AGENTS.md | (ok) |: |
| .clinerules | (missing) | rule pack inactive for Cline | create symlink if Cline is used |
```

### Step 6: Pause

Don't fix anything. Print the report. Ask the user which drift to
resolve, then propose the smallest diff per fix.
