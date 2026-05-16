# Claude Code permission profiles

`ai-config-kit profiles` switches the `permissions.allow` + `permissions.deny`
blocks of a Claude Code `settings.json` to a curated set tailored to a
specific stack. Six profiles ship today.

## What's a profile?

A small JSON file under `ai_config_kit/resources/profiles/` listing
allow + deny patterns. Profiles can `_meta.extends` other profiles to
inherit their allow + deny lists. The resolver unions both lists and
de-duplicates while preserving order.

## Built-in profiles

| Name | Scope | Summary |
|---|---|---|
| `global` | global | Inspection-only baseline (Read, Grep, Find, git status, gh queries). Walks into any directory safely. |
| `python` | project | Adds pytest, ruff, mypy, uv, pip-audit, git mutations, gh PR/issue creation. |
| `laravel` | project | Composer + artisan + vendor/bin (Pest, PHPUnit, Pint, PHPStan, Rector), Sail. Denies `migrate:fresh` + `db:wipe`. |
| `node` | project | npm/pnpm/yarn/bun, TS toolchain, framework CLIs (next, vite, astro), Vitest/Playwright. |
| `go` | project | go toolchain, gofmt/goimports, golangci-lint, govulncheck. |
| `mixed` | project | **Default.** Everything: Python + PHP + JS + Go + network diagnostics + Docker. |

Every project profile extends `global`, so the baseline read/inspect
permissions always apply.

## Usage

```bash
# Inspect what's available
ai-config-kit profiles list

# See what a profile resolves to (full JSON, parent profiles merged)
ai-config-kit profiles show          # default: mixed
ai-config-kit profiles show python
ai-config-kit profiles show laravel  | jq .

# Write to the project's <src_dir>/settings.json (dry-run by default)
ai-config-kit profiles apply python
ai-config-kit profiles apply python --apply

# Write to the global ~/.claude/settings.json
ai-config-kit profiles apply global --scope global --apply
```

`--json` flag works on `profiles list` for scripting.

## Architecture

```text
permissions:
  allow: [<global allow> | <profile-specific allow>]
  deny:  [<global deny>  | <profile-specific deny>]
```

When you run `profiles apply mixed --scope project`, the resolver:

1. Reads `mixed.json`.
2. Recursively reads every name in `_meta.extends` (currently just `global`).
3. Concatenates parent + self for `permissions.allow` and `permissions.deny`.
4. De-duplicates each list while preserving first-seen order.
5. Drops the `_meta` block (it's internal-only; Claude Code never reads it).
6. Backs up any existing `settings.json` to `settings.json.before-profile`.
7. Writes the resolved JSON.

## Design principles (lifted from the proposal)

1. **Global is inspection-only.** Read, grep, find, status — everything
   that observes without changing. A fresh checkout + Claude can read
   but not write.
2. **Project configs add write capability.** Edit, Write, language
   toolchain, git mutations, PR creation. Each project explicitly opts in.
3. **Deny rules are layered.** Global denies catch system-destructive
   patterns; project denies catch project-specific footguns
   (`migrate:fresh`, `db:wipe`).
4. **Deny beats allow.** When the same pattern appears in both,
   Claude Code's resolver picks deny. Use this to safely broad-allow
   like `Bash(git:*)` while denying force-push variants.
5. **Publishing is never auto-approved.** Every profile denies
   `twine upload`, `npm publish`, `cargo publish`, `composer publish`,
   `gem push`, `goreleaser release`, `gh release create`. Irreversible
   actions always prompt.

## Local overrides

The profile lands at `<src_dir>/settings.json`. For per-machine personal
overrides, use Claude Code's `<src_dir>/settings.local.json`
(git-ignored convention) — it merges on top of the profile-installed
file at runtime.

## Verifying

After `profiles apply --apply`:

```bash
claude config list
```

shows the merged effective config. Look for your profile's allow
patterns and the global denies.

## Custom profiles

Today the resolver only loads built-in resource files. To ship a
custom profile, copy one of the built-ins into
`<src_dir>/decisions/your-profile.json` and apply it via the
`decisions install <url>` flow (Phase B) — though that path
overwrites pack files, not settings.json. A first-class
`ai-config-kit profiles add <name> <path>` verb is queued for v0.6.
