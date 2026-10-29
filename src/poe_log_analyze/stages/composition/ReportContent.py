from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

@dataclass(frozen = True, slots = True)
class ReportContent:
    """Named JSON projections; serialized aggregate schemas remain unchanged."""

    analysis: dict[str, Any]
    manifest: dict[str, Any]
    timeline: dict[str, Any]
    maps: dict[str, Any]
    statistics: dict[str, Any]
    activity: dict[str, Any]
    flow: dict[str, Any]
    event_rows: Path

    views: dict[str, Any] = field(default_factory = dict)
