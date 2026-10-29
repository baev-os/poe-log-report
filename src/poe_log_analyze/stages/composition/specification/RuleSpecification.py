from dataclasses import dataclass

@dataclass(frozen = True, slots = True)
class RuleSpecification:
    """Classifier code, outcome, and exact recognition pattern."""

    rule_id: str
    type: str
    status: str
    fields: tuple[str, ...] = ()
    pattern: str = ""
    priority: int | None = None
    parent: str = ""
    sequence: int | None = None
    description: str = ""
