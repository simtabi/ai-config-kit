# `ai-configurator`: design specification + agent prompt

> This file is **both** the design spec AND the standing prompt that
> coding agents load when they continue this project. Mirrors the
> structure of the sibling `get-installer/SPEC.md`. Both files are
> intentionally similar so agents trained on one are productive in the
> other.

---

## 🔁 Session protocol (read before everything else)

Identical to `get-installer/SPEC.md` § "Session protocol": kept in
sync so agents work the same way in both projects. Summary:

**Session start**:
1. Read this SPEC end-to-end.
2. Run the audit checklist below (5-line summary at the top of your reply).
3. Read `STATUS.md` if present + `~/.claude/projects/<slug>/memory/MEMORY.md`
   + the latest `CHANGELOG.md` entry.
4. Restate the user's goal in one sentence before any tool call.

**During the work**:

5. **Hallucination guard**: every claim about the codebase comes
   from a live `Read` / `Grep` / shell call. Memory tells you what was
   true when written, not what's true now. Cite `path:line` where
   possible. Phrases that signal you're guessing: "typically",
   "usually", "I believe", "around line ~", round numbers, paraphrases
   of code you haven't opened.

6. **Track progress**: `TaskCreate` / `TaskUpdate` for anything
   beyond 3 steps. Mark `in_progress` before you start; `completed`
   the moment it's done, not in a batch.

7. **Watch for regressions**: re-run the audit checklist after every
   non-trivial edit; don't accumulate a "tests-at-the-end" debt.

8. **Log failures**: when a step fails, surface it in your reply
   immediately: what failed, what you tried, what you'll try next.

9. **Research before guessing**: `WebFetch` the official docs site
   first, project README + spec second, reputable blogs third. Skip:
   Medium content farms, AI-generated blog spam, paywalled pages.

10. **Clarifying questions**: when the request is ambiguous and the
    wrong path costs > 5 minutes to undo, ask once with a numbered
    options list. Not Socratic chains.

**Session end**:

11. **Self-improvement loop**: suggest SPEC updates (new findings →
    §5; finished phases → `[x]`), prompt updates (this section), test
    gaps you noticed.

12. **Hand-off summary**: last paragraph: what changed (paths), what's
    still open (issue ids), what the next agent picks up first.

---

## 🔍 Audit checklist: run this FIRST every session

Before writing code, run a status sweep and report the findings inline.

1. **`pytest -q`**: must be green.
2. **`ruff check src tests`**: must be clean.
3. **`mypy --strict src/ai_configurator`**: must be clean.
4. **CLI surface check**: `python -m ai_configurator --help`
   should list every subcommand in `docs/tools/ai-configurator.md`.
5. **README authority check**: exactly ONE `README.md` at the repo
   root, ONE under `docs/` is allowed if it's an index, per-pack
   `details.md` (not `README.md`) under `resources/decisions/<pack>/`.
6. **Security baselines**: quickly grep:
   - `subprocess.run(.*shell=True` (zero expected)
   - `os.system\|eval\(` (zero expected)
   - `mode=0o7..` / `chmod` calls: verify each is intentional and
     ≤ `0o644` for content files, `0o600` for sensitive ones
7. **Roadmap drift**: for `[x]` items in §4 below, spot-check the
   referenced feature actually exists. For `[ ]` items, spot-check it
   genuinely is not done.
8. **Vendor adapter integrity**: `VENDOR_ADAPTERS` keys must be a
   subset of `SUPPORTED_VENDORS`. Each adapter with `global_target`
   under `Path.home()` must be redirectable via `with_vendor_adapter`
   so tests never write to a real `~/.cursor/rules/` etc.
9. **Decision pack surface**: every entry in
   `DEFAULT_DECISIONS_ON_INIT` must have a corresponding directory
   under `resources/decisions/` with a `manifest.json` and at least
   one file. `decisions list` must show the same count.
