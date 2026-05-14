---
description: Show uncommitted changes grouped by file type + size, ready for review. Read-only.
---

Surface the current uncommitted diff in a reviewable format.

### Step 1: Summary

```bash
git status --short | wc -l
git diff --stat
```

Print:
- Number of files changed
- Total lines added / removed
- Quick "is this a small/medium/large diff" call

### Step 2: Group by type

```bash
git status --short | awk '{print $2}' | awk -F. '{print $NF}' | sort | uniq -c | sort -rn
```

Bucket by extension:
- `.py`, `.ts`, `.js`, `.php`, `.go`, `.rs` → code
- `.md`, `.mdx`, `.rst`, `.txt` → docs
- `.json`, `.yml`, `.yaml`, `.toml`, `.ini` → config
- `.test.*`, files in `tests/` → tests
- Other → other

### Step 3: Per-bucket diff hint

For each bucket with > 0 changes, list the files + a one-line hint
for what to review:

```
code (3 files, +120 -45):
  src/manager.py        (added reconcile() method + helpers)
  src/cli.py            (wired reconcile into main())
  tests/test_manager.py (4 new test cases)
```

### Step 4: Risk callouts

Flag anything that needs special review:

- Files matching `.env` / `.credentials` / SSH-key patterns
  (CRITICAL — should be in .gitignore, not the diff)
- Schema files (`*.schema.json`, `*.graphql`, migration files)
  → breaking-change risk
- `pyproject.toml` / `package.json` / `composer.json` → dependency
  change
- `.github/workflows/*.yml` → CI surface area
- `Dockerfile` / `docker-compose.yml` → deploy surface area

### Step 5: Suggestions

Based on the diff size + grouping, suggest:

- "Split into multiple commits by bucket" if the diff spans 3+
  buckets with substantive changes each.
- "Single commit looks right" if the diff is focused on one bucket.
- "Checkpoint now" if > 10 files / > 200 lines uncommitted.
- "Read first, then decide" if anything risky is in the diff.

### Step 6: Do not commit

This is read-only. Use `/checkpoint-now` to actually create the
commit, with the user's explicit verb.
