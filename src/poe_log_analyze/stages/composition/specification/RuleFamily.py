from poe_log_analyze.stages.composition.specification.RuleSpecification import RuleSpecification

from dataclasses import dataclass

@dataclass(frozen = True, slots = True)
class RuleFamily:
    """Rule family with explanations from the shared rules document."""

    code: str
    section: str
    description: str
    rules: tuple[RuleSpecification, ...]
