from collections.abc import Callable
from functools import partial
from pathlib import Path

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.request.ReportRequest import ReportRequest
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod
from poe_log_analyze.core.request.ReportOutputs import ReportOutputs
from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.result.ReportResult import ReportResult


class GenerateReportAction:
    """Freeze window input before handing the operation to the worker thread."""

    def __init__(self, handler: ReportGenerator) -> None:
        self._handler = handler

    def prepare(self, inputs: tuple[Path, ...], workspace: Path, timezone: str,
                language: str, generate_pdf: bool = False,
                period: ReportPeriod = ReportPeriod(),
                comparison_period: ReportPeriod | None = None,
                outputs: ReportOutputs | None = None, pdf_dark: bool = False) -> Callable[[ExecutionContext], ReportResult]:

        command = ReportRequest(inputs, workspace, timezone = timezone,
                                report_language = language, replace_report = True, generate_pdf = generate_pdf,
                                period = period, comparison_period = comparison_period, outputs = outputs, pdf_dark = pdf_dark)
        return partial(self._handler.generate, command)
