import unittest

from copy import deepcopy
from datetime import date
from types import SimpleNamespace

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod

from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection
from poe_log_analyze.stages.composition.analytics.MapCycleBuilder import MapCycleBuilder
from poe_log_analyze.stages.composition.analytics.MeasuredSpanIndex import MeasuredSpanIndex

from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled


class MapCycleTests(unittest.TestCase):
    """The next map's first entry completes the cycle; returns remain inside it."""

    @staticmethod
    def fixture(period = ReportPeriod(), *, marked = True):
        selection = ReportPeriodSelection(period, 'UTC', ExecutionContext())
        session = {'path': 'sessions/1/index.html', 'branched': False}
        sessions = SimpleNamespace(rows = {1: session}, session = lambda line: 1)
        interval = {'first_line': 1, 'started_at': '2026-09-01T23:50:00+00:00',
                    'ended_at': '2026-09-02T00:10:00+00:00', 'seconds': 1200}

        if marked:
            interval['afk_intervals'] = [{'entered_at': '2026-09-01T23:55:00+00:00',
                                          'ended_at': '2026-09-02T00:00:00+00:00'}]

        maps = [{'kind_code': 'map', 'first_line': 2, 'started_at': interval['started_at'],
                 'name': 'Synthetic A', 'area_id': 'MapWorldsDunes', 'identity_complete': True,
                 'visits': [{'entry_line': 2, 'entered_at': interval['started_at'],
                             'ended_at': '2026-09-01T23:55:00+00:00', 'seconds': 300, 'bounded': True}]},
                {'kind_code': 'map', 'first_line': 8, 'started_at': interval['ended_at'],
                 'name': 'Synthetic B', 'area_id': 'MapWorldsBeach', 'identity_complete': True, 'visits': []}]
        hideout = {'kind_code': 'hideout', 'visits': [{'entry_line': 4, 'entered_at': '2026-09-01T23:55:00+00:00',
                    'ended_at': interval['ended_at'], 'seconds': 900, 'bounded': True}]}
        spans = MeasuredSpanIndex(selection.intervals([interval]), maps + [hideout], sessions, selection)

        return maps, spans

    def test_cycle_balance_zero_and_inputs_unchanged(self):
        maps, spans = self.fixture()
        before = deepcopy(maps)

        model = MapCycleBuilder.build(maps, spans, {'links': {}})
        row = model['rows'][0]

        self.assertEqual(maps, before)
        self.assertEqual((row['seconds'], row['map_seconds'], row['outside_seconds'], row['afk_seconds']), (1200, 300, 900, 300))
        self.assertEqual(model['summary']['median_seconds'], 1200)
        self.assertEqual(model['without_afk']['median_seconds'], 900)
        self.assertEqual(model['open_cycles'], 1)

        maps[1]['started_at'] = maps[0]['started_at']

        model = MapCycleBuilder.build(maps, spans, {'links': {}})

        self.assertEqual(model['summary']['median_seconds'], 0)

    def test_period_unknown_afk_branches_and_empty(self):
        maps, spans = self.fixture(ReportPeriod(date(2026, 9, 2), date(2026, 9, 2)))
        row = MapCycleBuilder.build(maps, spans, {'links': {}})['rows'][0]

        self.assertEqual(row['seconds'], 600)
        self.assertEqual(row['excluded'], ['clipped'])

        maps, spans = self.fixture(marked = False)

        self.assertIsNone(MapCycleBuilder.build(maps, spans, {'links': {}})['without_afk']['median_seconds'])

        spans.sessions.rows[1]['branched'] = True

        self.assertEqual(MapCycleBuilder.build(maps, spans, {'links': {}})['rows'], [])
        self.assertEqual(MapCycleBuilder.build([], spans, {'links': {}})['summary']['count'], 0)

    def test_dst_elapsed_time_and_cancelled_empty_input(self):
        maps, spans = self.fixture()
        interval = spans.intervals[1][0]
        interval.update(started_at = '2026-10-25T02:45:00+02:00', ended_at = '2026-10-25T02:45:00+01:00',
                        seconds = 3600, afk_intervals = [])
        maps[0]['started_at'], maps[1]['started_at'] = interval['started_at'], interval['ended_at']

        model = MapCycleBuilder.build(maps, spans, {'links': {}})

        self.assertEqual(model['summary']['median_seconds'], 3600)

        spans.selection.control = ExecutionContext(cancelled = lambda: True)

        with self.assertRaises(GenerationCancelled):
            MapCycleBuilder.build([], spans, {'links': {}})
