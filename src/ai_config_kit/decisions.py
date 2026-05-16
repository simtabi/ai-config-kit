"""Decision-pack data types (SPEC C1).

Extracted from ``manager.py`` to keep that file's surface focused on
the orchestrator (``ClaudeConfig``) instead of mixing in pack data
shape. The ``decisions_*`` methods that operate on these types still
live on ``ClaudeConfig`` — they touch enough of its state
(``src_dir``, ``_audit``, ``_matches_secret``, ``_decisions_root``)
that extracting them would require either a tight back-reference or
an awkward dependency-injection layer.

Public types re-exported via ``ai_config_kit/__init__.py``:

- :class:`DecisionFile`         a single file in a pack
- :class:`DecisionPack`         a whole pack (name + files + readme)
- :class:`DecisionsListReport`  every bundled pack
- :class:`DecisionsApplyReport` outcome of ``decisions_apply``
- :class:`DecisionDiff`         one file's diff against on-disk state
- :class:`DecisionsDiffReport`  every file's diff for one pack
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DecisionFile:
    """A single file inside a bundled decision pack."""

    src: str
    dest: str
    # Octal string ("0755") set on dest after copy. None leaves the mode at
    # umask default. Only the low 12 bits (perms + sticky) are honored.
    mode: str | None = None


@dataclass(frozen=True)
class DecisionPack:
    name: str
    description: str
    version: str
    files: list[DecisionFile] = field(default_factory=list)
    readme: str = ""

    def summary(self) -> str:
        files = "\n".join(f"    {f.dest}" for f in self.files)
        return (
            f"{self.name} ({self.version})\n"
            f"  {self.description}\n"
            f"  files ({len(self.files)}):\n{files}"
        )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "files": [
                {"src": f.src, "dest": f.dest, "mode": f.mode}
                for f in self.files
            ],
            "readme": self.readme,
        }


@dataclass(frozen=True)
class DecisionsListReport:
    packs: list[DecisionPack] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        return {"packs": [p.to_json_dict() for p in self.packs]}

    def summary(self) -> str:
        if not self.packs:
            return "no bundled decision packs"
        lines = [f"{len(self.packs)} bundled pack(s):"]
        for p in self.packs:
            lines.append(f"  {p.name:30s} {p.description}")
        return "\n".join(lines)


@dataclass(frozen=True)
class DecisionsApplyReport:
    pack: str
    written: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    overwritten: list[str] = field(default_factory=list)
    dry_run: bool = False

    @property
    def total(self) -> int:
        return len(self.written) + len(self.overwritten) + len(self.skipped)

    def summary(self) -> str:
        prefix = "[dry-run] " if self.dry_run else ""
        parts = [f"applied {self.pack}"]
        if self.written:
            parts.append(f"{len(self.written)} new")
        if self.overwritten:
            parts.append(f"{len(self.overwritten)} overwritten")
        if self.skipped:
            parts.append(f"{len(self.skipped)} skipped (already present)")
        return prefix + "; ".join(parts)


@dataclass(frozen=True)
class DecisionDiff:
    """One pack file's diff against the current on-disk state.

    Surfaced by ``ClaudeConfig.decisions_diff`` so the CLI can show a
    unified diff before clobbering content with ``--force``.

    @field dest      Relative path (under ``src_dir``) of the file.
    @field kind      One of "new", "same", "changed".
    @field unified   The ``difflib.unified_diff`` output. Empty for "same"
                     and "new" (callers can show the new content via
                     ``new_content``).
    @field new_content   The proposed file content.
    @field old_content   The current on-disk content (empty for "new").
    """

    dest: str
    kind: str
    unified: str = ""
    new_content: str = ""
    old_content: str = ""


@dataclass(frozen=True)
class DecisionsDiffReport:
    pack: str
    diffs: list[DecisionDiff] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return any(d.kind in {"new", "changed"} for d in self.diffs)

    def summary(self) -> str:
        new = sum(1 for d in self.diffs if d.kind == "new")
        changed = sum(1 for d in self.diffs if d.kind == "changed")
        same = sum(1 for d in self.diffs if d.kind == "same")
        parts = []
        if new:
            parts.append(f"{new} new")
        if changed:
            parts.append(f"{changed} changed")
        if same:
            parts.append(f"{same} same")
        return f"pack {self.pack}: " + ("; ".join(parts) if parts else "no files")
