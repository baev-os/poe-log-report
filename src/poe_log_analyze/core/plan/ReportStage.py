from enum import StrEnum


class ReportStage(StrEnum):
    """Stages in processing order; publication belongs to the core."""

    PREPARATION = 'Preparation'
    PARSING = 'Parsing'
    RECONSTRUCTION = 'History reconstruction'
    MERGING = 'Source merging'
    COMPOSITION = 'View composition'
    RENDERING = 'HTML rendering'
    VERIFICATION = 'Report verification'
