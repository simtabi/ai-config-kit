# core

Skeleton content for a fresh `ai-configurator` install.

## Contents

- `CLAUDE.md`: short opinionated template covering identity, code quality
  gates, scope discipline, anti-hallucination, history is additive.
- `settings.json`: minimal valid settings file with `permissions`,
  `hooks`, and the JSON schema reference.

## Apply

```bash
ai-configurator decisions apply core
```

The command refuses to overwrite existing files in the content dir.
Pass `--force` to overwrite (you'll lose any customisation you've made).
