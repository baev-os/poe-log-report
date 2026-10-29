from dataclasses import dataclass

@dataclass(frozen = True, slots = True)
class ProgressUpdate:
    """Processed volume; total=0 means the stage size is unknown."""

    stage: str
    processed: int = 0
    total: int = 0
    lines: int = 0
    unit: str = ''
