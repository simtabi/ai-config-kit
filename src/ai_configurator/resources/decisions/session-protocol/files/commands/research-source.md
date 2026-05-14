---
description: Look up a fact (API signature, flag semantics, current spec). Official docs first, never content farms.
argument-hint: <topic>
---

You need a fact about $1 that you don't have from this session's
reads. Don't guess. Don't paraphrase from training data — that's a
year+ stale.

Research order (highest trust first):

1. **Official documentation**
   - `docs.<vendor>.com`, `developer.<vendor>.com`, the framework's
     own docs site.
   - Use `WebFetch <url>` to pull the exact page.
   - Look for a version selector — read the *current stable* docs,
     not the latest pre-release unless the user is on it.

2. **Project's own GitHub** — README, CHANGELOG, the `docs/` tree,
   release notes for the version under discussion.
   - `WebFetch https://github.com/<org>/<repo>/blob/<ref>/<path>`

3. **Tagged releases** — when behaviour changed across versions, the
   CHANGELOG entry for the version in question is the authoritative
   answer.

4. **Reputable blogs**
   - Author of the project / framework, on their own site.
   - Lobste.rs / Hacker News front-page (curation signal).
   - Mailing list archives + GitHub Discussions tagged "answered".

5. **Stack Overflow** — answers with > 50 upvotes and a recent edit
   date (within ~2 years of the version under discussion).

6. **Last resort**: ask the user with a one-line question + your
   best guess.

**Skip** (these are higher risk than asking):

- Random Medium / dev.to articles with no author authority.
- Content-farm sites (`tutorialspoint`, `geeksforgeeks` when the
  topic is fast-moving — they're often years stale).
- AI-generated blog spam (look for too-perfect prose + zero edit
  history).
- Paywalled pages without context.
- StackOverflow answers under 5 upvotes from > 5 years ago.

After you find the answer, **cite the URL** when you use the fact:

> Per <https://docs.example.com/api/v3/users#create>, the
> `Authorization` header is required and must be `Bearer …`.

Citation is non-optional. It lets the user verify and protects future
sessions from inheriting a stale fact.
