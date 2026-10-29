import unittest
import MapObservationAnalyticsTests

from copy import deepcopy

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.stages.composition.MapConsistencyBuilder import MapConsistencyBuilder


class MapConsistencyTests(unittest.TestCase):
    """Linear quartiles, known zero, weekly cohorts, and exclusions."""

    def test_quantiles_zero_one_and_fractional(self):
        self.assertIsNone(MapConsistencyBuilder.quantile([], .25))
        self.assertEqual(MapConsistencyBuilder.quantile([0], .75), 0)
        self.assertEqual(MapConsistencyBuilder.quantile([0, 60, 120, 180, 240], .25), 60)
        self.assertEqual(MapConsistencyBuilder.quantile([0, 60, 120, 180, 240], .75), 180)
        self.assertEqual(MapConsistencyBuilder.quantile([0, 1], .25), .25)

    def test_same_id_level_week_and_common_exclusions(self):
        rows = MapObservationAnalyticsTests.MapObservationAnalyticsTests.records()

        for row in rows:
            row['date'] = '2026-09-01' if row['line'] < 5 else '2026-09-08'

        rows[0]['remaining_seconds'] = None
        rows[1]['excluded'] = ['clipped']
        rows[2]['visits'][0]['level'] = 81
        before = deepcopy(rows)

        result = MapConsistencyBuilder.build({'rows': rows + [deepcopy(rows[0])]}, ExecutionContext())

        self.assertEqual(rows, before)

        groups = result['modes']['all']['groups']

        self.assertEqual(len(groups), 2)
        self.assertEqual([row['week'] for row in groups[0]['weeks']], ['2026-08-31', '2026-09-07'])
        self.assertEqual(groups[0]['weeks'][0]['complete'], 3)
        self.assertEqual(groups[0]['weeks'][0]['q1_seconds'], 120)
        self.assertEqual(result['modes']['without_afk']['groups'][0]['weeks'][0]['complete'], 2)
        self.assertEqual(MapConsistencyBuilder.build({'rows': []}, ExecutionContext())['modes']['all']['groups'], [])
