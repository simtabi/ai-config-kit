# fetch-canonical-pattern

When the model is asked to add a canonical / upstream file (license,
code of conduct, security policy, third-party notice, .gitignore
template, RFC excerpt, etc.), its file-write tool **streams the
content through the response**. That stream is where the content
filter watches. For long well-known texts, that filter trips and
the write fails mid-flight, leaving a half-written file.

## The fix

Route the file's bytes around the response stream entirely:

- **URL → disk** via `ai-config-kit fetch` (Python, stdlib, cross-platform)
- Or **URL → disk** via `curl -o <path> <url>` (where curl is available)
- The model's reply contains only the **command** and **metadata
  output** (`bytes=`, `sha256=`, etc.): no file body.

## What this pack ships

- `commands/fetch-canonical.md`: the `/fetch-canonical` slash command
  the model can use, with explicit "do NOT use file-write/edit/create
  tool" guardrails.
- `CLAUDE.md.fetch-canonical-pattern.fragment`: global rule to paste
  into your `CLAUDE.md` so the pattern fires whenever a canonical
  file is requested, even without invoking the slash command.

## Apply

```bash
ai-config-kit decisions apply fetch-canonical-pattern
```

Then optionally append the fragment to your live `CLAUDE.md`:

```bash
cat ~/.config/claude-config/content/claude/CLAUDE.md.fetch-canonical-pattern.fragment \
  >> ~/.config/claude-config/content/claude/CLAUDE.md
ai-config-kit sync -m "adopt fetch-canonical-pattern"
```

## Why two flavours of fetcher

| Tool | When |
|---|---|
| `ai-config-kit fetch <url> <dest>` | Default. Pure Python, works on Windows, macOS, Linux. No external dependencies beyond `ai-config-kit` itself. |
| `curl -fsSL -o <dest> <url>` | When `curl` is already on PATH and `ai-config-kit` isn't (CI image without it, plain shell session, etc.). Same disk-to-disk behaviour. |

Both keep file bytes out of the response stream. Pick whichever is
already installed.
