from dataclasses import dataclass
from pathlib import Path

@dataclass(slots = True)
class SessionState:
    """Shared result and its generated report."""

    result_dir: Path | None = None
    report_path: Path | None = None
    closing: bool = False
