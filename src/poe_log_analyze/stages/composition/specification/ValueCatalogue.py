from dataclasses import dataclass

@dataclass(frozen = True, slots = True)
class ValueCatalogue:
    """Finite list of allowed values from the executable catalogue."""

    code: str
    label: str
    values: tuple[str, ...]
