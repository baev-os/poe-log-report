from dataclasses import dataclass

@dataclass(frozen = True, slots = True)
class TimezoneOption:
    """IANA identifier and offset when the list was created."""

    key: str
    label: str
    offset_minutes: int