10. **AI-tell prose check**: `grep -rniE 'leverage|seamless|essentially|note that|simply,|comprehensive|robust\b|delve into' docs/ README.md CHANGELOG.md src/ai_configurator/resources/decisions/` returns only banned-list mentions, not actual prose. Em-dash sandwich (` — `) also zero in prose (table-cell em-dashes and the audit-prose grep pattern are intentional exceptions).

Five-line summary at the top of your first response, then proceed
with the user's request.

---

## 0: Project identity (locked)

| Field | Value |
|---|---|
| Project | `ai-configurator` |
| Python module | `ai_configurator` |
| CLI command | `ai-configurator` |
| Distribution channel | `get.simtabi.com` (via sibling `get-installer`) |
| Repo | `https://github.com/simtabi/ai-configurator` |
| License | MIT, `Copyright (c) 2026 Simtabi LLC` |
| Min Python | 3.10 |
| Runtime deps | **none** (stdlib only) |
| Current version | 0.2.0 |

## 1: Mission

Version your `~/.claude/` directory without versioning your caches.
Symlinks a content directory you control into `~/.claude/` at the
paths Claude Code expects, ships opinionated **decision packs** that
bake content-filter-safe practices into every install, and gives you
one verb (`bootstrap`) to set up everything on a fresh machine.

Two-layer design:

1. **The Python tool**: manages symlinks, ships decision packs,
   provides `fetch` / `repair` / `decisions` / etc.
2. **The user's content directory**: at `~/.config/claude-config/`
   (kept under that path for backwards compat after the rename from
   `claude-config` → `ai-configurator`). Contains the user's
   actual `CLAUDE.md`, `settings.json`, `commands/`, `agents/`, etc.

## 2: Current state (v0.3.0-dev)

Renamed from `claude-configurator` to `ai-configurator` to reflect the
broader scope: target any AI coding tool, not just Claude Code.

What's **done**:

1. Core class `ClaudeConfig` with 18 verbs:
   `bootstrap`, `init`, `install`, `uninstall`, `sync`, `track`,
   `status`, `doctor`, `validate`, `list`, `view`, `cleanup`,
   `repair`, `fetch`, `reconcile`,
   `compose-agents-md`, `project-install`,
   `decisions {list,show,apply}`.
2. **13 bundled decision packs** at
   `src/ai_configurator/resources/decisions/<name>/`. **12
   auto-applied on `init`**, 1 opt-in (`core`):
   - `script-generation-pattern`: generator-script-first for many-file work
   - `fetch-canonical-pattern`: disk-to-disk canonical-file downloads
   - `session-protocol`: disciplined session bookends + anti-hallucination
   - `docker-multiarch`: `linux/amd64 + linux/arm64` from one Dockerfile
   - `docker-env-interpolation`: render-env.sh flattens layered .env files
   - `claude-best-practices`: distilled from `code.claude.com/docs`
   - `humanistic-style`: strip AI tells; PHPDoc / JSDoc / Sphinx
   - `docs-structure`: one README at root, everything else under `docs/`
   - `mcp-best-practices`: safe MCP server configuration
   - `safety-net-commits`: prompt for git checkpoints at safe moments
   - `vendor-portability`: write-once, target Claude / Cursor / Cline / Codex / Aider / Windsurf / Copilot
   - `polling-discipline`: "don't chain sleeps"; surfaces Monitor + Bash run_in_background + ScheduleWakeup
   - `core` (opt-in): skeleton CLAUDE.md + settings.json
3. **Multi-vendor support**: `vendors: tuple[str, ...]` on
   `ClaudeConfig`. Default is `("claude-code",)`. The bootstrap flow
   prompts the user per-vendor; selected vendors persist to the JSON
   config. Seven CLI-based vendors are now `current` (claude-code,
   aider, codex, cursor, cline, windsurf, copilot); `claude`
   (web/desktop) stays `partial`. `VendorAdapter` registry maps each
   to its global target (`~/.cursor/rules/`, `~/.codex/instructions/`,
   etc.) and per-project files (`AGENTS.md`, `.cursorrules`,
   `.windsurfrules`, `.clinerules`, `.github/copilot-instructions.md`).
