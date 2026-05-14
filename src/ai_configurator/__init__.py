"""ai-configurator: manage Claude Code's ~/.claude/ via symlinks from a content dir.

Public API:
    ClaudeConfig        The single management class (fluent, OOP, configurable).
    InstallReport       Returned by .install() with counts of links created.
    UninstallReport     Returned by .uninstall().
    DoctorReport        Returned by .doctor() with health summary.
    StatusReport        Returned by .status() with tracked + untracked breakdown.
    SyncReport          Returned by .sync() with commit hash + push status.
    CleanupReport       Returned by .cleanup() with per-category removals.
    ListingReport       Returned by .list_contents(): grouped content view.
    ListingGroup        Member of ListingReport.groups.
    BootstrapReport     Returned by .bootstrap() with per-step outcome.
    BootstrapStep       Member of BootstrapReport.steps.
    ValidationReport    Returned by .validate() with blockers + warnings.
    Prompter            Type alias for the prompter callable used by .bootstrap().
    ConfigError         Raised on configuration parse / validation failure.
"""

from __future__ import annotations

from importlib import metadata as _md

from .manager import (
    BootstrapReport,
    BootstrapStep,
    ClaudeConfig,
    CleanupReport,
    ConfigError,
    DecisionFile,
    DecisionPack,
    DecisionsApplyReport,
    DecisionsListReport,
    DoctorReport,
    FetchReport,
    InstallReport,
    ListingGroup,
    ListingReport,
    Prompter,
    ReconcileReport,
    RepairAction,
    RepairReport,
    StatusReport,
    SyncReport,
    UninstallReport,
    ValidationReport,
)

try:
    __version__ = _md.version("ai-configurator")
except _md.PackageNotFoundError:
    # Editable install before metadata is built, or running from source tree.
    __version__ = "0.0.0+unknown"

__all__ = [
    "BootstrapReport",
    "BootstrapStep",
    "ClaudeConfig",
    "CleanupReport",
    "ConfigError",
    "DecisionFile",
    "DecisionPack",
    "DecisionsApplyReport",
    "DecisionsListReport",
    "DoctorReport",
    "FetchReport",
    "InstallReport",
    "ListingGroup",
    "ListingReport",
    "Prompter",
    "ReconcileReport",
    "RepairAction",
    "RepairReport",
    "StatusReport",
    "SyncReport",
    "UninstallReport",
    "ValidationReport",
    "__version__",
]
