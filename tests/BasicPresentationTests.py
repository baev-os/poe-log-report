import unittest

from copy import deepcopy

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.stages.composition.BasicReportBuilder import BasicReportBuilder


class BasicPresentationTests(unittest.TestCase):
    """Name grouping and shares preserve measurements and unknown values."""

    def test_zones_merge_names_across_ids_preserving_totals_and_input(self):
        rows = [
            {'name': 'Synthetic Zone', 'area_id': 'one', 'visits': 2, 'seconds': 60.5, 'measured_visits': 1},
            {'name': 'Synthetic Zone', 'area_id': 'two', 'visits': 3, 'seconds': 90.5, 'measured_visits': 2},
            {'name': 'Unknown', 'visits': 1, 'seconds': 0, 'measured_visits': 0},
            {'name': 'Zero', 'visits': 1, 'seconds': 0, 'measured_visits': 1},
            {'name': 'Partial', 'visits': 1, 'seconds': 5, 'measured_visits': 0},
        ]
        original = deepcopy(rows)
        result = BasicReportBuilder.zones(rows, ExecutionContext())

        self.assertEqual(rows, original)
        self.assertEqual(result[0], {'name': 'Synthetic Zone', 'visits': 5, 'duration': '00:02:31'})

        by_name = {row['name']: row for row in result}

        self.assertEqual(by_name['Unknown']['duration'], '—')
        self.assertEqual(by_name['Zero']['duration'], '00:00:00')
        self.assertEqual(by_name['Partial']['duration'], '00:00:05')
        self.assertEqual(sum(row['visits'] for row in result), 8)

    def test_pie_uses_counts_not_rounded_labels_and_leaves_input_intact(self):
        rows = [{'name': name, 'count': count, 'percentage': label}
                for name, count, label in [('One', 1, '33.3 %'), ('Two', 2, '66.7 %'), ('Empty', 0, '0.0 %')]]
        original = deepcopy(rows)
        result = BasicReportBuilder.map_pie(rows, ExecutionContext())

        self.assertEqual(rows, original)
        self.assertEqual([row['count'] for row in result], [1, 2])
        self.assertIn('0 0,1', result[0]['path'])
        self.assertIn('0 1,1', result[1]['path'])
        self.assertEqual(result[1]['percentage'], '66.7 %')
        self.assertEqual(BasicReportBuilder.map_pie([], ExecutionContext()), [])
        self.assertEqual(BasicReportBuilder.map_pie([rows[-1]], ExecutionContext()), [])

        single = BasicReportBuilder.map_pie([rows[0]], ExecutionContext())[0]

        self.assertEqual(single['path'].count('A 100,100'), 2)

    def test_presentation_helpers_honor_cancellation(self):
        control = ExecutionContext(cancelled = lambda: True)

        with self.assertRaises(GenerationCancelled):
            BasicReportBuilder.zones([{}], control)

        with self.assertRaises(GenerationCancelled):
            BasicReportBuilder.map_pie([{'count': 1}], control)

        with self.assertRaises(GenerationCancelled):
            BasicReportBuilder.time_balance({'categories': [{}]}, None, control)

        with self.assertRaises(GenerationCancelled):
            BasicReportBuilder.activities({'groups': [{}]}, control)
