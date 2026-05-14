# Release process

Tag-driven, with OIDC trusted publishing to PyPI. Single source of
version truth in `pyproject.toml`; `__init__.py` reads it via
`importlib.metadata`.

## Per-release steps

1. Update `CHANGELOG.md` — move WIP entries into a new `[X.Y.Z] — YYYY-MM-DD` section.
2. Bump `pyproject.toml::project.version` to `X.Y.Z`.
3. Commit: `release: vX.Y.Z`.
4. Tag: `git tag -a vX.Y.Z -m "X.Y.Z"`.
5. Push: `git push && git push --tags`.
6. The `release.yml` workflow publishes to PyPI via OIDC.

## Versioning

Semver per `https://semver.org`:

- **MAJOR** — incompatible API changes.
- **MINOR** — backwards-compatible feature additions. Default-changing
  behaviour (e.g., expanding `dir_symlink_names` defaults) lives here.
- **PATCH** — backwards-compatible bug fixes only.

Bumping defaults that could change what gets symlinked counts as a
MINOR. Removing a secret pattern from the default list is a MAJOR.

## First-time setup on a new release channel

See [shipping-checklist.md](shipping-checklist.md).
