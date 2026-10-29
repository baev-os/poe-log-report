from pathlib import Path
from zoneinfo import ZoneInfo

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.request.ReportRequest import ReportRequest
from poe_log_analyze.core.request.ReportMode import ReportMode

from poe_log_analyze.runtime.Workspace import Workspace
from poe_log_analyze.runtime.RuntimeResources import RuntimeResources

from poe_log_analyze.stages.preparation.PreparedInputs import PreparedInputs
from poe_log_analyze.stages.preparation.ResultDirectories import ResultDirectories


class PrepareInputs:
    """Validate the output path and inputs before creating temporary results."""

    def execute(self, request: ReportRequest, control: ExecutionContext) -> PreparedInputs:
        control.check()
        output = (Workspace.current_report_output(request.output) if request.replace_report
                  else Workspace.local_output(request.output))

        if not request.replace_report and (output.exists() or output.is_symlink()):
            raise FileExistsError('The result directory already exists')

        paths = tuple(path.resolve(strict = True) for path in request.inputs)

        if any(path.is_relative_to(output) for path in paths):
            raise ValueError('The result cannot contain source data')

        if request.replace_report:
            temporary = Workspace.local_output(output.parent / "build/tmp/report-generation")

            if any(path in (output.parent / "index.html", output.parent / "report.pdf") or path.is_relative_to(temporary)
                   or path == temporary.with_suffix(".lock") for path in paths):
                raise ValueError("Source data must not be inside the report's internal workspace")

        RuntimeResources.configure_timezone()

        if request.mode == ReportMode.EXPORT:
            if any(not path.is_dir() for path in paths):
                raise ValueError('A saved-analysis directory is required')

            if len(paths) == 1:
                paths = tuple(ResultDirectories.result_directories(paths[0]))
        else:
            if any(not path.is_file() for path in paths):
                raise ValueError('Input must be a regular file')

            ZoneInfo(request.timezone)

        return PreparedInputs(paths, output)
