# humanistic-style

Two concerns shipped as one pack because they share a principle: write
prose and code that reads like a thoughtful human wrote it, not like
generative output.

## What ships

| File | Purpose |
|---|---|
| `CLAUDE.md.humanistic-style.fragment` | Rules for prose voice + code-comment conventions. Banned-phrase list. PHPDoc / JSDoc / Sphinx-style docstring conventions. SOLID, DRY, KISS, and fluent-chain OOP reminders. |
| `commands/audit-prose.md` | `/audit-prose <path>` slash command. Greps for banned phrases + flags em-dash overuse. |
| `commands/audit-docblocks.md` | `/audit-docblocks <path>` slash command. Checks public-API surface has the right doc-block format per language. |
| `humanistic-style/banned-phrases.txt` | The authoritative banned-phrase list. Maintained alongside the fragment so tools can grep it directly. |

## Why

Generative output has tells: em-dash sandwiches, "By following these
steps", "robust and scalable", "let's dive into", "It is worth noting".
A reader can spot them in two sentences and the work loses authority.

Banned-phrase list, by category:

- **Filler openers**: "let's dive into", "in this article", "as we
  explore", "you'll notice that"
- **Filler closers**: "in conclusion", "to summarize", "by following
  these steps", "as we can see"
- **AI marketing**: "robust", "powerful", "comprehensive", "seamless",
  "cutting-edge", "state-of-the-art", "best-in-class", "leverage"
- **Hedging filler**: "essentially", "fundamentally", "in essence",
  "at its core"
- **Tour-guide voice**: "Now let's", "Let's go ahead and", "Note that",
  "Importantly", "**Important:**"
- **Em-dash sandwich**: " — and — ", " — but — ", em-dashes inside
  parentheticals where commas would do
- **Smarmy connectors**: "delve", "delve into", "in the realm of",
  "the world of"

## Apply

```bash
ai-configurator decisions apply humanistic-style
```

Then append the fragment to your live `CLAUDE.md`:

```bash
cat ~/.config/claude-config/content/claude/CLAUDE.md.humanistic-style.fragment \
  >> ~/.config/claude-config/content/claude/CLAUDE.md
ai-configurator sync -m "adopt humanistic-style"
```

Auto-applied by `ai-configurator init`. The `banned-phrases.txt` ships
to the content dir at `humanistic-style/banned-phrases.txt` so other
tools (linters, hooks, CI checks) can read it directly.
