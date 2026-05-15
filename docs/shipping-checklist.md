# Shipping checklist

One-time, per-channel setup before the first `vX.Y.Z` tag can publish.

## PyPI (trusted publishing)

- [ ] Repository on GitHub is public (or PyPI trusted-publishing is configured for the private repo).
- [ ] Create a `pypi` GitHub Environment in the repo settings.
- [ ] Configure a trusted publisher on PyPI:
  - Project name: `ai-configurator`
  - Owner: `simtabi`
  - Repository: `ai-configurator`
  - Workflow: `release.yml`
  - Environment: `pypi`
- [ ] The `release.yml` workflow runs `pypa/gh-action-pypi-publish` with `permissions.id-token: write`.

## OIDC verification

- [ ] First tag triggers the workflow.
- [ ] Workflow succeeds, package appears at `https://pypi.org/project/aicfg/`.
- [ ] `pip install aicfg` from a clean venv resolves the new version.

## Repo metadata

- [ ] `pyproject.toml::project.urls.Homepage` = `https://opensource.simtabi.com/products/ai-configurator`
- [ ] `pyproject.toml::project.urls.Documentation` = `https://opensource.simtabi.com/documentation/ai-configurator`
- [ ] `pyproject.toml::project.urls.Repository` = `https://github.com/simtabi/ai-configurator`
- [ ] GitHub repo description set (≤ 120 chars, ends with a period).
- [ ] GitHub topics include at minimum: `oss`, `python`, `claude-code`, `dotfiles`.

## Ongoing prep before every release

- [ ] `pytest -q` green.
- [ ] `ruff check src tests` clean.
- [ ] `mypy src/ai_configurator` clean.
- [ ] `python -m build` produces sdist + wheel without warnings.
- [ ] CHANGELOG entry written, explaining the *why* per change.
- [ ] No `dependencies = [...]` regressions (stdlib only is the rule).
