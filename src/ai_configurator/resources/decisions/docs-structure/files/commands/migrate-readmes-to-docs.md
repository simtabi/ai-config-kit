---
description: Migrate stray README / topic .md files at root into docs/. Proposes the diff; user confirms before any move.
---

Migrate the current project to the docs-structure standard:

1. Stray `.md` files at root (not in the allowed set) move to
   `docs/<sensible-location>/`.
2. Existing `docs/` is preserved and extended.
3. The main README gets a TOC + links to moved subdocs if absent.

### Pre-flight

Refuse to proceed if any of these are true:

- The repo has uncommitted changes (run `git status --short`; if
  output is non-empty, ask the user to commit first or pass
  `--allow-dirty`).
- `docs/` exists AND already follows the standard (run
  `/audit-docs-structure` first; if it returns clean, no migration
  needed).

### Plan

For each file currently at root that's not in the allowed set:

| Current path | Proposed path | Reason |
|---|---|---|
| `ROADMAP.md` | `docs/SPEC.md` (append) | merge roadmap into the spec |
| `ARCHITECTURE.md` | `docs/architecture.md` | per the standard |
| `INSTALL.md` | `docs/installation.md` | per the standard |
| `NOTES.md` | `docs/contributors/notes.md` | dev-onboarding |
| `random-thing.md` | `docs/random-thing.md` | catch-all; user picks better grouping |

Print this table. **Pause. Ask the user**: which moves are correct?
Are there any to skip? Any to merge instead of move?

### Execute (after confirmation)

For each approved move:

```bash
mkdir -p $(dirname <new-path>)
git mv <old-path> <new-path>   # if repo is git
# OR
mv <old-path> <new-path>
```

Update the main `README.md` to link to the new locations:

```markdown
## Documentation

- [Installation](docs/installation.md)
- [Architecture](docs/architecture.md)
- [Roadmap](docs/SPEC.md)
- (etc.)
```

### Post-migration audit

Re-run `/audit-docs-structure`. Verify it returns clean.

### Checkpoint commit

After the migration succeeds, **suggest a checkpoint commit** so
the move is in git history and reviewable:

```
git commit -am "docs: migrate root .md files to docs/ per docs-structure standard"
```

Do NOT commit without asking. The user has the explicit verb.
