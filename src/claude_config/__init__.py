"""claude-config — manage Claude Code's ~/.claude/ via symlinks from a content dir.

Public API:
    ClaudeConfig    The single management class (fluent, OOP, configurable).
    InstallReport   Returned by .install() with counts of links created.
    DoctorReport    Returned by .doctor() with health summary.
    StatusReport    Returned by .status() with tracked + untracked breakdown.
    SyncReport      Returned by .sync() with commit hash + push status.
    ConfigError     Raised on configuration parse / validation failure.
"""

from .manager import (
    ClaudeConfig,
    ConfigError,
    DoctorReport,
    InstallReport,
    StatusReport,
    SyncReport,
)

__version__ = "0.1.0"
__all__ = [
    "ClaudeConfig",
    "ConfigError",
    "DoctorReport",
    "InstallReport",
    "StatusReport",
    "SyncReport",
    "__version__",
]
