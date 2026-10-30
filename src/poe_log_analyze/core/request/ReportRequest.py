from dataclasses import dataclass
from pathlib import Path

from poe_log_analyze.core.request.ReportLanguage import ReportLanguage
from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod
from poe_log_analyze.core.request.ReportOutputs import ReportOutputs


@dataclass(frozen = True, slots = True)
class ReportRequest:
    """Frozen input; execution control is supplied separately."""

    inputs: tuple[Path, ...]
    output: Path
    timezone: str = "Europe/London"
    report_language: str = "en"
    mode: ReportMode = ReportMode.FULL
    require_complete: bool = False
    replace_report: bool = False
    generate_pdf: bool = False
    period: ReportPeriod = ReportPeriod()
    comparison_period: ReportPeriod | None = None
    outputs: ReportOutputs | None = None
    pdf_dark: bool = False

    def __post_init__(self) -> None:
        ReportLanguage(self.report_language)

        if type(self.pdf_dark) is not bool:
            raise ValueError('The dark theme must be a boolean flag')

        if self.outputs is not None:
            if not isinstance(self.outputs, ReportOutputs) or self.mode == ReportMode.ANALYSIS:
                raise ValueError('Report selection is available only when generating a report')

            if self.generate_pdf:
                raise ValueError('When selecting reports, specify PDF separately for each profile')

        if not isinstance(self.period, ReportPeriod):
            raise ValueError('Invalid report period')

        if self.period.active and self.mode == ReportMode.ANALYSIS:
            raise ValueError('Select the period when generating the report; analysis preserves the entire log')

        if self.comparison_period is not None:
            if not isinstance(self.comparison_period, ReportPeriod):
                raise ValueError('Invalid comparison baseline period')

            if self.mode == ReportMode.ANALYSIS:
                raise ValueError('Comparison is available only when generating a report')

            if any(p.date_from is None or p.date_to is None for p in (self.period, self.comparison_period)):
                raise ValueError('Comparison requires both report period B dates and both baseline period A dates')

        if not isinstance(self.mode, ReportMode):
            raise ValueError('Unknown generation route')

        if not isinstance(self.inputs, tuple) or not self.inputs or any(not isinstance(p, Path) for p in self.inputs):
            raise ValueError('A nonempty immutable set of input paths is required')

        if self.replace_report and self.mode != ReportMode.FULL:
            raise ValueError('Replacing the current report requires the full route')

        if self.generate_pdf and self.mode == ReportMode.ANALYSIS:
            raise ValueError('PDF is available only when generating a report')
