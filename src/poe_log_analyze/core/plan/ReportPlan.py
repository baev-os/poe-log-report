from dataclasses import dataclass

from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.plan.ReportStage import ReportStage


@dataclass(frozen = True, slots = True)
class ReportPlan:
    """Immutable stage sequence for the selected route."""

    mode: ReportMode

    @property
    def stages(self) -> tuple[ReportStage, ...]:
        if self.mode == ReportMode.ANALYSIS:
            return (ReportStage.PREPARATION, ReportStage.PARSING)

        if self.mode == ReportMode.EXPORT:
            return tuple(stage for stage in ReportStage if stage != ReportStage.PARSING)

        if self.mode == ReportMode.FULL:
            return tuple(ReportStage)

        raise ValueError('Unknown generation route')
