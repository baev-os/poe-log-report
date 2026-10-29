import sys
import argparse

class DesktopLauncher:
    """Single standalone entry point for the window and diagnostic modes."""

    @staticmethod
    def main():
        """Launch the GUI or an explicitly selected command without a graphical session."""

        if len(sys.argv) > 1 and sys.argv[1] == "--cli":
            from poe_log_analyze.cli.AnalysisCli import AnalysisCli
            return AnalysisCli.main(sys.argv[2:])

        if len(sys.argv) > 1 and sys.argv[1] == "--report":
            from poe_log_analyze.cli.ReportCli import ReportCli
            return ReportCli.main(sys.argv[2:])

        if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
            parser = argparse.ArgumentParser(description = 'Standalone GUI and report check')
            parser.add_argument("directory")
            parser.add_argument("--report-language", choices = ("ru", "en"), default = "en")
            args = parser.parse_args(sys.argv[2:])

            from poe_log_analyze.desktop.DesktopSmokeTest import DesktopSmokeTest
            return DesktopSmokeTest().run(args.directory, args.report_language)

        from poe_log_analyze.desktop.DesktopApplication import DesktopApplication
        return DesktopApplication.main()
