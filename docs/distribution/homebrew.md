# Homebrew tap distribution

`ai-config-kit` ships through the `simtabi/homebrew-tap` repository
as a complementary channel to `pip install`. Users on macOS / Linuxbrew
who prefer Homebrew can run:

```bash
brew install simtabi/tap/ai-config-kit
```

This page covers the one-time tap setup and the per-release bump.

## When to use the tap

| Situation | Best channel |
|---|---|
| Fresh-machine bootstrap, any OS | `pip install ai-config-kit` |
| User already has Homebrew + pinned Python | `brew install simtabi/tap/ai-config-kit` |
| `pipx` / `uv tool` user | the matching tool's install verb |
| CI image build | `pip install` directly in the image |

The tap is for users who prefer Homebrew as their package manager. It
isn't a replacement for `pip install`.

## Live formula

The ready-to-ship formula lives at
[`templates/homebrew-formula/ai-config-kit.rb`](../../templates/homebrew-formula/ai-config-kit.rb).
On every PyPI release, the same file (with updated `url` + `sha256`)
lands in `simtabi/homebrew-tap/Formula/ai-config-kit.rb`.

The formula has zero runtime dependencies declared because
`ai-config-kit` is stdlib-only. The `test do` block exercises:

1. `--version` returns the expected version string.
2. `decisions list` reports the bundled-packs surface (proves the
   wheel kept its resources directory).
3. `--help` includes the multi-vendor verbs (`compose-agents-md`,
   `project-install`).

## Initial setup (one-time)

1. Create `simtabi/homebrew-tap` on GitHub (empty, public, with a
   `Formula/` directory).

2. Tap it locally:

   ```bash
   brew tap-new simtabi/tap
   cd "$(brew --repository simtabi/tap)"
   ```

3. Copy the live formula into `Formula/`:

   ```bash
   cp /path/to/ai-config-kit/templates/homebrew-formula/ai-config-kit.rb \
      Formula/ai-config-kit.rb
   ```

4. Replace the placeholder `sha256` line with the real PyPI sdist
   hash:

   ```bash
   VERSION=0.2.0
   PKG=ai_config_kit
   PYPI_URL="https://files.pythonhosted.org/packages/source/${PKG:0:1}/${PKG//-/_}/${PKG//-/_}-${VERSION}.tar.gz"
   SHA=$(curl -fsSL "$PYPI_URL" | shasum -a 256 | awk '{print $1}')
   sed -i.bak "s/REPLACE_WITH_PYPI_SDIST_SHA256_ON_RELEASE/${SHA}/" Formula/ai-config-kit.rb
   rm Formula/ai-config-kit.rb.bak
   ```

5. Lint:

   ```bash
   brew style --fix Formula/ai-config-kit.rb
   brew audit --new --strict Formula/ai-config-kit.rb
   ```

6. Commit + push to `simtabi/homebrew-tap`.

## Ongoing releases (automated)

Once the tap exists, add this to the release workflow in
`.github/workflows/release.yml`:

```yaml
- name: Bump Homebrew tap
  if: startsWith(github.ref, 'refs/tags/v')
  uses: dawidd6/action-homebrew-bump-formula@v3
  with:
    token: ${{ secrets.TAP_GITHUB_TOKEN }}
    tap: simtabi/homebrew-tap
    formula: ai-config-kit
    tag: ${{ github.ref_name }}
    revision: ${{ github.sha }}
```

`TAP_GITHUB_TOKEN` is a fine-grained PAT with `contents: write` scope
on `simtabi/homebrew-tap`. The action opens a PR; merge it after CI
on the tap passes.

## Limitations

- **Python pin**: depends on `python@3.13` (newest stable). Update on
  a major Homebrew Python bump.
- **No `bottle` blocks**: `ai-config-kit` is pure Python, so source
  build is fine on every platform.
- **Linuxbrew compatibility**: untested. Pure-Python formulas usually
  work; smoke-test on a Linux runner before announcing.

## See also

- [`templates/homebrew-formula/ai-config-kit.rb`](../../templates/homebrew-formula/ai-config-kit.rb)
- [Homebrew tap docs](https://docs.brew.sh/Taps)
- [`brew create --python` reference](https://docs.brew.sh/Python-for-Formula-Authors)
