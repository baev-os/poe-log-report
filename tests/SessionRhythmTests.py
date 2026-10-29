import unittest

from copy import deepcopy

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod

from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection
from poe_log_analyze.stages.composition.sessions.SessionHistoryBuilder import SessionHistoryBuilder
from poe_log_analyze.stages.composition.sessions.SessionRhythmBuilder import SessionRhythmBuilder


class SessionRhythmTests(unittest.TestCase):
    """Half-hour boundaries, original anchor, DST, and unknown AFK."""

    @staticmethod
    def build(start = '2026-10-25T02:45:00+02:00', end = '2026-10-25T02:45:00+01:00', *, marked = True):
        definitions = [{'first_line': 1, 'line_ranges': [[1, 10]], 'branches': [
            {'first_line': 1, 'last_line': 10, 'started_at': start, 'ended_at': end, 'reason': 'eof'}]}]
        intervals = [{'first_line': 1, 'started_at': start, 'ended_at': end, 'seconds': 3600, 'incomplete': False}]

        if marked:
            intervals[0]['afk_intervals'] = [{'entered_at': '2026-10-25T02:50:00+02:00',
                                            'ended_at': '2026-10-25T02:10:00+01:00'}]

        selection = ReportPeriodSelection(ReportPeriod(), 'Europe/Berlin', ExecutionContext())
        sessions = SessionHistoryBuilder(definitions, intervals, [], selection)
        before = deepcopy(intervals)
        result = SessionRhythmBuilder.build(definitions, intervals, [], {'rows': [], 'gaps': {'rows': []}}, sessions, selection)

        return result['by_session']['1'], before, intervals

    def test_utc_bins_marked_time_and_no_mutation(self):
        row, before, intervals = self.build()

        self.assertEqual(before, intervals)
        self.assertEqual([part['play_seconds'] for part in row['bins']], [1800, 1800])
        self.assertEqual([part['afk_seconds'] for part in row['bins']], [1200, 0])
        self.assertEqual(row['early']['remaining_seconds'], 600)
        self.assertEqual(row['late']['remaining_seconds'], 1800)
        self.assertIn('+02:00', row['bins'][0]['started_at'])
        self.assertIn('+01:00', row['bins'][1]['started_at'])

    def test_missing_afk_is_unknown_not_zero(self):
        row, _, _ = self.build(marked = False)

        self.assertIsNone(row['early']['remaining_seconds'])
        self.assertIsNone(row['late']['rate_without_afk'])

    def test_streak_breaks_at_returns_afk_and_ineligible_maps(self):
        maps = [{'line': line, 'excluded': [], 'afk_seconds': 0} for line in (2, 4, 6, 8, 10)]
        gaps = [{'line': line, 'from_run': line - 2, 'session_id': '1', 'return': False,
                 'from_visit': line - 2,
                 'clipped': False, 'seconds': 60, 'afk_seconds': 0} for line in (4, 6, 8, 10)]
        gaps[1]['afk_seconds'] = 1
        maps[3]['excluded'] = ['incomplete']
        selection = ReportPeriodSelection(ReportPeriod(), 'UTC', ExecutionContext())
        result = SessionRhythmBuilder.streaks(maps, gaps, {'id': '1', 'branched': False}, selection)

        self.assertEqual([row['lines'] for row in result], [[2, 4], [6], [10]])

        gaps[0]['from_visit'] = 3
        result = SessionRhythmBuilder.streaks(maps, gaps, {'id': '1', 'branched': False}, selection)

        self.assertEqual([row['lines'] for row in result], [[2], [4], [6], [10]])
        self.assertEqual(SessionRhythmBuilder.streaks(maps, gaps, {'branched': True}, selection), [])
