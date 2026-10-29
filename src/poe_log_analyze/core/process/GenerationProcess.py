import logging

from collections.abc import Callable

from poe_log_analyze.core.process.GenerationSnapshot import GenerationSnapshot
from poe_log_analyze.core.process.GenerationStatus import GenerationStatus
from poe_log_analyze.core.plan.ReportPlan import ReportPlan
from poe_log_analyze.core.plan.ReportStage import ReportStage


class GenerationProcess:
    """Single-worker state machine: validate every transition and stage order."""

    def __init__(self, plan: ReportPlan,
                 observer: Callable[[GenerationSnapshot], None] = lambda value: None) -> None:

        self._plan = plan
        self._observer = observer
        self._status = GenerationStatus.CREATED
        self._stage: ReportStage | None = None
        self._completed: tuple[ReportStage, ...] = ()

    @property
    def snapshot(self) -> GenerationSnapshot:
        return GenerationSnapshot(self._status, self._stage, self._completed, len(self._plan.stages))

    def _require(self, *statuses: GenerationStatus) -> None:
        if self._status not in statuses:
            raise RuntimeError('Invalid transition from ' + self._status)

    def _notify(self) -> None:
        # Observer failures must not cancel an already accepted result publication.
        try:
            self._observer(self.snapshot)
        except Exception:
            logging.getLogger(__name__).exception('Could not deliver generation state')

    def start(self) -> None:
        self._require(GenerationStatus.CREATED)
        self._status = GenerationStatus.RUNNING
        self._notify()

    def begin_stage(self, stage: ReportStage) -> None:
        self._require(GenerationStatus.RUNNING)

        if self._stage is not None or self._plan.stages[len(self._completed):][:1] != (stage,):
            raise RuntimeError('Invalid generation stage order')

        self._stage = stage
        self._notify()

    def complete_stage(self, stage: ReportStage) -> None:
        self._require(GenerationStatus.RUNNING)

        if self._stage != stage:
            raise RuntimeError('The stage has not been started')

        self._completed += (stage,)
        self._stage = None
        self._notify()

    def request_cancel(self) -> None:
        self._require(GenerationStatus.CREATED, GenerationStatus.RUNNING, GenerationStatus.CANCELLING)
        self._status = GenerationStatus.CANCELLING
        self._notify()

    def confirm_cancelled(self) -> None:
        self._require(GenerationStatus.CANCELLING)
        self._status = GenerationStatus.CANCELLED
        self._notify()

    def begin_publication(self) -> None:
        self._require(GenerationStatus.RUNNING)

        if self._stage is not None or self._completed != self._plan.stages:
            raise RuntimeError('Cannot save the result before all stages finish')

        self._status = GenerationStatus.PUBLISHING
        self._notify()

    def succeed(self) -> None:
        self._require(GenerationStatus.PUBLISHING)
        self._status = GenerationStatus.SUCCEEDED
        self._notify()

    def fail(self) -> None:
        self._require(GenerationStatus.CREATED, GenerationStatus.RUNNING,
                      GenerationStatus.CANCELLING, GenerationStatus.PUBLISHING)
        self._status = GenerationStatus.FAILED
        self._notify()
