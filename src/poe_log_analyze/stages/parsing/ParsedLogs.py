from dataclasses import dataclass
from pathlib import Path

from poe_log_analyze.core.result.AnalysisSummary import AnalysisSummary


@dataclass(frozen = True, slots = True)
class ParsedLogs:
    """Initial analysis without eliminating source duplicates."""

    directory: Path
    summary: AnalysisSummary
