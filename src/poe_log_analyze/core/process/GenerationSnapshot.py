from dataclasses import dataclass

from poe_log_analyze.core.process.GenerationStatus import GenerationStatus
from poe_log_analyze.core.plan.ReportStage import ReportStage


@dataclass(frozen = True, slots = True)
class GenerationSnapshot:
    """Observer snapshot; GUI changes cannot modify the process."""

    status: GenerationStatus
    stage: ReportStage | None
    completed: tuple[ReportStage, ...]
    total: int
