from __future__ import annotations

from pathlib import Path

import pytest

from claude_config import ClaudeConfig


@pytest.fixture
def tmp_layout(tmp_path: Path) -> tuple[Path, Path]:
    """Returns (content_dir, target_base) both inside tmp_path."""
    content = tmp_path / "content"
    target = tmp_path / "claude-target"
    (content / "claude").mkdir(parents=True)
    target.mkdir()
    return content, target


@pytest.fixture
def cfg(tmp_layout: tuple[Path, Path]) -> ClaudeConfig:
    content, target = tmp_layout
    return ClaudeConfig(content_dir=content, target_base=target)