4. **Auto-reconcile on upgrade**: `ClaudeConfig.reconcile()` compares
   the installed package version against `last_applied_version` in the
   JSON config and re-applies missing auto-apply packs. The CLI runs
   this on every command; users who `pip install --upgrade
   ai-configurator` pick up new packs automatically.
5. `fetch` command: disk-to-disk URL → file with SHA256 + atomic
   write. Stdlib only.
6. **157 tests passing**, ruff + mypy --strict clean.
7. Cross-platform: macOS, Linux, Windows.
8. CI workflows + Dependabot.
9. Doc tree under `docs/` (installation, configuration,
   architecture, release, shipping-checklist, decisions, SPEC,
   tools/ai-configurator.md).

Known issues / gaps live in §5.

## 3: URL contracts

The bootstrap entry point is the sibling `get-installer`:

```bash
sh -c "$(curl -fsSL https://get.simtabi.com/install.sh)" -- --product ai-configurator
```

Once installed:

```bash
ai-configurator bootstrap         # validate + init + install + doctor
ai-configurator status            # what's tracked
ai-configurator list              # grouped content view
ai-configurator sync -m "..."     # commit changes in the content dir
```

The user's content dir defaults to `~/.config/claude-config/content/`
(yes, the dir is still named `claude-config`: predates the rename;
keeping it for back-compat).

## 4: Required features (by phase)

### Phase A: Schema-driven settings validation

- [ ] `settings.json` (the Claude Code config) has a JSON Schema upstream.
      Fetch it once at install time, cache locally, validate the user's
      settings on `doctor`. Surface field-level errors with `path:line`.
- [ ] Same for `CLAUDE.md` frontmatter (if any).

### Phase B: Pluggable decision packs (from the wild)

- [ ] `decisions install <url>`: install a community / private pack
      from a git URL (only after sha256 verification per pack manifest).
- [ ] `decisions search <term>`: search a registry of public packs
      (TBD: a registry at `decisions.simtabi.com` or similar).

### Phase C: Memory dir hygiene

- [ ] `ai-configurator memory clean --older-than 90d`: remove
      stale per-project memory entries.
- [ ] `ai-configurator memory dedupe`: find near-duplicate
      memories across projects (basic shingle-hash).

### Phase D: Settings.json migration helpers

- [ ] `ai-configurator settings migrate`: detects schema-version
      changes in Claude Code's `settings.json` and migrates the user's
      file (with a backup).
- [ ] Tracks Claude Code releases via the get-installer's audit beacons.

### Phase E: Cross-machine sync (beyond git)

- [ ] `ai-configurator sync --target s3://bucket/path`: push the
      content dir to object storage in addition to git.
- [ ] `ai-configurator sync --target webdav://...`: for
      Nextcloud / iCloud-like users.

### Phase F: Selective install (subset of content)

- [ ] `ai-configurator install --only commands,agents`: install
      only specific subtrees. Useful for limited test envs.
- [ ] `ai-configurator install --exclude sessions` (already
      handled by `include_sessions=false`, but documented as the
      mainline path).

### Phase G: Audit log

- [ ] Every `track` / `install` / `uninstall` / `decisions apply`
      writes a row to `~/.claude/projects/.audit.jsonl` so a user can
      audit their own changes later. (Distinct from the get-installer
      audit beacons.)

### Phase H: Multi-vendor ✔ 2026-05-14

`ai-configurator` now targets seven CLI-based AI coding agents:
`claude-code`, `aider`, `codex`, `cursor`, `cline`, `windsurf`,
`copilot`. Each is declared in a `VendorAdapter` registry with its
own global target (`~/.cursor/rules/`, `~/.codex/instructions/`, etc.)
and per-project files (`AGENTS.md`, `.cursorrules`, `.windsurfrules`,
`.clinerules`, `.github/copilot-instructions.md`).

