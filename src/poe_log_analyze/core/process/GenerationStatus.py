from enum import StrEnum


class GenerationStatus(StrEnum):
    """Lifecycle of one run."""

    CREATED = "created"
    RUNNING = "running"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    PUBLISHING = "publishing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
