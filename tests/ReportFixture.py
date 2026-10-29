from pathlib import Path

from poe_log_analyze.Bootstrap import Bootstrap

from poe_log_analyze.core.request.ReportRequest import ReportRequest
from poe_log_analyze.core.request.ReportMode import ReportMode


class ReportFixture:
    """Brief shared-core invocation for report-content checks."""

    @staticmethod
    def export_report(result_dir: Path, output: Path, *, require_complete = False, control = None, report_language = "ru"):
        result = Bootstrap.report_generator().generate(ReportRequest((result_dir,), output,
            mode = ReportMode.EXPORT, require_complete = require_complete, report_language = report_language), control)
        return result.report_path
