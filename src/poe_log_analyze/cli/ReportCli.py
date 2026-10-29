import argparse
import subprocess
import sys

from poe_log_analyze.Bootstrap import Bootstrap

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.request.ReportRequest import ReportRequest
from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod
from poe_log_analyze.core.request.ReportOutputs import ReportOutputs

from datetime import date

from pathlib import Path

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

class ReportCli:
    """Command-line export of a saved analysis."""

    def __init__(self, handler: ReportGenerator) -> None:
        self._handler = handler

    @staticmethod
    def main(argv: list[str] | None = None) -> int:
        return ReportCli(Bootstrap.report_generator()).run(argv)

    def run(self, argv: list[str] | None = None) -> int:
        """Export a saved analysis without parsing the source again."""

        parser = argparse.ArgumentParser(description = 'Local HTML report')
        parser.add_argument("--result", type = Path, required = True, help = 'analysis directory')
        parser.add_argument("--output", type = Path, required = True, help = 'new report directory')
        parser.add_argument("--require-complete", action = "store_true", help = 'require complete recognition')
        parser.add_argument("--report-language", choices = ("ru", "en"), default = "en", help = 'report language: en (default) or ru')
        parser.add_argument("--pdf", action = "store_true", help = 'also create a summary PDF report')

        for flag, label in (('basic', 'basic HTML'), ('basic-pdf', 'basic report PDF'),
                            ('extended', 'extended HTML'), ('extended-pdf', 'extended report PDF')):
            parser.add_argument('--' + flag, action = argparse.BooleanOptionalAction, default = None, help = label)

        parser.add_argument("--date-from", help = 'inclusive period start, YYYY-MM-DD, in the analysis time zone')
        parser.add_argument("--date-to", help = 'inclusive period end, YYYY-MM-DD, in the analysis time zone')
        parser.add_argument('--compare-from', help = 'baseline period A start, YYYY-MM-DD')
        parser.add_argument('--compare-to', help = 'baseline period A end, YYYY-MM-DD; all four A/B dates are required')

        parser.add_argument("--dark-pdf", action = "store_true", help = 'Dark theme for PDFs and area image')
        args = parser.parse_args(argv)

        try:
            values = (args.basic, args.basic_pdf, args.extended, args.extended_pdf)

            if args.pdf and any(value is not None for value in values):
                raise ValueError('Use per-report PDF flags instead of --pdf')

            outputs = None if args.pdf else ReportOutputs(*(default if value is None else value
                for value, default in zip(values, (True, True, False, False))))
            period = ReportPeriod(date.fromisoformat(args.date_from) if args.date_from else None,
                                  date.fromisoformat(args.date_to) if args.date_to else None)
            comparison = (ReportPeriod(date.fromisoformat(args.compare_from) if args.compare_from else None,
                                       date.fromisoformat(args.compare_to) if args.compare_to else None)
                          if args.compare_from is not None or args.compare_to is not None else None)
            command = ReportRequest((args.result,), args.output, mode = ReportMode.EXPORT,
                require_complete = args.require_complete, report_language = args.report_language,
                generate_pdf = args.pdf, period = period, comparison_period = comparison, outputs = outputs, pdf_dark = args.dark_pdf)
            path = self._handler.generate(command, ExecutionContext()).report_path
        except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError) as error:
            print(f"Report creation failed: {error}", file = sys.stderr)
            return 1

        print(f"Local report: {path}")

        if args.pdf and path is not None:
            print(f"PDF: {path.parent / 'report.pdf'}")

        if outputs is not None and path is not None:
            for profile in ('basic', 'extended'):
                if getattr(outputs, profile + '_pdf'):
                    print(f"PDF: {path.parent.parent / 'pdf' / profile / 'report.pdf'}")

        return 0
