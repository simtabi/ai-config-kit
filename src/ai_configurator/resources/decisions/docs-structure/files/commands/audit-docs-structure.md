---
description: Audit the current repo against the docs-structure standard. Reports only.
---

Audit the current project against the docs-structure standard.
Report findings: do NOT edit.

### Step 1: Root-file census

```bash
ls -1 *.md LICENSE 2>/dev/null
```

Allowed at root (per the standard): `README.md`, `CHANGELOG.md`,
`CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`,
and (allowed exception) `SPEC.md` if there's an agent-prompt for
this repo.

Flag anything else.

### Step 2: docs/ presence

```bash
ls -la docs/ 2>/dev/null
```

If `docs/` is missing AND there are stray `.md` files at root, the
migration is needed. If `docs/` exists but has no `README.md` (the
docs index), suggest creating one.

### Step 3: README size + TOC

```bash
wc -l README.md
grep -n "^## Table of contents\|^## TOC\|^- \[" README.md | head -20
```

Flag:
- README > 300 lines (too much detail at root; move to `docs/`)
- No TOC (every README should have one)
- TOC links that don't resolve (anchor mismatch)

### Step 4: docs/ subgroup audit

If `docs/` exists, check whether files are grouped:

```bash
find docs -maxdepth 2 -type f -name "*.md" | head -30
```

If `docs/` has more than 8 top-level files, suggest splitting by
audience (`users/`, `operators/`, `contributors/`, `architecture/`).

### Step 5: Required-files audit

The Simtabi org standard requires these at root:

```bash
for f in README.md LICENSE CHANGELOG.md CONTRIBUTING.md CODE_OF_CONDUCT.md SECURITY.md .gitignore .editorconfig; do
    if [ -f "$f" ]; then echo "  [ok]   $f"; else echo "  [MISS] $f"; fi
done
```

Flag any missing.

### Step 6: Report

```
| Finding | Severity | Suggested fix |
|---|---|---|
| ROADMAP.md at root | medium | move to docs/SPEC.md or docs/roadmap.md |
| README.md is 412 lines | high | extract installation + architecture into docs/ |
| docs/ has 14 top-level files | medium | regroup into users/ + operators/ + contributors/ |
| .editorconfig missing | low | add one (see Simtabi org standard) |
```

### Step 7: Do not migrate without confirmation

Print the proposed migration plan. Pause. Ask for "go" before doing
anything destructive. For the actual move, defer to
`/migrate-readmes-to-docs`.
