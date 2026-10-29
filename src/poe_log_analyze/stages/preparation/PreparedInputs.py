from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen = True, slots = True)
class PreparedInputs:
    """Canonical inputs and validated destination directory."""

    paths: tuple[Path, ...]
    output: Path
