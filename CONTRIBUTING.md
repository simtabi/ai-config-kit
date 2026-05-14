# Contributing to ai-configurator

Thanks for considering a contribution. This file captures the rules
that keep the codebase consistent.

## Development setup

```bash
git clone https://github.com/simtabi/claude-configs
cd claude-configs
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
ruff check src tests
mypy src/ai_configurator
```

All four must be green on every PR. CI re-runs them on macOS +
Ubuntu × Python 3.10 / 3.11 / 3.12 / 3.13 once the workflows ship.

## Architecture rules

These keep the surface area small and predictable.

1. **One class.** `ClaudeConfig` is the entire public surface (plus
   the small frozen-dataclass result types). New behaviour should
   extend the class, not introduce parallel ones.
2. **Fluent setters return `self`.** Mutators are chainable.
3. **Operations producing data return a frozen `Report` dataclass.**
   No tuples, no untyped dicts. Tests assert on report fields.
4. **No runtime dependencies.** Standard library only. The tool
   installs in any Python 3.10+ env with no transitive surprises.
5. **Three-layer config: CLI flag > env var > JSON > class default.**
   Don't add a fourth layer without strong justification.
6. **Secrets are blocking, not advisory.** Never narrow the secret-
   pattern enforcement. New secret-looking patterns can be added,
   never removed without a major version bump.
7. **Vendor adapters live in one registry.** New AI-agent support
   adds a `VendorAdapter` entry to `VENDOR_ADAPTERS` and bumps
   `VENDOR_STATUS`. Adapters declaring `global_target` under
   `Path.home()` must be redirectable via `with_vendor_adapter`
   so the test suite never writes to a real `~/.cursor/rules/`
   etc.
8. **Canonical rules live in AGENTS.md, not per-vendor copies.**
   `compose-agents-md` synthesizes it from `CLAUDE.md` plus the
   decision-pack fragments. Per-vendor files are produced by copy
   from that single source; never hand-edit `.cursorrules`,
   `.windsurfrules`, etc. in this repo's content dir.

## Coding conventions

- `mypy --strict` clean. New optional fields use `field | None = None`,
  not bare `Optional`. Prefer `Path` over `str` for filesystem paths.
- `ruff check` clean with the configured ruleset
  (`E`, `F`, `W`, `I`, `N`, `UP`, `B`, `SIM`, `RUF`).
- Tests live in `tests/`. Use `tmp_path` for filesystem state; never
  write to `~/.claude/`, `~/.config/`, or any real user path from a
  test.
- Docstrings on the class and every public method. Internal helpers
  prefixed with `_`; their docstrings optional but encouraged.
- No `# type: ignore` without a one-line comment explaining why.

## Commit messages

- Imperative subject ≤ 72 chars.
- Body explains why, not what.
- No emoji, no `Co-Authored-By`.
- AI-tells (`leverage`, `seamless`, `essentially`, `note that`,
  `simply,`) are blocked. Write plainly.

## What goes in this repo

- Tool code, tests, docs.

## What does NOT go in this repo

- Anyone's personal content. The whole point of the design is that
  config lives in the user's content dir (default
  `~/.config/claude-config/content/`), not here. Don't add seed
  CLAUDE.md content beyond the trivial template in `init`.

## Release process

Tag-driven. Bump `pyproject.toml::project.version`, update
`CHANGELOG.md`, commit, tag `vX.Y.Z`, push the tag. CI handles PyPI
trusted-publishing release once the workflow is configured.

## Reporting bugs

Open an issue with:

- What you ran (exact command line)
- What happened (output + exit code)
- What you expected
- `ai-configurator status` + `ai-configurator doctor` output
- Python version, OS

## Reporting security issues

See [`SECURITY.md`](SECURITY.md). Do not file public issues for
disclosures.
