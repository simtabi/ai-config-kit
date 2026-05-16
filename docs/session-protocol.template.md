# Session protocol + audit checklist — shared template

This file is the canonical source for the "🔁 Session protocol" +
"🔍 Audit checklist" sections that appear at the top of every
Simtabi project's `docs/SPEC.md`. SPEC §5 issue C5 said to factor
out this duplication; the template lives here in `ai-config-kit`
(the project where the pattern originated) and the other repos
reference it.

When a third Simtabi project adopts this pattern, copy the two
sections below into its SPEC.md unchanged (the project name is
the only variable). When the protocol changes, update this file
first, then propagate to consumer SPECs:

- `simtabi/ai-config-kit/docs/SPEC.md`
- `simtabi/get-installer/docs/SPEC.md`
- _add new consumers here as they appear_

A future cleanup could move this to `simtabi/.github/` as an
org-default; for now keeping it in this repo is fine since the
ecosystem is small.

---

## 🔁 Session protocol (read before everything else)

**Session start**:

1. Read this SPEC end-to-end.
2. Run the audit checklist below (5-line summary at the top of your reply).
3. Read `STATUS.md` if present + `~/.claude/projects/<slug>/memory/MEMORY.md`
   + the latest `CHANGELOG.md` entry.
4. Restate the user's goal in one sentence before any tool call.

**During the work**:

5. **Hallucination guard**: every claim about the codebase comes
   from a live `Read` / `Grep` / shell call. Memory tells you what was
   true when written, not what's true now. Cite `path:line` where
   possible. Phrases that signal you're guessing: "typically",
   "usually", "I believe", "around line ~", round numbers, paraphrases
   of code you haven't opened.

6. **Track progress**: `TaskCreate` / `TaskUpdate` for anything
   beyond 3 steps. Mark `in_progress` before you start; `completed`
   the moment it's done, not in a batch.

7. **Watch for regressions**: re-run the audit checklist after every
   non-trivial edit; don't accumulate a "tests-at-the-end" debt.

8. **Log failures**: when a step fails, surface it in your reply
   immediately: what failed, what you tried, what you'll try next.

9. **Research before guessing**: `WebFetch` the official docs site
   first, project README + spec second, reputable blogs third. Skip:
   Medium content farms, AI-generated blog spam, paywalled pages.

10. **Clarifying questions**: when the request is ambiguous and the
    wrong path costs > 5 minutes to undo, ask once with a numbered
    options list. Not Socratic chains.

**Session end**:

11. **Self-improvement loop**: suggest SPEC updates (new findings →
    §5; finished phases → `[x]`), prompt updates (this section), test
    gaps you noticed.

12. **Hand-off summary**: last paragraph: what changed (paths), what's
    still open (issue ids), what the next agent picks up first.

---

## 🔍 Audit checklist: run this FIRST every session

Before writing code, run a status sweep and report the findings inline.

1. **`pytest -q`**: must be green.
2. **`ruff check src tests`**: must be clean.
3. **`mypy --strict <src-package>`**: must be clean.
4. **CLI surface check**: `python -m <package> --help` should list
   every subcommand documented in `docs/tools/<package>.md`.
5. **README authority check**: exactly ONE `README.md` at the repo
   root + project name + `pip install` line accurate to pyproject.toml.
6. **CHANGELOG check**: `[Unreleased]` section exists; the most
   recent dated entry matches the latest tag.
7. **External-URL drift check**: any URL pinned anywhere in the repo
   (badges, schema $ref, doc links) responds 200/3xx. If you can't
   reach the network, say so.

The 5-line summary at the top of every reply has the form:

```
audit: tests=PASS lint=PASS types=PASS docs=PASS urls=N/A
queue: <one-line description of what I'm about to do>
```

Anything that fails → fix BEFORE the user-facing work, OR flag
explicitly with "blocked on X" and propose a path forward.

---

_The two sections above are kept in lock-step across every
consuming SPEC.md. Source of truth: this file._
