import json

from functools import cache

from poe_log_analyze.runtime.RuntimeResources import RuntimeResources

from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue


class MercenaryGreetings:
    """Known mercenary greeting: a separate observation, not a duel outcome."""

    FAMILIES = (', the Cyaxan', ', the Keitan', ', the Azadin', ', the Bardiyan')

    @staticmethod
    @cache
    def greetings() -> frozenset[str]:
        path = RuntimeResources.resource_root() / 'site/data/mercenary-greetings.json'
        return frozenset(json.loads(path.read_text(encoding = 'utf-8')))

    @classmethod
    def matches(cls, speaker: str, utterance: str) -> bool:
        if speaker not in RuleCatalogue.SPEAKERS or not any(family in speaker for family in cls.FAMILIES):
            return False

        # Gameplay dialogue may contain trailing spaces; preserve the original separately.
        greeting = utterance.rstrip(' \t')

        # The source catalogue records this line without a trailing ellipsis.
        if greeting == 'Death waits with open arms...':
            greeting = 'Death waits with open arms'

        return greeting in cls.greetings()
