"""Generation worker independent of Tcl/Tk."""

from collections.abc import Callable
from queue import SimpleQueue
from threading import Event, Thread

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.execution.ProgressUpdate import ProgressUpdate
from poe_log_analyze.core.process.GenerationSnapshot import GenerationSnapshot
from poe_log_analyze.core.result.ReportResult import ReportResult

from poe_log_analyze.desktop.TaskEvent import TaskEvent


class Task(Thread):
    """Send results through a queue; access Tk only from the window."""

    def __init__(self, operation: Callable[[ExecutionContext], ReportResult]):
        super().__init__(name = "report-generation", daemon = False)

        self.operation = operation
        self.stop = Event()
        self.events: SimpleQueue[TaskEvent] = SimpleQueue()

    def report_progress(self, update: ProgressUpdate) -> None:
        self.events.put(TaskEvent("progress", update))

    def report_state(self, snapshot: GenerationSnapshot) -> None:
        self.events.put(TaskEvent("state", snapshot))

    def run(self) -> None:
        control = ExecutionContext(cancelled = self.stop.is_set, progress = self.report_progress,
                                   state_changed = self.report_state)

        try:
            self.events.put(TaskEvent("succeeded", self.operation(control)))
        except GenerationCancelled:
            self.events.put(TaskEvent("cancelled"))
        except Exception as error:
            self.events.put(TaskEvent("failed", str(error)))
