from dataclasses import dataclass
from pathlib import Path

from poe_log_analyze.core.result.AnalysisSummary import AnalysisSummary


@dataclass(frozen = True, slots = True)
class ReportResult:
    """Published paths; directory points to the report for export and replacement."""

    directory: Path
    report_path: Path | None
    summary: AnalysisSummary | None
