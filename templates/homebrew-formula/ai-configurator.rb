# Homebrew formula for `ai-configurator`.
#
# Live formula in the `simtabi/homebrew-tap` repository at
# `Formula/ai-configurator.rb`. The release workflow keeps `url` and
# `sha256` in sync with each PyPI release.
#
# Tap usage:
#   brew tap simtabi/tap
#   brew install ai-configurator
#
# Or one-shot:
#   brew install simtabi/tap/ai-configurator
#
# To regenerate locally after a PyPI release (X.Y.Z):
#   brew create --python --tap simtabi/tap \
#     https://files.pythonhosted.org/packages/source/a/ai-configurator/ai_configurator-X.Y.Z.tar.gz
#   brew update-python-resources Formula/ai-configurator.rb
#   brew style --fix Formula/ai-configurator.rb
#   brew audit --new --strict Formula/ai-configurator.rb
#
# ai-configurator has zero runtime dependencies (stdlib only), so no
# `resource` blocks are required.

class AiConfigurator < Formula
  include Language::Python::Virtualenv

  desc "Symlink-manage ~/.claude and ship cross-vendor AI agent rules"
  homepage "https://opensource.simtabi.com/products/ai-configurator"
  url "https://files.pythonhosted.org/packages/source/a/ai-configurator/ai_configurator-0.2.0.tar.gz"
  sha256 "REPLACE_WITH_PYPI_SDIST_SHA256_ON_RELEASE"
  license "MIT"
  head "https://github.com/simtabi/claude-configs.git", branch: "main"

  depends_on "python@3.13"

  def install
    virtualenv_install_with_resources
  end

  test do
    # The CLI must report its version.
    assert_match version.to_s, shell_output("#{bin}/ai-configurator --version")

    # `decisions list` is a side-effect-free verb that touches the
    # bundled-resources surface; a broken wheel that lost its packed
    # decision packs would surface here.
    output = shell_output("#{bin}/ai-configurator decisions list")
    assert_match "bundled pack(s)", output

    # `--help` lists the new multi-vendor verbs so a stale wheel
    # without the slice-1..4 work would fail this assertion.
    help_text = shell_output("#{bin}/ai-configurator --help")
    assert_match "compose-agents-md", help_text
    assert_match "project-install", help_text
  end
end
