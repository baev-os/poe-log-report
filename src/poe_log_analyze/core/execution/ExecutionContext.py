import logging

from collections.abc import Callable
from dataclasses import dataclass, field

from time import monotonic

from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.process.GenerationSnapshot import GenerationSnapshot
from poe_log_analyze.core.execution.ProgressUpdate import ProgressUpdate


@dataclass
class ExecutionContext:
    """Cancellation and observation; stages exchange data through explicit results."""

    cancelled: Callable[[], bool] = lambda: False
    progress: Callable[[ProgressUpdate], None] = lambda value: None
    state_changed: Callable[[GenerationSnapshot], None] = lambda value: None
    on_cancel: Callable[[], None] = lambda: None
    _last: float = field(default = 0, init = False)
    _current: ProgressUpdate | None = field(default = None, init = False)

    def check(self) -> None:
        if self.cancelled():
            self.on_cancel()
            raise GenerationCancelled('Operation cancelled')

        now = monotonic()

        if self._current is not None and now - self._last >= 1:
            self._notify(self._current, now)

    def report(self, stage: str, processed: int = 0, total: int = 0,
               lines: int = 0, force: bool = False, *, unit: str = '') -> None:

        self.check()
        now = monotonic()

        update = ProgressUpdate(stage, processed, total, lines, unit)

        if force or self._current is None or stage != self._current.stage or now - self._last >= 0.1:
            self._notify(update, now)
        else:
            self._current = update

    def _notify(self, update: ProgressUpdate, now: float) -> None:
        self._current = update
        self._last = now

        try:
            self.progress(update)
        except Exception:
            logging.getLogger(__name__).exception('Could not deliver progress')
