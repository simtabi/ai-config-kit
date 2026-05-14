# Personal Claude Code conventions

Universal defaults loaded into every Claude Code session. Per-project
and per-org `CLAUDE.md` files complement these rules; they never
replace them.

## Identity

Set these in every fresh clone, scoped per-repo (no global config):

```bash
git config user.email "<your-noreply>@users.noreply.github.com"
git config user.name  "Your Name"
```

## Code quality gates

Before saying work is done, run all of these and report the result:

- Tests: language-appropriate
- Lint: language-appropriate
- Type-check: where applicable
- Build: where applicable

Don't suppress failures with `# noqa`, `// eslint-disable`, etc. without
a one-line comment explaining why.

## Scope discipline

- Stay in the scope I gave you. "Fix everything" means fix identified
  bugs and obvious inconsistencies, not invent new features.
- Don't add files I didn't ask for unless they fit a documented
  required-files list and are missing.
- Prefer `Edit` over `Write` for existing files.
- When in doubt, ask one short question rather than guess.

## Verification before pinning

Whenever about to commit a value that points at an external resource
(SHA, release tag, URL, API endpoint), verify it resolves first.

## Anti-hallucination

- File paths, symbols, function names: grep before citing.
- Counts and metrics: count from the source, never tally mentally.
- Audit results that return zero: sample one manually before declaring clean.
- If a fact can't be verified, say "haven't verified" rather than asserting.

## History is additive

Destructive git operations (reset --hard, force-push, branch delete,
rebase that loses commits) require an explicit verb from me. Soft
directions like "clean things up" do **not** authorise them.

## Tone

- Concise. Match response length to question complexity.
- No emoji.
- No filler ("Great question!", "Let me…", "I'll go ahead and…").
- Cite code as `path:line` where possible.