- [x] `VendorAdapter` + `ProjectFile` data model (`manager.py`).
- [x] `compose-agents-md` verb: builds the canonical `AGENTS.md` from
      the user's `CLAUDE.md` + every `CLAUDE.md.*.fragment` shipped
      by decision packs. Output carries an autogen marker; refuses
      to clobber hand-edited files.
- [x] `project-install <path>` verb: writes per-vendor files into a
      project repo. Falls back to the configured vendors list when
      `--vendor` omitted. Auto-composes `AGENTS.md` if missing.
- [x] `install` extension: drops the canonical into each non-
      `claude-code` vendor's `global_target` (currently cursor +
      codex).
- [x] `with_vendor_adapter` test override so the suite doesn't write
      to the real `~/.cursor/rules/`.
- [x] `vendor-portability` decision pack: `Pattern 0` points users
      at the new verbs; manual patterns retained for users without
      the configurator installed.
- [x] End-to-end smoke test: init → compose → project-install
      asserts the user's `CLAUDE.md` content reaches every vendor's
      expected destination unchanged.

Status matrix at v0.3.0:
- `current`: claude-code, aider, codex, cursor, cline, windsurf, copilot
- `partial`: claude (Claude.ai web/desktop, manual CLAUDE.md sharing)

### Phase I: Homebrew tap distribution ✔ 2026-05-14

- [x] `templates/homebrew-formula/ai-configurator.rb`: ready-to-ship
      live formula for `simtabi/homebrew-tap/Formula/`. Stdlib-only,
      depends_on python@3.13, `test do` exercises `--version`,
      `decisions list`, and `--help` (which must include the
      multi-vendor verbs).
- [x] `docs/distribution/homebrew.md`: one-time tap setup
      (`brew tap-new`, `brew create --python`,
      `brew update-python-resources`) plus the release-time bump
      workflow.

## 5: Open issues / known bugs

| # | Where | Issue |
|---|---|---|
| C1 | `src/ai_configurator/manager.py` | The 1500+ line file is dense. Consider extracting `decisions_*` methods to a sibling `decisions.py` module while keeping `ClaudeConfig` as the orchestrator. |
| C2 | All commands | We don't have a `--json` output mode anywhere. Adding one would let other tools script around `ai-configurator status` etc. |
| C3 | `cli.py` | The bootstrap command's `--remote URL` flag accepts arbitrary URLs. Validate it's https:// or git@ before passing to git. |
| C4 | `decisions apply` | When `--force` is given, doesn't show a diff first. Add a confirm-with-diff for tty users. |
| C5 | Cross-project | Audit-checklist + agent-loop instructions are duplicated between this SPEC and `get-installer/SPEC.md`. If a third project adopts the pattern, factor into a shared template. |
| C6 | `tests/` | We test the manager's surface but not the integration with the symlinks-on-real-FS edge cases (e.g., bind-mounted target). Add a few integration tests. |

## 6: Out of scope

- **Not a fork of Claude Code's own config tooling.** When Claude Code
  ships its own dotfile-management story, we deprecate.
- **Not a multi-user / shared-tenant tool.** One user, one
  `~/.config/claude-config/`. Multi-user is org-level via git remotes.
- **Not a settings.json editor.** We symlink it; the user edits in
  their preferred way.

## 7: Coding conventions

Same as `get-installer/SPEC.md` §7 and the Simtabi-org defaults at
`/Users/imanimanyara/Artisan/projects/opensource/CLAUDE.md`. Highlights:

- Stdlib only. No runtime deps.
- `mypy --strict` clean. `ruff` clean with the project's lints.
- Tests under `tests/`. `tmp_path` for filesystem state.
- No emoji in code, commits, or docs.
- No AI-tells (`leverage`, `powerful`, `robust`, `comprehensive`,
  `seamless`, `essentially`, `note that`, `simply,`).
