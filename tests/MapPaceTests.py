import json
import unittest
import SharedHistoryTests

from copy import deepcopy
from datetime import date, datetime, timedelta

from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import patch

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.stages.composition.MapPaceBuilder import MapPaceBuilder
from poe_log_analyze.stages.composition.MapGapBuilder import MapGapBuilder
from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection
from poe_log_analyze.stages.composition.sessions.SessionHistoryBuilder import SessionHistoryBuilder


class MapPaceTests(unittest.TestCase):
    """First entries, returns, and gaps use confirmed boundaries and provenance."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @staticmethod
    def line(second, message, start = '2026-09-01T23:59:00'):
        moment = datetime.fromisoformat(start) + timedelta(seconds = second)
        return f'{moment:%Y/%m/%d %H:%M:%S} 1 abcd [INFO Client 1] {message}\n'

    @classmethod
    def fixture(cls):
        return '\n' * 500 + ''.join(cls.line(second, message) for second, message in (
            (0, 'Client-Safe Instance ID = 1'),
            (0, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
            (0, ': You have entered Dunes.'),
            (60, 'Generating level 1 area "HideoutOssuary" with seed 9'),
            (62, ': You have entered Synthetic Hideout.'),
            (90, 'Client-Safe Instance ID = 1'),
            (90, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
            (92, ': You have entered Dunes.'),
            (120, 'Generating level 1 area "HideoutOssuary" with seed 9'),
            (122, ': You have entered Synthetic Hideout.'),
            (150, 'Client-Safe Instance ID = 2'),
            (150, 'Generating level 80 area "MapWorldsCitySquare" with seed 2'),
            (152, ': You have entered Synthetic <City & Square>.'),
            (212, 'Generating level 1 area "HideoutOssuary" with seed 9'),
            (214, ': You have entered Synthetic Hideout.'),
            (240, 'Abnormal disconnect: An unexpected disconnection occurred.'),
        ))

    def source(self, name, text):
        path = self.root / name
        path.write_text(text)

        return path

    def report(self, name, sources, **options):
        result = ReportGenerator().generate(ReportRequest(tuple(sources), self.root / name, **options))
        return result.report_path.parent

    @staticmethod
    def data(public, name = 'map_pace'):
        return json.loads((public.parent / 'project/data' / (name + '.json')).read_text())

    def test_returns_midnight_statistics_gaps_duplicates_and_ru_en(self):
        source = self.source('synthetic.txt', self.fixture())
        before = source.read_bytes()

        for language, title in (('ru', 'Темп игры на картах'), ('en', 'Mapping pace')):
            public = self.report(language, (source, source), report_language = language)
            model = self.data(public)
            summary = model['summary']

            self.assertEqual((summary['count'], summary['new'], summary['returns']), (2, 2, 1))
            self.assertEqual((summary['map_seconds'], summary['play_seconds'], summary['rate']), (148, 240, 30))
            self.assertEqual((summary['complete'], summary['excluded'], summary['mean_seconds'], summary['median_seconds']), (2, 0, 74, 74))
            self.assertEqual((summary['min_seconds'], summary['max_seconds']), (60, 88))
            self.assertEqual([day['new'] for day in model['days']], [1, 1])
            self.assertEqual([day['rate'] for day in model['days']], [60, 20])
            self.assertEqual([day['map_seconds'] for day in model['days']], [60, 88])
            self.assertEqual(summary['map_seconds'], self.data(public, 'statistics_summary')['maps']['seconds'])
            self.assertEqual(summary['play_seconds'], self.data(public, 'activity')['seconds'])
            self.assertEqual(model['sessions'][0]['rate'], 30)

            gaps = model['gaps']

            self.assertEqual((gaps['count'], gaps['seconds'], gaps['unallocated_seconds']), (2, 64, 8))
            self.assertEqual(gaps['zones'][0]['seconds'], 56)
            self.assertEqual([row['return'] for row in gaps['rows']], [True, False])

            rhythm = self.data(public, 'session_rhythm')

            self.assertEqual(max(streak['count'] for session in rhythm['by_session'].values() for streak in session['streaks']), 1)
            self.assertEqual([model['rows'][i]['seconds'] for i in model['fastest']], [60, 88])

            html = (public / 'pace/index.html').read_text()

            self.assertIn(title, html)
            self.assertIn('Synthetic &lt;City &amp; Square&gt;', html)
            self.assertNotIn('Synthetic <City', html)

            for row in model['rows']:
                target, anchor = row['href'].split('#')

                self.assertEqual(target, 'events/page-2.html')
                self.assertIn(f'id="{anchor}"', (public / target).read_text())

        self.assertEqual(source.read_bytes(), before)

    def test_clipped_period_keeps_partial_seconds_without_new_entry_or_ranking(self):
        source = self.source('synthetic.txt', self.fixture())

        public = self.report('full', (source,))
        analysis = public.parents[1] / 'analysis'
        source.unlink()

        public = self.report('day', (analysis,), mode = ReportMode.EXPORT,
                             period = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2)))
        model = self.data(public)
        summary = model['summary']

        self.assertEqual((summary['new'], summary['count'], summary['complete'], summary['excluded']), (1, 2, 1, 1))
        self.assertEqual((summary['map_seconds'], summary['mean_seconds'], summary['rate']), (88, 60, 20))
        self.assertIn('clipped', model['rows'][0]['excluded'])
        self.assertEqual(model['rows'][0]['date'], 'outside')
        self.assertEqual([bar['date'] for bar in model['chart']['bars']], ['2026-09-02'])
        self.assertEqual(model['gaps']['seconds'], 64)

    def test_branch_time_preserved_without_single_path_ranking_or_gaps(self):
        prefix = SharedHistoryTests.SharedHistoryTests.prefix()
        first = self.source('one.txt', prefix + SharedHistoryTests.SharedHistoryTests.ending(12, 20, 30, 'Oshabi: Synthetic first branch.'))
        second = self.source('two.txt', prefix + SharedHistoryTests.SharedHistoryTests.ending(14, 25, 40, 'The Maven: Synthetic second branch.'))
        model = self.data(self.report('branches', (first, second)))

        self.assertEqual((model['summary']['new'], model['summary']['map_seconds']), (1, 33))
        self.assertEqual(model['summary']['complete'], 0)
        self.assertIn('branched', model['rows'][0]['excluded'])
        self.assertEqual(model['gaps']['rows'], [])

    def test_independent_equal_clocks_and_disconnect_do_not_form_cross_session_gaps(self):
        first = self.source('one.txt', self.fixture())
        second = self.source('two.txt', self.fixture().replace('seed 1', 'seed 17').replace('ID = 1', 'ID = 17')
                             .replace('seed 2', 'seed 27').replace('ID = 2', 'ID = 27'))
        model = self.data(self.report('independent', (first, second)))

        self.assertEqual((model['summary']['new'], model['summary']['play_seconds'], model['summary']['rate']), (4, 480, 30))
        self.assertEqual(model['gaps']['count'], 4)
        self.assertEqual(len({row['session_id'] for row in model['gaps']['rows']}), 2)

        combined = self.source('combined.txt', self.fixture() + self.fixture().lstrip('\n'))
        model = self.data(self.report('disconnect', (combined,)))

        self.assertEqual(model['gaps']['count'], 4)
        self.assertEqual(len(model['sessions']), 2)

    def test_unknown_identity_incomplete_zero_and_empty_selection(self):
        text = ''.join(self.line(second, message) for second, message in (
            (0, 'Generating level 80 area "MapWorldsDunes" with seed 0'),
            (0, ': You have entered Dunes.'),
            (0, 'Generating level 1 area "HideoutOssuary" with seed 9'),
            (0, ': You have entered Hideout.'),
            (1, 'Client-Safe Instance ID = 3'),
            (1, 'Generating level 80 area "MapWorldsCitySquare" with seed 3'),
            (2, ': You have entered City Square.'),
            (3, ': SyntheticHero (Duelist) is now level 90'),
        ))
        source = self.source('synthetic.txt', text)
        model = self.data(self.report('unknown', (source,)))

        self.assertEqual(model['summary']['complete'], 0)
        self.assertIn('identity', model['rows'][0]['excluded'])
        self.assertIn('incomplete', model['rows'][1]['excluded'])
        self.assertEqual(model['summary']['map_seconds'], 0)

        empty = self.data(self.report('empty', (source,), period = ReportPeriod(date(2027, 1, 1), None)))

        self.assertEqual(empty['rows'], [])
        self.assertIsNone(empty['summary']['rate'])
        self.assertIsNone(empty['summary']['median_seconds'])

    def test_gap_clips_dst_in_utc_and_preserves_inputs(self):
        control = ExecutionContext()
        selection = ReportPeriodSelection(ReportPeriod(), 'America/New_York', control)
        definitions = [{'first_line': 1, 'line_ranges': [[1, 9]], 'branches': []}]
        intervals = [{'first_line': 1, 'started_at': '2026-11-01T01:50:00-04:00',
                      'ended_at': '2026-11-01T01:11:00-05:00', 'seconds': 1260, 'incomplete': False}]
        sessions = SessionHistoryBuilder(definitions, intervals, [], selection)
        runs = [{'name': 'Dunes', 'kind_code': 'map', 'first_line': 1,
                 'visits': [{'entry_line': 1, 'end_line': 2, 'entered_at': '2026-11-01T01:50:00-04:00',
                             'ended_at': '2026-11-01T01:51:00-04:00', 'bounded': True, 'seconds': 60}]},
                {'name': 'City Square', 'kind_code': 'map', 'first_line': 8,
                 'visits': [{'entry_line': 8, 'end_line': 9, 'entered_at': '2026-11-01T01:10:00-05:00',
                             'ended_at': '2026-11-01T01:11:00-05:00', 'bounded': True, 'seconds': 60}]}]
        before = deepcopy(runs)

        model = MapGapBuilder.build(runs, sessions, selection)

        self.assertEqual(model['seconds'], 1140)
        self.assertEqual(model['unallocated_seconds'], 1140)
        self.assertEqual(runs, before)

    def test_gap_ambiguity_and_known_zero_map_duration_are_explicit(self):
        control = ExecutionContext()
        selection = ReportPeriodSelection(ReportPeriod(), 'UTC', control)
        definitions = [{'first_line': 1, 'line_ranges': [[1, 20]], 'branches': [{}, {}]}]
        intervals = [{'first_line': 1, 'started_at': '2026-09-01T00:00:00+00:00',
                      'ended_at': '2026-09-01T00:00:30+00:00', 'seconds': 30, 'incomplete': False}]
        # Branch-boundary fields suffice for ranges.
        definitions[0]['branches'] = [{'reason': 'network.abnormal_disconnect', 'incomplete': False,
                                      'started_at': intervals[0]['started_at'], 'ended_at': intervals[0]['ended_at'],
                                       'last_line': line} for line in (19, 20)]
        sessions = SessionHistoryBuilder(definitions, intervals, [], selection)
        runs = [{'name': 'Dunes', 'kind_code': 'map', 'first_line': 1, 'visits': [
            {'entry_line': 1, 'end_line': 5, 'entered_at': '2026-09-01T00:00:00+00:00',
             'ended_at': '2026-09-01T00:00:10+00:00', 'bounded': True, 'seconds': 10},
            {'entry_line': 10, 'end_line': 15, 'entered_at': '2026-09-01T00:00:20+00:00',
             'ended_at': '2026-09-01T00:00:30+00:00', 'bounded': True, 'seconds': 10}]}]

        gaps = MapGapBuilder.build(runs, sessions, selection)

        self.assertEqual((gaps['count'], gaps['excluded_pairs'], gaps['branched_sessions']), (0, 1, 1))

        sessions.rows[1]['branched'] = False
        runs[0]['visits'][0].update(bounded = False, ended_at = None, seconds = None)

        gaps = MapGapBuilder.build(runs, sessions, selection)

        self.assertEqual((gaps['count'], gaps['excluded_pairs']), (0, 1))

        statistics = MapPaceBuilder.statistics([{'new': 1, 'returns': 0, 'seconds': 0, 'excluded': []}], 0)

        self.assertEqual(statistics['complete'], 1)
        self.assertEqual(statistics['median_seconds'], 0)
        self.assertIsNone(statistics['rate'])

        control.cancelled = lambda: True

        with self.assertRaises(GenerationCancelled):
            MapPaceBuilder.build([], [], selection, sessions, {'days': [], 'seconds': 0}, {'by_date': {}})

    def test_cancelled_composition_preserves_current_report(self):
        source = self.source('synthetic.txt', self.fixture())
        request = ReportRequest((source,), self.root / 'report', replace_report = True)
        generator = ReportGenerator()

        generator.generate(request)
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

        with patch.object(MapPaceBuilder, 'build', side_effect = GenerationCancelled('Синтетическая отмена')):
            with self.assertRaises(GenerationCancelled):
                generator.generate(request)

        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
