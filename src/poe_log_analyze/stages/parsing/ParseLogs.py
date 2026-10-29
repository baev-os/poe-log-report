from pathlib import Path

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.stages.parsing.LogAnalysisService import LogAnalysisService
from poe_log_analyze.stages.parsing.CollectionAnalysisService import CollectionAnalysisService
from poe_log_analyze.stages.parsing.ParsedLogs import ParsedLogs
from poe_log_analyze.stages.preparation.AnalysisSummaryReader import AnalysisSummaryReader


class ParseLogs:
    """Streaming recognition; always account for complete source files."""

    def execute(self, paths: tuple[Path, ...], output: Path,
                request: ReportRequest, control: ExecutionContext) -> ParsedLogs:

        if len(paths) == 1:
            LogAnalysisService.analyze(paths[0], output, request.timezone,
                require_complete = request.require_complete,
                source_label = paths[0].stem if request.mode == ReportMode.FULL else "", control = control)
        else:
            CollectionAnalysisService.analyze_collection(paths, output, request.timezone,
                require_complete = request.require_complete, control = control)

        return ParsedLogs(output, AnalysisSummaryReader().execute(output))
