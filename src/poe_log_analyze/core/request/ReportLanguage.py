"""Validated language selection for one export."""

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen = True, slots = True)
class ReportLanguage:
    """Freeze the language code before starting background work."""

    code: str = "en"
    LABELS: ClassVar[dict[str, str]] = {"en": "English", "ru": "Russian"}

    def __post_init__(self) -> None:
        if self.code not in self.LABELS:
            raise ValueError('Report language must be en or ru')

    @property
    def label(self) -> str:
        return self.LABELS[self.code]
