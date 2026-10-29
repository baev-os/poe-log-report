import unittest
import MapObservationAnalyticsTests

from copy import deepcopy

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.stages.composition.MechanicCombinationsBuilder import MechanicCombinationsBuilder


class MechanicCombinationsTests(unittest.TestCase):
    """Exact sets, disjoint cohorts, and the same measurement exclusions."""

    def test_exact_sets_pairs_deduplication_and_modes(self):
        rows = MapObservationAnalyticsTests.MapObservationAnalyticsTests.records()

        for row in rows:
            row['mechanics'] = ['blight', 'harvest', 'blight'] if row['line'] < 5 else []

        before = deepcopy(rows)

        result = MechanicCombinationsBuilder.build({'rows': rows + [deepcopy(rows[0])]}, ExecutionContext())

        self.assertEqual(rows, before)
        self.assertEqual((result['map_count'], result['multiple_count']), (10, 5))
        self.assertEqual(result['pairs'][0]['codes'], ['blight', 'harvest'])
        self.assertEqual(result['pairs'][0]['share'], 50)

        samples = result['modes']['all']['groups'][0]['samples']

        self.assertEqual([row['count'] for row in samples], [5, 5])
        self.assertEqual(samples[1]['difference_seconds'], 60)
        self.assertEqual(result['modes']['without_afk']['groups'][0]['samples'][1]['difference_seconds'], 30)

    def test_levels_small_groups_unknown_afk_and_empty(self):
        rows = MapObservationAnalyticsTests.MapObservationAnalyticsTests.records()

        for row in rows:
            row['mechanics'] = ['blight'] if row['line'] < 5 else []

        rows[0]['remaining_seconds'] = None
        rows[1]['visits'][0]['level'] = 81

        result = MechanicCombinationsBuilder.build({'rows': rows}, ExecutionContext())

        self.assertEqual(len(result['modes']['all']['groups']), 2)

        sample = result['modes']['without_afk']['groups'][0]['samples'][1]

        self.assertFalse(sample['ready'])
        self.assertIsNone(sample['difference_seconds'])
        self.assertEqual(sample['complete'], 3)
        self.assertEqual(MechanicCombinationsBuilder.build({'rows': []}, ExecutionContext())['sets'], [])
