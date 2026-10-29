from poe_log_analyze.core.ReportGenerator import ReportGenerator


class Bootstrap:
    """Shared application composition root for GUI and CLI."""

    @staticmethod
    def report_generator() -> ReportGenerator:
        return ReportGenerator()
