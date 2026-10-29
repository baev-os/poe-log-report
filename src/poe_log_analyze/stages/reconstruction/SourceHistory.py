from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen = True, slots = True)
class SourceHistory:
    """One source's history; line numbers still belong to that source."""

    directory: Path
    data: dict[str, Any]
    manifest: dict[str, Any]
    model: dict[str, Any]
    activity: dict[str, Any]
    manifest_sha256: str

    @property
    def digest(self) -> str:
        return str(self.manifest['artifacts_sha256']['lines.jsonl'])
