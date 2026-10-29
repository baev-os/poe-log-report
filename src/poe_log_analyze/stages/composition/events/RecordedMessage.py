"""Source message for localized presentation of confirmed events."""

from dataclasses import asdict, dataclass

from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue


@dataclass(frozen = True, slots = True)
class RecordedMessage:
    """Preserve code, fields, and original text regardless of interface language."""

    code: str
    fields: dict
    original: str | None
    recognized: bool

    @staticmethod
    def from_record(row: dict) -> dict:
        text = row.get("text")
        header = RuleCatalogue.HEADER.fullmatch(text) if text is not None else None

        return asdict(RecordedMessage(row["type"], dict(row["fields"]),
                                     header["message"] if header else text,
                                     row["status"] == "recognized"))
