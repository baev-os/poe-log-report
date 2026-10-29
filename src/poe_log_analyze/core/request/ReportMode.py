from enum import StrEnum


class ReportMode(StrEnum):
    """Three supported routes through the same process."""

    FULL = "full"
    ANALYSIS = "analysis"
    EXPORT = "export"
