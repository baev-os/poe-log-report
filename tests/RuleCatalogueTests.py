"""Check shared-catalogue integrity when adding or moving rules."""

import unittest

from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue


class RuleCatalogueTests(unittest.TestCase):
    """Incorrect groups or duplicate priorities must not change classification."""

    def test_unique_priorities_identifiers_groups_and_continuation_parents(self):
        priorities, identifiers = [], []

        for group, rules in RuleCatalogue.RULE_GROUPS.items():
            self.assertTrue(rules, group)

            for priority, name, pattern in rules:
                with self.subTest(rule = name):
                    self.assertGreater(priority, 0)
                    self.assertTrue(name.startswith(group + "."))
                    self.assertTrue(pattern)

                priorities.append(priority)
                identifiers.append(name)

        self.assertEqual(len(priorities), len(set(priorities)))
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertEqual(set(identifiers), {name for name, _ in RuleCatalogue.MESSAGE_RULES})
        self.assertTrue(set(RuleCatalogue.CONTINUATIONS) <= set(identifiers))
