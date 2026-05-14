---
description: Generate many files via a runtime script rather than streaming their contents inline.
---

This task involves creating many files or content that risks a
content-filter block. Switch to the generator-script-first pattern:

1. **Write a generator script** (Python or Bash) holding the file
   contents in source form. Save it under `scripts/` in the repo, or
   `/tmp/` if it's strictly one-shot. The script should be idempotent:
   re-running overwrites only the files it owns.

2. **Run it** via Bash. The script writes files to disk.

3. **Read back** the generated files. Spot-check the most structurally
   important ones; for repetitive output, read 2–3 representative
   samples.

4. **Validate**:
   - Lint: run the project's linter on the new files.
   - Type-check: if applicable.
   - Tests: run the test suite or a relevant subset.
   - Schema / format: verify JSON / YAML / TOML / Markdown structure
     where relevant.

5. **Report**: name what was generated, what passed each gate, what
   failed. Cite paths as `path:line` for any callouts.

Pause before step 1 if any of these are true and confirm with the user:

- The script would need to take destructive actions (delete existing
  files outside its own outputs).
- The output target is outside the current repo.
- Any generated file matches a `secret_patterns` entry from
  `~/.config/claude-config/`.
