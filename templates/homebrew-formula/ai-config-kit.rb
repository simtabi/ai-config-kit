# Homebrew formula for `ai-config-kit`.
#
# Live formula in the `simtabi/homebrew-tap` repository at
# `Formula/ai-config-kit.rb`. The release workflow keeps `url` and
# `sha256` in sync with each PyPI release.
#
# Tap usage:
#   brew tap simtabi/tap
#   brew install ai-config-kit
#
# Or one-shot:
#   brew install simtabi/tap/ai-config-kit
#
# To regenerate locally after a PyPI release (X.Y.Z):
#   brew create --python --tap simtabi/tap \
#     https://files.pythonhosted.org/packages/source/a/ai-config-kit/ai_config_kit-X.Y.Z.tar.gz
#   brew update-python-resources Formula/ai-config-kit.rb
#   brew style --fix Formula/ai-config-kit.rb
#   brew audit --new --strict Formula/ai-config-kit.rb
#
# ai-config-kit has zero runtime dependencies (stdlib only), so no
# `resource` blocks are required.

class AiConfigurator < Formula
  include Language::Python::Virtualenv

  desc "Symlink-manage ~/.claude and ship cross-vendor AI agent rules"
  homepage "https://opensource.simtabi.com/products/ai-config-kit"
  url "https://files.pythonhosted.org/packages/source/a/ai-config-kit/ai_config_kit-0.4.2.tar.gz"
  sha256 "REPLACE_WITH_PYPI_SDIST_SHA256_ON_RELEASE"
  license "MIT"
  head "https://github.com/simtabi/ai-config-kit.git", branch: "main"

  depends_on "python@3.13"

  def install
    virtualenv_install_with_resources
  end

  test do
    # The CLI must report its version.
    assert_match version.to_s, shell_output("#{bin}/ai-config-kit --version")

    # `decisions list` is a side-effect-free verb that touches the
    # bundled-resources surface; a broken wheel that lost its packed
    # decision packs would surface here.
    output = shell_output("#{bin}/ai-config-kit decisions list")
    assert_match "bundled pack(s)", output

    # `--help` lists the new multi-vendor verbs so a stale wheel
    # without the slice-1..4 work would fail this assertion.
    help_text = shell_output("#{bin}/ai-config-kit --help")
    assert_match "compose-agents-md", help_text
    assert_match "project-install", help_text
  end
end
