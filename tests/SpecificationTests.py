"""Public specification completeness against the executable parser."""

import unittest

from io import BytesIO
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

from zoneinfo import ZoneInfo

from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue
from poe_log_analyze.stages.parsing.LogParser import LogParser
from poe_log_analyze.stages.composition.specification.SpecificationBuilder import SpecificationBuilder

DOCUMENT = (Path(__file__).resolve().parents[1] / "docs/rules.md").read_text()


class SpecificationTests(unittest.TestCase):
    """Codes, fields, and patterns must remain synchronized with the live catalogue."""

    def test_every_message_and_continuation_is_present_once(self):
        specification = SpecificationBuilder.build_specification(DOCUMENT)
        messages = {rule.rule_id: rule for group in specification.families for rule in group.rules}

        self.assertEqual(set(messages), {name for name, _ in RuleCatalogue.MESSAGE_RULES})

        for name, pattern in RuleCatalogue.MESSAGE_RULES:
            self.assertEqual(messages[name].pattern, pattern.pattern)
            self.assertEqual(messages[name].fields, tuple(pattern.groupindex))

        expected = {(parent, index, f"{parent}.{next(iter(pattern.groupindex))}", pattern.pattern)
                    for parent, patterns in RuleCatalogue.CONTINUATIONS.items()
                    for index, pattern in enumerate(patterns, 1)}

        self.assertEqual({(r.parent, r.sequence, r.rule_id, r.pattern) for r in specification.continuations}, expected)

        all_rules = [*messages.values(), *specification.framing, *specification.continuations]

        self.assertEqual(len({r.rule_id for r in all_rules}), specification.rule_count)
        self.assertEqual(len({r.type for r in all_rules}), specification.type_count)
        self.assertEqual({r.status for r in all_rules}, {"recognized", "unknown", "error"})

    def test_framing_matches_parser_outputs(self):
        raw = (b'\nunknown\n\xff\n'
               b'2026/09/01 10:00:00 ***** LOG FILE OPENING *****\n'
               b'2026/09/01 10:00:00 1 ab [INFO Client 1] unknown\n'
               b'2026/02/30 10:00:00 1 ab [INFO Client 1] unknown\n')
        actual = {(row['rule_id'], row['type'], row['status'])
                  for row in LogParser.iter_records(BytesIO(raw), ZoneInfo('UTC'))}

        self.assertEqual(actual, {(r.rule_id, r.type, r.status) for r in SpecificationBuilder.build_specification(DOCUMENT).framing})

    def test_alphabetical_type_blocks_include_each_rule_and_preserve_priorities(self):
        specification = asdict(SpecificationBuilder.build_specification(DOCUMENT))
        before = deepcopy(specification)
        groups = SpecificationBuilder.group_rules(specification)

        self.assertEqual([group['code'] for group in groups], sorted(group['code'] for group in groups))

        original = [*specification['framing'], *specification['continuations'],
                    *(rule for family in specification['families'] for rule in family['rules'])]
        rules = [rule for group in groups for rule in group['rules']]

        self.assertEqual(len(rules), specification['rule_count'])
        self.assertEqual({rule['rule_id']: rule for rule in rules}, {rule['rule_id']: rule for rule in original})

        for group in groups:
            ids = [rule['rule_id'] for rule in group['rules']]

            self.assertEqual(ids, sorted(ids))
            self.assertTrue(all(code.split('.')[0] == group['code'] for code in ids))

        by_type = {group['code']: group for group in groups}

        self.assertEqual(by_type['area']['label'], 'area.*')
        self.assertEqual(by_type['jewel']['label'], 'jewel.*')
        self.assertEqual(by_type['blank']['label'], 'blank')
        self.assertTrue(any(rule['parent'] for rule in by_type['action']['rules']))
        self.assertEqual(specification, before)

    def test_finite_values_and_missing_family_description(self):
        catalogues = {c.code: c.values for c in SpecificationBuilder.build_specification(DOCUMENT).catalogues}

        self.assertEqual(catalogues['SPEAKERS'], RuleCatalogue.SPEAKERS)
        self.assertEqual(catalogues['APPLY_FAILURES'], RuleCatalogue.APPLY_FAILURES)
        self.assertEqual(len(catalogues['BOOLEAN_SETTINGS']), sum(map(len, RuleCatalogue.BOOLEAN_SETTINGS.values())))

        with self.assertRaisesRegex(ValueError, 'Family descriptions'):
            SpecificationBuilder.build_specification(DOCUMENT.replace('#### `area`', '#### `unsupported`'))
