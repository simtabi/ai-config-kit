---
description: Download a canonical / upstream file disk-to-disk. Body bytes never enter the response stream.
argument-hint: <url> <dest>
---

The task is to put a canonical / upstream file on disk (license,
code of conduct, .gitignore template, spec excerpt, etc.). The
file-write / file-create / file-edit tool would stream the body
through your response, where the content filter watches. **Do not
use those tools for this file.**

Use the shell tool with a disk-to-disk downloader:

**Preferred** — `ai-configurator fetch` (Python, ships with ai-configurator):

```bash
ai-configurator fetch $1 $2
```

**Fallback** when ai-configurator isn't installed but `curl` is:

```bash
curl -fsSL --proto '=https' --tlsv1.2 --max-filesize 1048576 \
  -o $2 $1
```

After the download, run these verification commands and show only
their raw output:

```bash
ls -la $2
wc -l $2
shasum -a 256 $2 2>/dev/null || sha256sum $2
head -1 $2
```

**Do not:**

- `cat` the file
- Print, paraphrase, summarize, or otherwise reproduce any line of
  the file beyond line 1 (the title)
- Use file-write/create/edit tools on this file
- Add prose describing what the file contains

**If the download fails:**

Report the exit code and stderr. Do NOT recover by typing the
contents yourself. Propose an alternate source URL and ask before
retrying.

**If you can't run `ai-configurator fetch` and `curl` isn't available
either,** report that and stop. Don't install anything.
