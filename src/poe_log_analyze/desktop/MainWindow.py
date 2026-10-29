"""Analysis window built with standard Tkinter/ttk."""

import tkinter as tk
import webbrowser

from collections.abc import Callable
from pathlib import Path
from queue import Empty
from time import monotonic

from tkinter import messagebox, ttk

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.result.ReportResult import ReportResult

from poe_log_analyze.desktop.ActionPanel import ActionPanel
from poe_log_analyze.desktop.GenerateReportAction import GenerateReportAction
from poe_log_analyze.desktop.DesktopStyle import DesktopStyle
from poe_log_analyze.desktop.FileDialogLayout import FileDialogLayout
from poe_log_analyze.desktop.InputViewport import InputViewport
from poe_log_analyze.desktop.LicenseQuery import LicenseQuery
from poe_log_analyze.desktop.ProgressPanel import ProgressPanel
from poe_log_analyze.desktop.SessionState import SessionState
from poe_log_analyze.desktop.Task import Task
from poe_log_analyze.desktop.WindowLayout import WindowLayout

from poe_log_analyze.runtime.Workspace import Workspace


class MainWindow(tk.Tk):
    """Update widgets on the main loop; run generation in a Thread."""

    def __init__(self, handler: ReportGenerator, output: Path | None = None):
        super().__init__()

        self.withdraw()
        DesktopStyle.apply(self)
        self.file_dialog_layout = FileDialogLayout(self)
        self.title('Path of Exile Log Analyze')
        self.closed = False
        self.protocol("WM_DELETE_WINDOW", self.close)

        menu = tk.Menu(self)
        help_menu = tk.Menu(menu, tearoff = False)
        help_menu.add_command(label = 'Licenses', command = self.open_licenses)
        menu.add_cascade(label = 'Help', menu = help_menu)

        self.configure(menu = menu)
        self.session = SessionState()

        output = output if output is not None else Workspace.default_workspace()
        previous = output / "public/index.html"

        if previous.is_file():
            self.session.result_dir = previous.parent.parent
            self.session.report_path = previous

        self.analysis_action = GenerateReportAction(handler)
        self.task: Task | None = None

        container = ttk.Frame(self, padding = 16)
        container.pack(fill = tk.BOTH, expand = True)

        self.viewport = InputViewport(container)
        self.inputs = self.viewport.inputs
        self.inputs.workspace.set(str(output))
        self.actions = ActionPanel(container, self.start_analysis, self.open_report, self.cancel_task)
        self.progress = ProgressPanel(container)

        self.set_busy(False)
        self.layout = WindowLayout(self, self.viewport, self.actions, self.progress)
        self.deiconify()

    def open_licenses(self) -> None:
        directory = LicenseQuery.directory()

        if not webbrowser.open(directory.as_uri()):
            messagebox.showinfo('Licenses', 'License directory: ' + str(directory), parent = self)

    def set_busy(self, busy: bool) -> None:
        self.inputs.set_enabled(not busy)
        self.actions.update_available(busy, self.session.report_path is not None)

    def launch(self, operation: Callable[[ExecutionContext], ReportResult]) -> None:
        if self.task is not None:
            return

        self.set_busy(True)
        self.progress.start()
        self.task = Task(operation)
        self.task.start()
        self.after(20, self.poll_task)

    def poll_task(self) -> None:
        task = self.task

        if task is None:
            return

        finished = not task.is_alive()
        deadline = monotonic() + .012

        for _ in range(128):
            if monotonic() >= deadline:
                break

            try:
                event = task.events.get_nowait()
            except Empty:
                break

            match event.kind:
                case "state":
                    self.on_generation_state(event.value)
                case "progress":
                    self.progress.update_progress(event.value)
                case "succeeded":
                    self.on_result(event.value)
                case "failed":
                    self.progress.finish('Operation failed: ' + str(event.value), False)
                case "cancelled":
                    self.progress.finish('Operation cancelled. The previous result was preserved.', False)

        if finished and task.events.empty():
            task.join()
            self.task = None
            self.set_busy(False)

            if self.session.closing:
                self.close()
        else:
            self.after(20, self.poll_task)

    def on_generation_state(self, snapshot) -> None:
        self.actions.cancel.state(["!disabled" if snapshot.status.value in ("created", "running") else "disabled"])
        self.progress.update_state(snapshot)

    def start_analysis(self) -> None:
        if self.task is not None:
            return

        paths = self.inputs.paths()

        if not paths or not self.inputs.workspace.get().strip():
            self.progress.message.set('Add log files.')
            return

        try:
            operation = self.analysis_action.prepare(paths, Path(self.inputs.workspace.get()),
                self.inputs.timezone_key(), self.inputs.language_code(),
                period = self.inputs.period.value(),
                comparison_period = self.inputs.comparison_period.value() if self.inputs.compare.get() else None,
                outputs = self.inputs.outputs(), pdf_dark = self.inputs.pdf_dark.get())
        except ValueError as error:
            self.progress.message.set(str(error))
            return

        self.launch(operation)

    def open_report(self) -> None:
        path = self.session.report_path

        if path is not None:
            entry = path.parent.parent.parent / "index.html"

            if not webbrowser.open(entry.as_uri()):
                self.progress.message.set(f"Could not open the browser. Report: {entry}")

    def on_result(self, result: ReportResult) -> None:
        self.session.result_dir = result.directory
        self.session.report_path = result.report_path
        self.progress.finish(f"Analysis complete. Report ready: {result.report_path}", True)

    def cancel_task(self) -> None:
        if self.task is not None and not self.task.stop.is_set():
            self.task.stop.set()
            self.progress.notice('Cancelling… waiting for the current stage to finish.')

    def close(self) -> None:
        if self.closed:
            return

        self.session.closing = True

        if self.task is not None:
            self.cancel_task()
        else:
            self.closed = True
            self.progress.bar.stop()
            self.progress.stop_clock()
            self.layout.close()
            self.destroy()
