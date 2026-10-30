import sys

from poe_log_analyze.Bootstrap import Bootstrap

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.request.ReportRequest import ReportRequest
from poe_log_analyze.core.request.ReportMode import ReportMode

from poe_log_analyze.cli.RussianParser import RussianParser

from pathlib import Path

from zoneinfo import ZoneInfoNotFoundError

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

class AnalysisCli:
    """Command-line interface for local analysis without installing the package."""

    def __init__(self, handler: ReportGenerator) -> None:
        self._handler = handler

    @staticmethod
    def main(argv: list[str] | None = None) -> int:
        return AnalysisCli(Bootstrap.report_generator()).run(argv)

    def run(self, argv: list[str] | None = None) -> int:
        """Return 0 for diagnostics, 1 for errors, or 2 for incomplete strict analysis."""

        parser = RussianParser(description = 'Account for and recognize every PoE 1 log line',
                               add_help = False, usage = '%(prog)s [options]')
        parser.add_argument("-h", "--help", action = "help", help = 'show help')
        parser.add_argument("--input", type = Path, required = True,
                            metavar = 'FILE', help = 'source file (required)')
        parser.add_argument("--output", type = Path, default = Path("build/analysis"),
                            metavar = 'DIRECTORY', help = 'new result directory (default: build/analysis)')
        parser.add_argument("--timezone", default = "Europe/London", metavar = 'ZONE',
                            help = 'IANA timestamp time zone (default: Europe/London)')
        parser.add_argument("--require-complete", action = "store_true",
                            help = 'require no unknown lines or errors')
        args = parser.parse_args(argv)

        try:
            command = ReportRequest((args.input,), args.output, mode = ReportMode.ANALYSIS, timezone = args.timezone,
                require_complete = args.require_complete)
            result = self._handler.generate(command, ExecutionContext())

            coverage = result.summary
            assert coverage is not None
        except (OSError, ValueError, RuntimeError, ZoneInfoNotFoundError) as error:
            print(f"Analysis failed: {error}", file = sys.stderr)
            return 1

        print(f"Lines accounted for: {coverage.total_lines}; recognized: {coverage.recognized_lines}; "
              f"unknown: {coverage.unknown_lines}; errors: {coverage.error_lines}.")
        print(f"Report: {result.directory / 'coverage.md'}")

        if args.require_complete and not coverage.recognition_complete:
            print('Recognition incomplete. Diagnostic results were saved.', file = sys.stderr)
            return 2

        return 0
