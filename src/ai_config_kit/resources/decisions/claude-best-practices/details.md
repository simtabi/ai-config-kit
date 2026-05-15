# claude-best-practices

Distils the current Claude Code documentation
(<https://code.claude.com/docs/en/memory>,
<https://code.claude.com/docs/en/skills>,
<https://code.claude.com/docs/en/hooks>) into rules every CLAUDE.md
author should follow.

This pack is **auto-applied** by `ai-config-kit init`. New
versions of `ai-config-kit` may extend it; the **reconcile**
mechanism applies those extensions to existing users on the first
command after `pip install --upgrade ai-config-kit`.

## What ships

| File | Purpose |
|---|---|
| `CLAUDE.md.claude-best-practices.fragment` | Global rules to append to your `CLAUDE.md`. Covers size, hierarchy, imports, skills vs commands, hook usage, common anti-patterns. Every claim cites a `code.claude.com` URL. |
| `commands/audit-claude-md.md` | `/audit-claude-md` slash command that audits the user's CLAUDE.md against the rules and reports concrete fixes. |
| `commands/init-rules.md` | `/init-rules` slash command that proposes a `.claude/rules/` layout (path-scoped rules) when a CLAUDE.md is growing past 200 lines. |

## Rules at a glance

1. **Target under 200 lines per CLAUDE.md**: longer files reduce
   adherence (cited).
2. **Hierarchy**: managed > user (`~/.claude/CLAUDE.md`) > project
   (`./CLAUDE.md` or `./.claude/CLAUDE.md`) > local
   (`./CLAUDE.local.md`, gitignored). All concatenated, root-down.
3. **Use `@path` imports** for cross-file reference. Recursive, max
   depth 5. Counts against context budget at load.
4. **Use `.claude/rules/`** with `paths:` frontmatter for topic-scoped
   instructions that only load when matching files are touched.
5. **Skills replaced custom slash commands** (Claude Code v2.x).
   `.claude/skills/foo/SKILL.md` is the modern path; old
   `.claude/commands/foo.md` still works.
6. **Use `disable-model-invocation: true`** on skills with side
   effects (`/deploy`, `/commit`, `/send-slack`).
7. **Use `context: fork`** on read-heavy skills to keep main context
   clean.
8. **Use hooks** when something MUST happen at a lifecycle event.
   CLAUDE.md is context, not enforced configuration.
9. **AGENTS.md compat**: `@AGENTS.md` import or symlink so Claude
   reads the same file other agents do.
10. **`/init`** generates a starting CLAUDE.md. Set
    `CLAUDE_CODE_NEW_INIT=1` for the interactive multi-phase flow.
11. **Block-level HTML comments** in CLAUDE.md are stripped before
    sending to the model: free space for human notes.
12. **No secrets in CLAUDE.md**: they go to the model verbatim.

## Apply

```bash
ai-config-kit decisions apply claude-best-practices
```

Then append the fragment to your live `CLAUDE.md`:

```bash
cat ~/.config/claude-config/content/claude/CLAUDE.md.claude-best-practices.fragment \
  >> ~/.config/claude-config/content/claude/CLAUDE.md
ai-config-kit sync -m "adopt claude-best-practices"
```

## Why this auto-reconciles

`ai-config-kit` ships new versions as Claude Code's docs evolve.
The **reconcile** mechanism in `manager.py` compares the version
stored in your JSON config (`last_applied_version`) against the
currently-installed package version. On mismatch, it re-applies every
pack in `DEFAULT_DECISIONS_ON_INIT` non-clobberingly. When this pack
updates in a later release, the next time you run any
`ai-config-kit` command you'll see:

> reconciled 0.2.0 -> 0.3.0: applied claude-best-practices

…and the new files appear in your content dir. Existing files (your
customised CLAUDE.md, etc.) are NOT touched.

Disable auto-reconcile by setting `auto_reconcile: false` in your
JSON config.
