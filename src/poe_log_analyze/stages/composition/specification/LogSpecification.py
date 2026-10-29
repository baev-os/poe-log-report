from poe_log_analyze.stages.composition.specification.RuleFamily import RuleFamily
from poe_log_analyze.stages.composition.specification.RuleSpecification import RuleSpecification
from poe_log_analyze.stages.composition.specification.ValueCatalogue import ValueCatalogue

from dataclasses import dataclass

@dataclass(frozen = True, slots = True)
class LogSpecification:
    """Versioned snapshot of all supported rules for the HTML report."""

    version: str
    rules_version: str
    schema_version: str
    header: str
    framing: tuple[RuleSpecification, ...]
    families: tuple[RuleFamily, ...]
    continuations: tuple[RuleSpecification, ...]
    catalogues: tuple[ValueCatalogue, ...]
    rule_count: int
    type_count: int
