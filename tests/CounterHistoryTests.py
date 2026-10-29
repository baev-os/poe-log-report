"""Cumulative readings must not become totals or personal counters."""

import unittest

from copy import deepcopy

from poe_log_analyze.stages.composition.events.CounterHistoryBuilder import CounterHistoryBuilder


class CounterHistoryTests(unittest.TestCase):
    def test_repeated_decreasing_undated_and_cross_source_samples_stay_independent(self):
        builder = CounterHistoryBuilder()

        self.assertEqual(builder.result()['count'], 0)

        rows = [
            {'line_number': 1, 'record_id': 1, 'status': 'recognized', 'type': 'screen.character_info',
             'fields': {'character': 'SyntheticPlayer'}},
            {'line_number': 2, 'record_id': 2, 'status': 'recognized', 'type': 'screen.kill_count',
             'fields': {'count': '1,000'}, 'timestamp': '2026-09-01T13:00:00+05:00'},
            {'line_number': 3, 'record_id': 3, 'status': 'recognized', 'type': 'screen.kill_count',
             'fields': {'count': '1,000'}, 'timestamp': '2026-09-01T12:00:00+05:00'},
            {'line_number': 4, 'record_id': 4, 'status': 'recognized', 'type': 'screen.death_count',
             'fields': {'count': '0'}},
            {'line_number': 5, 'record_id': 5, 'status': 'recognized', 'type': 'screen.kill_count',
             'fields': {'count': '10'}, 'history_boundary': True},
            {'line_number': 6, 'record_id': 5, 'status': 'recognized', 'type': 'screen.kill_count',
             'fields': {'count': '999'}},
            {'line_number': 7, 'record_id': 7, 'status': 'unknown', 'type': 'screen.kill_count',
             'fields': {'count': '999'}},
        ]
        before = deepcopy(rows)

        for row in rows:
            builder.add(row)

        model = builder.result()

        self.assertEqual(rows, before)
        self.assertEqual(model['count'], 4)
        self.assertEqual([sample['count'] for sample in model['rows']], ['1,000', '1,000', '0', '10'])
        self.assertEqual([sample['line'] for sample in model['rows']], [2, 3, 4, 5])
        self.assertEqual(model['rows'][2]['time'], '—')
        self.assertNotIn('SyntheticPlayer', str(model))
        self.assertNotIn('delta', str(model))
