---
description: Commit current uncommitted work as a checkpoint. Generates a message from the diff. Prompts before running.
argument-hint: [optional commit message]
---

Create a checkpoint commit of the current uncommitted work. Pause
for explicit confirmation before any git write.

### Step 1: Pre-flight

```bash
git status --short
git diff --stat
```

If `git status --short` is empty, say so and stop. Nothing to
commit.

### Step 2: Secret-scan

```bash
git status --short | grep -E "(\.env|\.credentials|\.pem|\.key|\.token|\.netrc|\.npmrc|\.pypirc)$"
```

If anything matches, STOP. Print the offending paths + suggest
adding them to `.gitignore` before any commit. Do not proceed.

### Step 3: Compose message

If $1 is provided, use it as the subject line. Otherwise, generate
one from the diff:

- If most changes are in `docs/`: `docs: <one-line summary>`
- If mostly in `tests/`: `test: <one-line summary>`
- If mostly in `src/`: `<scope>: <one-line summary>` where `<scope>`
  is the touched module
- Otherwise: `checkpoint: <one-line summary>`

Body should explain the why (a sentence or two), not the what (the
diff already says that).

Subject ≤ 72 chars, imperative mood. No emoji, no `Co-Authored-By`
trailers unless the user asked.

### Step 4: Show the proposed commit

Print:

```
Proposed commit:

  <subject>

  <body>

Files: <N> changed, +<A> -<B> lines
```

### Step 5: Ask for the verb

Wait for an explicit "commit" / "go" / "yes" from the user. Anything
else (silence, redirect, "wait") means stop. Don't infer consent.

### Step 6: Commit

```bash
git add -A
git commit -m "$SUBJECT" -m "$BODY"
```

Don't `git push`. The user has the explicit verb for that.

### Step 7: Report

Print the new commit SHA + a one-line summary:

```
✓ checkpoint <sha-short>: <subject>
```
