import json

from pathlib import Path

from poe_log_analyze.stages.preparation.ResultDirectories import ResultDirectories

from poe_log_analyze.core.result.AnalysisSummary import AnalysisSummary


class AnalysisSummaryReader:
    """Project existing coverage.json files without opening original logs."""

    def execute(self, directory: Path) -> AnalysisSummary:
        summaries = []

        for source in ResultDirectories.result_directories(directory):
            data = json.loads((source / "coverage.json").read_text(encoding = "utf-8"))
            summaries.append(AnalysisSummary(
                sources = 1, total_lines = data["total_lines"],
                recognized_lines = data["recognized_lines"], unknown_lines = data["unknown_lines"],
                error_lines = data["error_lines"], accounting_complete = data["accounting_complete"],
                recognition_complete = data["recognition_complete"]))

        return AnalysisSummary(
            sources = len(summaries), total_lines = sum(item.total_lines for item in summaries),
            recognized_lines = sum(item.recognized_lines for item in summaries),
            unknown_lines = sum(item.unknown_lines for item in summaries),
            error_lines = sum(item.error_lines for item in summaries),
            accounting_complete = all(item.accounting_complete for item in summaries),
            recognition_complete = all(item.recognition_complete for item in summaries))
