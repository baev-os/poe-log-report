import unittest
import MapCycleTests

from copy import deepcopy

from poe_log_analyze.stages.composition.analytics.RecordedActivityIndex import RecordedActivityIndex
from poe_log_analyze.stages.composition.analytics.RemainingMonstersBuilder import RemainingMonstersBuilder


class RemainingMonstersTests(unittest.TestCase):
    """Last observation, known zero, separate unknown maps, and branches."""

    @staticmethod
    def fixture(*, branched = False):
        maps, spans = MapCycleTests.MapCycleTests.fixture()
        maps[0]['visits'][0]['level'] = 80
        maps[0]['branched'] = branched
        evidence = {'events': [{'line': line, 'entry_line': entry, 'timestamp': '2026-09-01T23:54:00+00:00',
                                'code': 'screen.monsters_remaining', 'fields': fields, 'text': 'Synthetic'}
                               for line, entry, fields in ((3, 2, {'count': '10', 'single': None}),
                                                           (4, 2, {'single': '1'}), (5, 2, {'count': '0'}),
                                                           (6, None, {'count': '12'}))]}
        index = RecordedActivityIndex(evidence, maps, {'links': {}}, spans.sessions, spans.selection)

        return index, {'rows': [{'line': row['first_line'], 'name': row['name']} for row in maps]}

    def test_last_snapshot_zero_denominator_and_no_mutation(self):
        index, explorer = self.fixture()
        before = deepcopy(index.evidence)

        result = RemainingMonstersBuilder.build(index, explorer)

        self.assertEqual(index.evidence, before)
        self.assertEqual((result['map_count'], result['observed_count'], result['unobserved_count']), (2, 1, 1))
        self.assertEqual(result['rows'][0]['last']['count'], 0)
        self.assertEqual(result['bins'][0]['share'], 100)
        self.assertEqual(len(result['unassigned']), 1)
        self.assertEqual(result['groups'][0]['median_count'], 0)

    def test_branches_and_missing_observations_are_not_zero(self):
        index, explorer = self.fixture(branched = True)

        result = RemainingMonstersBuilder.build(index, explorer)

        self.assertEqual((result['ambiguous_count'], result['observed_count']), (1, 0))
        self.assertIsNone(result['rows'][0]['last'])
        self.assertTrue(all(row['share'] is None for row in result['bins']))

        index.evidence['events'] = []

        self.assertEqual(RemainingMonstersBuilder.build(index, explorer)['unobserved_count'], 2)
