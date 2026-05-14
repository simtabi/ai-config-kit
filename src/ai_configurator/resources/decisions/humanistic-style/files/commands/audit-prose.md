---
description: Audit prose (READMEs, docs, commit bodies) for AI-tell phrases and em-dash overuse. Reports only — no edits.
argument-hint: <path-or-glob>
---

Audit prose files at $1 for AI tells. Default scope: every `.md` /
`.mdx` / `.rst` / `.txt` file in the project not under `node_modules`,
`.venv`, `.git`, or `vendor`.

### Step 1: Find files

```bash
find . -type f \( -name "*.md" -o -name "*.mdx" -o -name "*.rst" -o -name "*.txt" \) \
  -not -path "*/node_modules/*" \
  -not -path "*/.venv/*" \
  -not -path "*/.git/*" \
  -not -path "*/vendor/*" \
  -not -path "*/dist/*" \
  -not -path "*/build/*"
```

If $1 is provided, narrow to that path or glob.

### Step 2: Banned-phrase grep

Read the canonical list from
`~/.config/claude-config/content/claude/humanistic-style/banned-phrases.txt`
when available. Fall back to the inline list below.

For each file, run grep -nFi against each phrase. Capture `file:line`
matches.

Phrases (one per line, case-insensitive):

```
delve into
dive into
in this article
let's explore
let's dive into
in conclusion
to summarize
by following these steps
as we can see
robust and scalable
cutting-edge
state-of-the-art
best-in-class
seamless
comprehensive
essentially
fundamentally
in essence
at its core
leverage
powerful
note that
**important:**
*important:*
let's go ahead
you'll notice that
in the realm of
the world of
```

### Step 3: Em-dash audit

```bash
grep -nE "[a-zA-Z] — [a-zA-Z]" <file>  # em-dash flanked by letters
grep -nE " — and —| — but —" <file>     # em-dash sandwich
```

For each match, judge: is this a genuine aside (keep), or a "make it
sound sophisticated" tic (replace with comma / colon / period)?

### Step 4: Sentence-opener pattern

Flag opening sentences of paragraphs starting with: "Let's", "Now",
"You'll", "It's worth", "Note that", "Importantly".

### Step 5: Report

Markdown table:

```
| File | Line | Phrase | Suggested replacement |
|---|---|---|---|
| docs/intro.md | 12 | "delve into" | "explore" or just "open" |
| README.md | 47 | "By following these steps," | (delete; lead with the action) |
| docs/api.md | 89 | " — and — " | comma + semicolon |
```

### Step 6: Pause

Stop after the report. Do not edit. The user picks fixes manually
or asks for a follow-up pass.

Refuse to edit prose unless I say so explicitly. AI-tell removal is
a judgement call; an automated rewrite often makes things worse.
