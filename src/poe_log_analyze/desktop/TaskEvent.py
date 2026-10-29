"""Worker message processed by the window main loop."""

from dataclasses import dataclass


@dataclass(frozen = True, slots = True)
class TaskEvent:
    """Message data contains no widgets or GUI callbacks."""

    kind: str
    value: object = None
