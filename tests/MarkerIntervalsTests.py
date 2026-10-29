import unittest
import MapCycleTests

from copy import deepcopy
from datetime import datetime, timedelta

from poe_log_analyze.stages.composition.analytics.MarkerIntervalsBuilder import MarkerIntervalsBuilder


class MarkerIntervalsTests(unittest.TestCase):
    """Completed spans are separate from open boundaries and unknown maps."""

    @staticmethod
    def fixture():
        _, spans = MapCycleTests.MapCycleTests.fixture()
        start = datetime.fromisoformat('2026-09-01T23:50:00+00:00')
        rows = [{'line': line, 'timestamp': (start + timedelta(minutes = line)).isoformat(),
                 'new': True, 'session_id': '1', 'excluded': []} for line in range(2, 7)]
        observations = {'groups': [{'code': 'blight', 'label_key': 'mechanic.blight', 'count': 2,
                                    'months': [{'days': [{'rows': [{'line': 3}, {'line': 6}]}]}], 'undated': []}]}

        return rows, observations, spans

    def test_intervening_maps_measured_time_and_censored_boundaries(self):
        rows, observations, spans = self.fixture()
        before = deepcopy(rows)

        result = MarkerIntervalsBuilder.build(observations, {'rows': rows}, spans)

        self.assertEqual(rows, before)

        group = result['groups'][0]

        self.assertEqual((group['observed_count'], group['median_maps'], group['max_maps']), (2, 2, 2))
        self.assertEqual(group['intervals'][0]['seconds'], 180)
        self.assertEqual([row['count'] for row in group['spells']], [1, 2])
        self.assertTrue(group['spells'][0]['left_censored'])
        self.assertFalse(group['spells'][1]['right_censored'])

    def test_unknown_identity_breaks_sequence_and_branches_are_excluded(self):
        rows, observations, spans = self.fixture()
        rows[2]['excluded'] = ['identity']

        result = MarkerIntervalsBuilder.build(observations, {'rows': rows}, spans)

        self.assertEqual((result['skipped_maps'], result['sequence_count']), (1, 2))
        self.assertEqual(result['groups'][0]['intervals'], [])

        spans.sessions.rows[1]['branched'] = True

        result = MarkerIntervalsBuilder.build(observations, {'rows': rows}, spans)

        self.assertEqual(result['skipped_maps'], 5)
        self.assertEqual(MarkerIntervalsBuilder.build(observations, {'rows': []}, spans)['groups'][0]['spells'], [])
