# Installation

## Requirements

- **Python 3.10 or later**: the CLI runs under Python and uses
  stdlib only. The `fetch` and decision-pack features are pure
  Python so they work identically on macOS, Linux, and Windows.
- `git` on `PATH` (only needed for `init` and `sync`).
- **Windows note**: symlinks require either Administrator privileges
  or **Developer Mode enabled** (Settings → Privacy & security →
  For developers). Without it, `install` will fail with
  `OSError: [WinError 1314]`. The `fetch`, `cleanup`, `list`,
  `view`, `decisions`, `validate`, `compose-agents-md`, and
  `project-install` subcommands all work without symlink permission
  (the last two write regular files into a project directory).

## Install the CLI

Pick the option that matches how you usually install Python tools.

```bash
# Standard pip
pip install aicfg

# Isolated (recommended for tools)
pipx install aicfg

# uv
uv tool install aicfg
```

## First-time setup

The one-shot wrapper runs validation, content-dir init, symlink install,
and a health check:

```bash
ai-configurator bootstrap
```

Re-running `bootstrap` on a machine that's already set up is safe: each
step short-circuits if the work is already done.

### On a second machine

Push your content dir to a private git repo from machine A, then on
machine B:

```bash
pip install aicfg
git clone git@github.com:you/my-claude-content.git ~/.config/claude-config/content
ai-configurator bootstrap
```

### CI / ephemeral environments

For tests that need Claude Code with a specific config, set env vars to
point at a checked-out content dir:

```bash
git clone https://github.com/you/claude-content /tmp/cc
CLAUDE_CONFIG_CONTENT_DIR=/tmp/cc \
CLAUDE_CONFIG_TARGET=/tmp/runtime-claude \
  ai-configurator bootstrap --no-git --yes
```

`--yes` skips all confirmation prompts; `--no-git` skips `git init` (no
need for git in an ephemeral checkout).

## Uninstall

```bash
ai-configurator uninstall      # remove symlinks; restore pre-install backups
pip uninstall ai-configurator  # remove the CLI
```

Your content dir is **never touched** by `uninstall`: back it up first
if you also want to delete it.
