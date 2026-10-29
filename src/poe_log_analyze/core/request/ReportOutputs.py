from dataclasses import dataclass


@dataclass(frozen = True, slots = True)
class ReportOutputs:
    """Independent website and print selections; the basic set is enabled by default."""

    basic: bool = True
    basic_pdf: bool = True
    extended: bool = False
    extended_pdf: bool = False

    def __post_init__(self) -> None:
        values = (self.basic, self.basic_pdf, self.extended, self.extended_pdf)

        if any(type(value) is not bool for value in values):
            raise ValueError('Report selections must be boolean flags')

        if not any(values):
            raise ValueError('Select at least one report or PDF')
