<!--
Thanks for the PR. Please confirm the items below before requesting review.
-->

## What and why

<!-- One paragraph on the change and the motivation. -->

## Changes

- [ ] Behaviour change is documented in `CHANGELOG.md`
- [ ] Default-changing edits bump MINOR (not PATCH) version
- [ ] New public API surfaces are exported from `ai_config_kit.__init__`

## Quality gates

- [ ] `pytest -q` green
- [ ] `ruff check src tests` clean
- [ ] `mypy src/ai_config_kit` clean
- [ ] `python -m build` produces sdist + wheel without warnings

## Notes for reviewers

<!-- Anything subtle, anything you're unsure about, anything that needs a second pair of eyes. -->