- Commit messages: imperative ≤ 72 chars, body explains *why*.

## 8: Agent-loop instructions

Same as `get-installer/SPEC.md` §8:

1. Run the audit checklist at the top of this file FIRST.
2. State which Phase / issue you're working on before any tool call.
3. Verify before claiming: every file count / version / claim must
   come from a live shell or read.
4. Update this file when finishing a phase. Move `[ ]` → `[x]` with a
   `✔ <date>` note. Add discoveries to §5.
5. Stay scope-tight. Out-of-§4-and-§5 work requires user confirmation.
6. No destructive ops (`git push --force`, `reset --hard`, deletions)
   without an explicit verb from the user.
7. Stay a step ahead: tiny one-line cleanups in files you're already
   editing are welcome. Don't expand scope beyond the diff you'd
   already make.

## 9: System diagram (text form)

```
              ┌──────────────────────────────┐
              │  ~/.config/claude-config/    │  (user's content dir; git-versioned)
              │   ├── .git/                  │
              │   └── claude/                │
              │       ├── CLAUDE.md          │
              │       ├── settings.json      │
              │       ├── commands/          │
              │       ├── agents/            │
              │       ├── ...                │
              │       └── projects/<slug>/   │
              │           └── memory/        │
              └────────┬─────────────────────┘
                       │ symlinks
                       ▼
              ┌──────────────────────────────┐
              │  ~/.claude/                  │  (what Claude Code reads)
              │   ├── CLAUDE.md           ───┼──▶ symlink into content
              │   ├── settings.json       ───┼──▶ symlink into content
              │   ├── commands/           ───┼──▶ dir symlink
              │   ├── agents/             ───┼──▶ dir symlink
              │   ├── ...                    │
              │   ├── sessions/  (runtime, untracked)
              │   ├── history.jsonl (runtime, untracked)
              │   └── paste-cache/ (runtime, untracked)
              └──────────────────────────────┘
                       ▲
                       │ managed by
                       │
              ┌──────────────────────────────┐
              │  ai-configurator CLI     │  (this Python package)
              │   bootstrap / install / ...  │
              └──────────────────────────────┘
```

## 10: Directory layout

```
ai-configurator/
├── README.md              # the single authoritative README
├── SPEC.md                # this file
├── LICENSE
├── CHANGELOG.md
├── pyproject.toml
├── Makefile
├── CONTRIBUTING.md
├── SECURITY.md
├── CODE_OF_CONDUCT.md
├── .gitignore
├── .editorconfig
├── .github/
│   ├── workflows/
│   │   ├── ci.yml
│   │   └── release.yml
│   ├── dependabot.yml
│   └── ISSUE_TEMPLATE/
├── docs/
│   ├── installation.md
│   ├── configuration.md
│   ├── architecture.md
│   ├── decisions.md
│   ├── release.md
│   ├── shipping-checklist.md
│   └── tools/ai-configurator.md
├── src/
│   └── ai_configurator/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── manager.py
│       ├── py.typed
│       └── resources/decisions/
│           ├── core/{manifest.json, details.md, files/...}
│           ├── script-generation-pattern/...
│           └── fetch-canonical-pattern/...
└── tests/
    ├── conftest.py
    ├── test_manager.py
    └── test_cli.py
```

The repo (folder name `ai-configurator`, plural) and the package name
(`ai-configurator`, singular) intentionally differ: the folder
predates the rename and renaming the GitHub repo would break inbound
links. This dual identity is documented in `docs/architecture.md`.

---

*Last updated 2026-05-15: project renamed to ai-configurator, 13
bundled packs (12 auto-applied), multi-vendor end-to-end (seven CLI
vendors wired via `VendorAdapter`), `compose-agents-md` +
`project-install` verbs, auto-reconcile-on-upgrade, Homebrew tap
formula shipped. 206 tests passing.*
