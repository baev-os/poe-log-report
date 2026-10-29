from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from poe_log_analyze.stages.reconstruction.SourceHistory import SourceHistory


@dataclass(frozen = True, slots = True)
class UnifiedHistory:
    """Merged ledger and reconstructed visits without HTML presentation data."""

    ledger: Path
    digest: str
    data: dict[str, Any]
    models: list[dict[str, Any]]
    runs: list[dict[str, Any]]
    intervals: list[dict[str, Any]]
    sources: tuple[SourceHistory, ...]
    sessions: list[dict[str, Any]] = field(default_factory = list)
    loading_routes: list[dict[str, Any]] = field(default_factory = list)
    technical_context: list[dict[str, Any]] = field(default_factory = list)
    disconnect_returns: list[dict[str, Any]] = field(default_factory = list)
    activity_evidence: dict[str, Any] = field(default_factory = lambda: {'events': [], 'focus': []})
    observation_evidence: dict[str, Any] = field(default_factory = lambda: {'events': [], 'links': [], 'paths': []})
