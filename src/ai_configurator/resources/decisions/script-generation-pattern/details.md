# script-generation-pattern

Ships a slash command and a CLAUDE.md fragment that teach the model to
use a **generator-script-first** workflow for tasks that involve many
files or content patterns that may trigger a content-filter block.

## The problem

When a request involves creating ~8+ files, or files with long /
sensitive-looking / repetitive content, two failure modes hit:

1. **Content filtering policy block** — the API rejects the streamed
   output mid-response. The session is left in a half-applied state and
   the model can't easily recover.
2. **Token waste** — streaming long file contents as tool outputs costs
   far more than the equivalent generator script.

## The pattern

Instead of streaming N file contents inline:

1. **Write a generator script** (Python or Bash) that contains the file
   contents in source form.
2. **Run the script** via Bash; let it write the files to disk.
3. **Read back** the generated files to verify they match the design spec.
4. **Validate** (lint, type-check, tests, schema validation) and report.

The model's role shifts from "stream 30 file contents in sequence" to
"write the generator + verify the result" — a smaller, more reliable
surface.

## When NOT to use it

- Small changes (3–5 files).
- Files with significant unique content where a script would be just as
  long as the inlined output.
- One-shot exploration where speed matters more than reliability.

## What this pack ships

- `commands/generate-via-script.md` — slash command (`/generate-via-script`)
  that prompts the model into the pattern.
- `CLAUDE.md.script-generation-pattern.fragment` — appendable rules to
  paste into your `CLAUDE.md` so the pattern is always loaded, not just
  on slash invocation.

## Apply

```bash
ai-configurator decisions apply script-generation-pattern
```

Then append the fragment to your `CLAUDE.md` (or read it and adapt):

```bash
cat ~/.config/claude-config/content/claude/CLAUDE.md.script-generation-pattern.fragment \
  >> ~/.config/claude-config/content/claude/CLAUDE.md
ai-configurator sync -m "adopt script-generation-pattern"
```
