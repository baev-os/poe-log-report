from dataclasses import dataclass


@dataclass(frozen = True, slots = True)
class AnalysisSummary:
    """Complete input accounting; cross-source duplicates are not excluded here."""

    sources: int
    total_lines: int
    recognized_lines: int
    unknown_lines: int
    error_lines: int
    accounting_complete: bool
    recognition_complete: bool

    def __post_init__(self) -> None:
        counts = (self.sources, self.total_lines, self.recognized_lines,
                  self.unknown_lines, self.error_lines)

        if any(type(value) is not int or value < 0 for value in counts) or self.sources == 0:
            raise ValueError('Invalid analysis counters')

        if self.total_lines != self.recognized_lines + self.unknown_lines + self.error_lines:
            raise ValueError('Analysis counters do not reconcile')

        if type(self.accounting_complete) is not bool or type(self.recognition_complete) is not bool:
            raise ValueError('Invalid analysis completeness flags')

        if self.recognition_complete != (self.unknown_lines == self.error_lines == 0):
            raise ValueError('Recognition completeness disagrees with counters')
