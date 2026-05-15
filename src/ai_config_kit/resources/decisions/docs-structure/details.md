# docs-structure

Industry-standard repo docs layout shipped as a default. One
authoritative `README.md` at the root, every other prose file under
`docs/`, grouped by audience. Required Simtabi-org files at the
locations GitHub Community-profile recognises.

## What ships

| File | Purpose |
|---|---|
| `CLAUDE.md.docs-structure.fragment` | The standard. What goes at root, what goes in `docs/`, how to organise `docs/` by audience, README TOC requirements. |
| `commands/audit-docs-structure.md` | `/audit-docs-structure` audits the current repo against the standard. |
| `commands/migrate-readmes-to-docs.md` | `/migrate-readmes-to-docs` performs the migration for existing repos: flattens stray READMEs into the main one, moves other `.md` files to `docs/`. |

Auto-applied on `init`. Existing projects benefit by running the
migration slash command + accepting the proposed diff.

## The standard (summary)

**Root** (only these `.md` files allowed):

- `README.md` (one authoritative)
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`
- `LICENSE` (no extension)

**`docs/`** (everything else):

```
docs/
├── README.md                      (optional index linking subdocs)
├── installation.md
├── configuration.md
├── architecture.md
├── release.md
├── shipping-checklist.md
├── SPEC.md                        (agent prompt + design spec)
├── api/                           (auto-generated API reference)
├── architecture/                  (ADRs, diagrams, deep-dives)
├── operators/                     (deploy + run-in-prod docs)
├── users/                         (end-user guides)
├── contributors/                  (dev-onboarding, repo conventions)
└── tools/
    └── <slug>.md                  (per-tool CLI reference, one file per tool)
```

Full rules in the fragment.

## Apply

Auto-applied. Manual:

```bash
ai-config-kit decisions apply docs-structure
```
