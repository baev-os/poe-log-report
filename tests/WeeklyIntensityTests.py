import unittest

from copy import deepcopy

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.stages.composition.WeeklyIntensityBuilder import WeeklyIntensityBuilder


class WeeklyIntensityTests(unittest.TestCase):
    """Exact totals, smooth profile, midnight, DST, and unknown boundaries."""

    @staticmethod
    def interval(start, end):
        return {'started_at': start, 'ended_at': end}

    def test_short_interval_is_not_rounded_to_an_hour_and_input_stays_unchanged(self):
        rows = [self.interval('2026-09-07T12:07:00+00:00', '2026-09-07T12:09:00+00:00')]
        before = deepcopy(rows)

        model = WeeklyIntensityBuilder.build(rows, 'UTC', ExecutionContext())

        self.assertEqual(rows, before)
        self.assertEqual(model['seconds'], 120)
        self.assertEqual(model['rows'][0]['seconds'], 120)
        self.assertEqual(model['maximum_seconds'], 120)

        points = model['rows'][0]['points']

        self.assertEqual(len(points), 289)
        self.assertEqual(points[12 * 12]['seconds'], 120)
        self.assertEqual(points[11 * 12 + 7]['seconds'], 0)
        self.assertEqual(points[11 * 12 + 8]['seconds'], 120)

    def test_profile_uses_one_scale_for_all_weekdays_and_sums_occurrences(self):
        rows = [self.interval('2026-09-07T12:00:00+00:00', '2026-09-07T13:00:00+00:00'),
                self.interval('2026-09-14T12:00:00+00:00', '2026-09-14T13:00:00+00:00'),
                self.interval('2026-09-08T12:00:00+00:00', '2026-09-08T13:00:00+00:00')]

        model = WeeklyIntensityBuilder.build(rows, 'UTC', ExecutionContext())

        self.assertEqual([row['seconds'] for row in model['rows']], [7200, 3600, 0, 0, 0, 0, 0])
        self.assertEqual(model['rows'][0]['points'][150]['level'], 1)
        self.assertEqual(model['rows'][1]['points'][150]['level'], .5)
        self.assertEqual(model['seconds'], 10800)

    def test_midnight_and_week_boundary_are_continuous(self):
        model = WeeklyIntensityBuilder.build([self.interval('2026-09-13T23:45:00+00:00',
            '2026-09-14T00:15:00+00:00')], 'UTC', ExecutionContext())

        self.assertEqual(model['rows'][6]['seconds'], 900)
        self.assertEqual(model['rows'][0]['seconds'], 900)
        self.assertEqual(model['rows'][6]['points'][-1]['seconds'], model['rows'][0]['points'][0]['seconds'])
        self.assertEqual(model['rows'][0]['points'][0]['seconds'], 1800)

    def test_spring_dst_gap_is_not_counted_and_repeated_hour_counts_twice(self):
        for start, end, expected in (
            ('2026-03-29T00:00:00+00:00', '2026-03-29T03:00:00+00:00', 10800),
            ('2026-10-25T00:00:00+00:00', '2026-10-25T03:00:00+00:00', 10800)):
            with self.subTest(start = start):
                model = WeeklyIntensityBuilder.build([self.interval(start, end)], 'Europe/Berlin', ExecutionContext())

                self.assertEqual(model['seconds'], expected)
                self.assertEqual(model['rows'][6]['seconds'], expected)

        self.assertEqual(model['rows'][6]['points'][30]['seconds'], 7200)

    def test_fractional_offset_fractional_seconds_and_empty_data(self):
        model = WeeklyIntensityBuilder.build([self.interval('2026-09-07T18:14:59.500000+00:00',
            '2026-09-07T18:15:00.500000+00:00')], 'Asia/Kathmandu', ExecutionContext())

        self.assertEqual(model['rows'][0]['seconds'], .5)
        self.assertEqual(model['rows'][1]['seconds'], .5)

        empty = WeeklyIntensityBuilder.build([self.interval(None, None)], 'UTC', ExecutionContext())

        self.assertEqual(len(empty['rows']), 7)
        self.assertEqual(empty['seconds'], 0)
        self.assertTrue(all(point['opacity'] == 0 for row in empty['rows'] for point in row['points']))

    def test_cancel_before_or_during_sampling(self):
        control = ExecutionContext(cancelled = lambda: True)

        with self.assertRaises(GenerationCancelled):
            WeeklyIntensityBuilder.build([], 'UTC', control)
