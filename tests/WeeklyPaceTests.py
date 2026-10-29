import json
import unittest
import AreaDetailsTests
import MapPaceTests
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

from poe_log_analyze.stages.composition.DailyAreaStatisticsBuilder import DailyAreaStatisticsBuilder
from poe_log_analyze.stages.composition.DailyPlaytimeBuilder import DailyPlaytimeBuilder
from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection
from poe_log_analyze.stages.composition.WeeklyPaceBuilder import WeeklyPaceBuilder
from poe_log_analyze.stages.composition.sessions.SessionHistoryBuilder import SessionHistoryBuilder


class WeeklyPaceTests(unittest.TestCase):
    """Weeks preserve shared measurements, empty gaps, and exact links."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @staticmethod
    def fixture():
        first = MapPaceTests.MapPaceTests.fixture().replace('2026/09/01', '2026/09/06').replace('2026/09/02', '2026/09/07')
        second = MapPaceTests.MapPaceTests.fixture().replace('2026/09/01', '2026/09/21').replace('2026/09/02', '2026/09/22')
        second = second.replace('ID = 1', 'ID = 101').replace('ID = 2', 'ID = 102').replace('seed 1', 'seed 101').replace('seed 2', 'seed 102')

        return first + second

    def source(self, name, text):
        path = self.root / name
        path.write_text(text)

        return path

    def report(self, name, sources, **options):
        result = ReportGenerator().generate(ReportRequest(tuple(sources), self.root / name, **options))
        return result.report_path.parent

    @staticmethod
    def data(public, name = 'weekly_pace'):
        return json.loads((public.parent / 'project/data' / (name + '.json')).read_text())

    @staticmethod
    def interval(start, seconds):
        end = datetime.fromisoformat(start) + timedelta(seconds = seconds)
        return {'started_at': start, 'ended_at': end.isoformat(), 'seconds': seconds}

    @staticmethod
    def build(runs, intervals, period = ReportPeriod(), zone = 'Asia/Almaty'):
        selection = ReportPeriodSelection(period, zone, ExecutionContext())
        selected, activity = selection.runs(runs), selection.intervals(intervals)
        play = DailyPlaytimeBuilder.build({'intervals': activity}, zone)
        areas = DailyAreaStatisticsBuilder.build(selected, zone, {day['date'] for day in play['days']}, selection.control)
        sessions = SessionHistoryBuilder([], [], selected, selection)

        return WeeklyPaceBuilder.build(runs, selected, selection, sessions, play, areas)

    def test_sunday_monday_returns_empty_week_and_ru_en_links(self):
        source = self.source('synthetic.txt', self.fixture())
        original = source.read_bytes()
        paths = []

        for language in ('ru', 'en'):
            public = self.report(language, (source, source), report_language = language, generate_pdf = True)
            model = self.data(public)

            self.assertEqual([week['date'] for week in model['weeks']], ['2026-08-31', '2026-09-07', '2026-09-14', '2026-09-21'])
            self.assertEqual([week['partial'] for week in model['weeks']], [True, False, False, True])

            rows = model['panels'][0]['rows']

            self.assertEqual([row['new'] for row in rows], [1, 1, 0, 2])
            self.assertEqual([row['returns'] for row in rows], [0, 1, 0, 1])
            self.assertEqual([row['map_seconds'] for row in rows], [60, 88, 0, 148])
            self.assertEqual([row['play_seconds'] for row in rows], [60, 180, 0, 240])
            self.assertEqual([row['mean_seconds'] for row in rows], [None, 60, None, 74])
            self.assertEqual([row['complete'] for row in rows], [0, 1, 0, 2])
            self.assertEqual(sum(row['play_seconds'] for row in rows), self.data(public, 'daily_playtime')['seconds'])

            pace = self.data(public, 'map_pace')['summary']

            self.assertEqual(sum(row['new'] for row in rows), pace['new'])
            self.assertEqual(sum(row['returns'] for row in rows), pace['returns'])
            self.assertEqual(sum(row['map_seconds'] for row in rows), pace['map_seconds'])
            self.assertIsNone(rows[2]['rate'])

            paths.append([panel['path'] for panel in model['panels']])

            self.assertIn('weeks/index.html', (public / 'pace/index.html').read_text())

            html = (public / 'pace/weeks/index.html').read_text()

            self.assertIn('href="#week-2026-09-07"', html)
            self.assertIn('maps/2026-09-07/index.html', html)
            self.assertIn('events/page-2.html#line-', html)
            self.assertIn('#visit-', html)
            self.assertIn('Synthetic &lt;City &amp; Square&gt;', html)
            self.assertNotIn('weekly.title', html)

            for panel in model['panels'][1:]:
                self.assertRegex(panel['path'], r'^pace/weeks/[0-9a-f]{64}/index.html$')
                self.assertIn(f'lang="{language}"', (public / panel['path']).read_text())

            manifest = json.loads((public.parent / 'report-manifest.json').read_text())

            self.assertEqual(manifest['pdf']['content_version'], '12')

        self.assertEqual(paths[0], paths[1])
        self.assertEqual(source.read_bytes(), original)

    def test_week_slice_matches_existing_pace_and_export_without_source(self):
        source = self.source('synthetic.txt', self.fixture())

        public = self.report('full', (source,))
        expected = self.data(public)['panels'][0]['rows'][1]
        analysis = public.parents[1] / 'analysis'
        source.unlink()

        exported = self.report('slice', (analysis,), mode = ReportMode.EXPORT,
                               period = ReportPeriod(date(2026, 9, 7), date(2026, 9, 13)))
        weekly = self.data(exported)
        actual = weekly['panels'][0]['rows'][0]
        pace = self.data(exported, 'map_pace')['summary']

        for key in ('count', 'new', 'returns', 'map_seconds', 'play_seconds', 'rate', 'complete', 'excluded', 'mean_seconds', 'median_seconds'):
            self.assertEqual(actual[key], expected[key], key)
            self.assertEqual(actual[key], pace[key], key)

        self.assertFalse(weekly['weeks'][0]['partial'])
        self.assertEqual(len(weekly['weeks'][0]['days']), 7)

    def test_weighted_metrics_type_filter_and_previous_week_changes(self):
        run = AreaDetailsTests.AreaDetailsTests.run_record
        runs = [run(1, 'MapWorldsDunes', 'Dunes', '2026-09-07T10:00:00+05:00', '2026-09-07T10:00:10+05:00', 'map'),
                run(3, 'MapWorldsDunes', 'Dunes', '2026-09-07T10:01:00+05:00', '2026-09-07T10:01:30+05:00', 'map'),
                run(5, 'MapWorldsDunes', 'Dunes', '2026-09-09T10:00:00+05:00', '2026-09-09T10:01:30+05:00', 'map'),
                run(7, 'MapWorldsDunes', 'Dunes', '2026-09-14T10:00:00+05:00', '2026-09-14T10:01:00+05:00', 'map'),
                run(9, 'MapWorldsCitySquare', 'City Square', '2026-09-07T10:02:00+05:00', '2026-09-07T10:05:00+05:00', 'map'),
                run(11, 'HideoutOssuary', 'Hideout', '2026-09-07T10:05:00+05:00', '2026-09-07T10:06:00+05:00', 'hideout'),
                run(13, '1_1_1', 'Other', '2026-09-07T10:06:00+05:00', '2026-09-07T10:07:00+05:00')]
        intervals = [self.interval(f'2026-09-{day:02}T10:00:00+05:00', 600) for day in (7, 9, 14)]
        before = deepcopy((runs, intervals))

        model = self.build(runs, intervals, ReportPeriod(date(2026, 9, 7), date(2026, 9, 20)))
        panel = next(panel for panel in model['panels'] if panel['area_id'] == 'MapWorldsDunes')
        first, second = panel['rows']

        self.assertAlmostEqual(first['mean_seconds'], 130 / 3)
        self.assertEqual((first['median_seconds'], first['rate'], second['rate']), (30, 9, 6))

        changes = {row['code']: row for row in second['changes']}

        self.assertEqual((changes['new']['delta'], changes['rate']['delta'], changes['median_seconds']['delta']), (-2, -3, 30))
        self.assertAlmostEqual(changes['new']['change_percent'], -200 / 3)
        self.assertFalse(second['comparison_partial'])
        self.assertEqual([zone['seconds'] for zone in model['weeks'][0]['zones']], [310, 60, 60])
        self.assertAlmostEqual(sum(zone['share'] for zone in model['weeks'][0]['zones']), 100)
        self.assertEqual(model['panels'][0]['rows'][0]['new'], 4)
        self.assertEqual((runs, intervals), before)

    def test_unknown_dates_zero_duration_and_missing_denominator(self):
        run = AreaDetailsTests.AreaDetailsTests.run_record
        stamp = '2026-09-07T00:00:00+05:00'
        runs = [run(1, '', '../../<unsafe>', None, None, 'map'), run(3, 'first', 'Same', stamp, stamp, 'map'),
                run(5, 'second', 'Same', stamp, stamp, 'map')]

        model = self.build(runs, [])

        self.assertEqual(model['panels'][0]['undated'], 1)
        self.assertEqual(len({panel['path'] for panel in model['panels']}), 4)

        row = model['panels'][0]['rows'][0]

        self.assertEqual((row['new'], row['complete'], row['mean_seconds']), (2, 2, 0))
        self.assertIsNone(row['rate'])
        self.assertEqual(self.build(runs[:1], [])['weeks'], [])

    def test_period_edges_empty_weeks_and_zero_baseline(self):
        run = AreaDetailsTests.AreaDetailsTests.run_record
        runs = [run(1, 'map', 'Map', '2026-09-14T00:00:00+05:00', '2026-09-14T00:01:00+05:00', 'map')]
        interval = self.interval('2026-09-14T00:00:00+05:00', 60)

        model = self.build(runs, [interval], ReportPeriod(date(2026, 9, 8), date(2026, 9, 15)))

        self.assertEqual([week['partial'] for week in model['weeks']], [True, True])

        rows = model['panels'][0]['rows']
        change = next(change for change in rows[1]['changes'] if change['code'] == 'new')

        self.assertEqual(change['delta'], 1)
        self.assertIsNone(change['change_percent'])
        self.assertTrue(rows[1]['comparison_partial'])

        empty = self.build([], [], ReportPeriod(date(2026, 9, 7), date(2026, 9, 20)))

        self.assertEqual(len(empty['weeks']), 2)
        self.assertTrue(all(row['mean_seconds'] is None for row in empty['panels'][0]['rows']))

    def test_dst_monday_boundary_uses_local_dates_and_elapsed_seconds(self):
        intervals = [{'started_at': '2026-11-01T01:30:00-04:00', 'ended_at': '2026-11-02T00:30:00-05:00', 'seconds': 86400}]

        model = self.build([], intervals, zone = 'America/New_York')

        self.assertEqual([week['date'] for week in model['weeks']], ['2026-10-26', '2026-11-02'])
        self.assertEqual([week['play_seconds'] for week in model['weeks']], [84600, 1800])

    def test_branches_and_independent_logs_keep_shared_measurements(self):
        first = self.source('first.txt', SharedHistoryTests.SharedHistoryTests.prefix() + SharedHistoryTests.SharedHistoryTests.ending(12, 20, 30, 'Oshabi: Synthetic branch.'))
        second = self.source('second.txt', SharedHistoryTests.SharedHistoryTests.prefix() + SharedHistoryTests.SharedHistoryTests.ending(14, 25, 40, 'The Maven: Synthetic branch.'))

        public = self.report('branches', (first, second))
        rows = self.data(public)['panels'][0]['rows']

        self.assertEqual(sum(row['map_seconds'] for row in rows), 33)
        self.assertEqual(sum(row['complete'] for row in rows), 0)

        one = self.source('one.txt', MapPaceTests.MapPaceTests.fixture())
        two = self.source('two.txt', MapPaceTests.MapPaceTests.fixture().replace('seed 1', 'seed 17').replace('ID = 1', 'ID = 17'))
        independent = self.data(self.report('independent', (one, two)))['panels'][0]['rows'][0]

        self.assertEqual((independent['new'], independent['returns'], independent['play_seconds'], independent['map_seconds']), (4, 2, 480, 296))

    def test_cancellation_preserves_current_report(self):
        source = self.source('synthetic.txt', self.fixture())
        request = ReportRequest((source,), self.root / 'report', replace_report = True)
        generator = ReportGenerator()

        generator.generate(request)
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}

        with patch.object(WeeklyPaceBuilder, 'build', side_effect = GenerationCancelled('Синтетическая отмена')):
            with self.assertRaises(GenerationCancelled):
                generator.generate(request)

        self.assertEqual(before, {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()})

        selection = ReportPeriodSelection(ReportPeriod(), 'UTC', ExecutionContext(cancelled = lambda: True))

        with self.assertRaises(GenerationCancelled):
            WeeklyPaceBuilder.build([], [], selection, SessionHistoryBuilder([], [], [], selection), {'days': []}, {'by_date': {}})
