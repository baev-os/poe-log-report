import json
import unittest
import AreaDetailsTests
import SharedHistoryTests

from copy import deepcopy
from datetime import date, datetime

from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import patch

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.stages.composition.PlaytimeHeatmapBuilder import PlaytimeHeatmapBuilder
from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection


class PlaytimeHeatmapTests(unittest.TestCase):
    """Hourly cells preserve measured seconds, days, and calendar context."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @staticmethod
    def interval(start, end):
        return {'started_at': start, 'ended_at': end,
                'seconds': datetime.fromisoformat(end).timestamp() - datetime.fromisoformat(start).timestamp()}

    @staticmethod
    def panel(model, code = 'all'):
        return next(panel for panel in model['panels'] if panel['code'] == code)

    @classmethod
    def cell(cls, model, weekday, hour, code = 'all'):
        return cls.panel(model, code)['rows'][weekday]['cells'][hour]

    @staticmethod
    def build(intervals, runs = (), zone = 'Asia/Almaty', period = ReportPeriod()):
        selection = ReportPeriodSelection(period, zone, ExecutionContext())
        return PlaytimeHeatmapBuilder.build(selection.intervals(intervals), selection.runs(list(runs)), zone,
                                           {'by_date': {'2026-09-01': {}, '2026-09-02': {}}}, selection.control)

    def source(self, name, text):
        path = self.root / name
        path.write_text(text)

        return path

    def report(self, name, sources, **options):
        result = ReportGenerator().generate(ReportRequest(tuple(sources), self.root / name, **options))
        return result.report_path.parent

    @staticmethod
    def data(public, name = 'playtime_heatmap'):
        return json.loads((public.parent / 'project/data' / (name + '.json')).read_text())

    def test_midnight_multiple_dates_and_period_keep_sums(self):
        intervals = [self.interval('2026-09-01T23:45:00+05:00', '2026-09-02T01:15:00+05:00'),
                     self.interval('2026-09-08T23:30:00+05:00', '2026-09-08T23:40:00+05:00')]
        before = deepcopy(intervals)

        model = self.build(intervals)

        self.assertEqual(self.panel(model)['seconds'], 6000)
        self.assertEqual(self.panel(model)['active_days'], 3)
        self.assertEqual((self.cell(model, 1, 23)['seconds'], self.cell(model, 1, 23)['active_days']), (1500, 2))
        self.assertEqual([day['date'] for day in self.cell(model, 1, 23)['days']], ['2026-09-08', '2026-09-01'])
        self.assertIsNone(self.cell(model, 1, 23)['days'][0]['href'])
        self.assertEqual(self.cell(model, 1, 23)['days'][1]['href'], 'maps/2026-09-01/index.html')
        self.assertEqual(self.cell(model, 2, 0)['seconds'], 3600)
        self.assertEqual(self.cell(model, 2, 1)['seconds'], 900)

        selected = self.build(intervals, period = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2)))

        self.assertEqual(self.panel(selected)['seconds'], 4500)
        self.assertEqual(self.panel(selected)['active_days'], 1)
        self.assertEqual(intervals, before)

    def test_dst_repeated_skipped_and_half_hour_transitions(self):
        cases = [
            ('America/New_York', '2026-03-08T00:30:00-05:00', '2026-03-08T04:30:00-04:00', [1800, 3600, 0, 3600, 1800]),
            ('America/New_York', '2026-11-01T00:30:00-04:00', '2026-11-01T03:30:00-05:00', [1800, 7200, 3600, 1800]),
            ('Australia/Lord_Howe', '2026-04-05T00:30:00+11:00', '2026-04-05T03:30:00+10:30', [1800, 5400, 3600, 1800]),
            ('Australia/Lord_Howe', '2026-10-04T01:30:00+10:30', '2026-10-04T03:30:00+11:00', [0, 1800, 1800, 1800]),
        ]

        for zone, start, end, values in cases:
            with self.subTest(zone = zone, start = start):
                interval = self.interval(start, end)

                model = self.build([interval], zone = zone)

                self.assertEqual(self.panel(model)['seconds'], interval['seconds'])
                self.assertEqual([self.cell(model, 6, hour)['seconds'] for hour in range(len(values))], values)
                self.assertEqual(self.panel(model)['active_days'], 1)

    def test_quarter_hour_zone_and_fractional_seconds(self):
        model = self.build([self.interval('2026-09-01T15:14:59.500000+00:00', '2026-09-01T15:15:00.500000+00:00')],
                           zone = 'Asia/Kathmandu')

        self.assertEqual(self.cell(model, 1, 20)['seconds'], 0.5)
        self.assertEqual(self.cell(model, 1, 21)['seconds'], 0.5)
        self.assertEqual(self.panel(model)['seconds'], 1)

    def test_filters_use_known_parts_and_existing_area_catalogue(self):
        start, end = '2026-09-01T23:00:00+05:00', '2026-09-01T23:01:00+05:00'
        run = AreaDetailsTests.AreaDetailsTests.run_record
        runs = [run(1, 'MapWorldsDunes', 'Synthetic map', start, end, 'map'),
                run(3, 'HideoutOssuary', 'Synthetic hideout', start, end, 'hideout'),
                run(5, 'Delve_Main', 'Synthetic mine', start, end),
                run(7, '1_1_1', 'Synthetic act', start, end),
                run(9, 'unknown', 'Azurite Mine', start, end),
                run(11, 'MapWorldsDunes', 'Unknown end', start, None, 'map'),
                run(13, 'MapWorldsDunes', 'Known zero', start, start, 'map')]
        runs[5]['visits'][0]['segments'] = [deepcopy(runs[0]['visits'][0])]
        before = deepcopy(runs)

        model = self.build([self.interval(start, end)], runs)

        self.assertEqual([self.panel(model, code)['seconds'] for code in PlaytimeHeatmapBuilder.FILTERS], [60, 120, 60, 60])
        self.assertEqual(self.panel(model, 'maps')['active_days'], 1)
        self.assertEqual(model['maximum_seconds'], 120)
        self.assertEqual(self.cell(model, 1, 23, 'maps')['level'], 5)
        self.assertEqual(runs, before)

    def test_empty_unknown_zero_and_reversed_intervals_have_no_activity(self):
        stamp = '2026-09-01T00:00:00+05:00'
        intervals = [{'started_at': None, 'ended_at': None}, {'started_at': stamp, 'ended_at': None},
                     self.interval(stamp, stamp), self.interval('2026-09-01T01:00:00+05:00', stamp)]

        model = self.build(intervals)

        self.assertEqual(model['maximum_seconds'], 0)

        for panel in model['panels']:
            self.assertEqual((panel['seconds'], panel['active_days']), (0, 0))
            self.assertEqual(sum(len(row['cells']) for row in panel['rows']), 168)
            self.assertTrue(all(not cell['days'] and cell['level'] == 0 for row in panel['rows'] for cell in row['cells']))

    def test_reports_duplicates_ru_en_export_without_source_and_period(self):
        source = self.source('synthetic.txt', AreaDetailsTests.AreaDetailsTests.fixture())
        before = source.read_bytes()

        public = self.report('full', (source, source), generate_pdf = True)
        model = self.data(public)

        self.assertEqual(self.panel(model)['seconds'], self.data(public, 'daily_playtime')['seconds'])
        self.assertEqual(self.panel(model)['seconds'], 240)
        self.assertEqual(self.panel(model, 'maps')['seconds'], 148)
        self.assertEqual(self.panel(model, 'hideout')['seconds'], 56)
        self.assertEqual(self.panel(model)['active_days'], 2)
        self.assertEqual(self.cell(model, 1, 23)['seconds'], 60)
        self.assertEqual(self.cell(model, 2, 0)['seconds'], 180)
        self.assertEqual(source.read_bytes(), before)

        analysis = public.parents[1] / 'analysis'
        source.unlink()

        for language in ('ru', 'en'):
            exported = self.report(language, (analysis,), mode = ReportMode.EXPORT, report_language = language)

            self.assertEqual(self.data(exported), model)

            for name in ('index.html', 'playtime/index.html'):
                html = (exported / name).read_text()

                self.assertIn('heatmap-chart', html)
                self.assertIn('href="#heatmap-all-1-23"', html)
                self.assertIn('id="heatmap-all-1-23"', html)
                self.assertIn('maps/2026-09-01/index.html', html)
                self.assertNotIn('heatmap.title', html)

        selected = self.report('selected', (analysis,), mode = ReportMode.EXPORT,
                               period = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2)))

        self.assertEqual(self.panel(self.data(selected))['seconds'], 180)
        self.assertEqual(self.panel(self.data(selected), 'maps')['seconds'], 88)
        self.assertEqual(self.panel(self.data(selected))['active_days'], 1)

        empty = self.report('empty', (analysis,), mode = ReportMode.EXPORT, period = ReportPeriod(date(2030, 1, 1), None))

        self.assertEqual(self.panel(self.data(empty))['seconds'], 0)
        self.assertNotIn('data-heatmap-cell', (empty / 'index.html').read_text())

    def test_branches_and_independent_equal_clocks_preserve_measured_time(self):
        first = self.source('first.txt', SharedHistoryTests.SharedHistoryTests.prefix() + SharedHistoryTests.SharedHistoryTests.ending(12, 20, 30, 'Oshabi: Synthetic first branch.'))
        second = self.source('second.txt', SharedHistoryTests.SharedHistoryTests.prefix() + SharedHistoryTests.SharedHistoryTests.ending(14, 25, 40, 'The Maven: Synthetic second branch.'))

        public = self.report('branches', (first, second))
        model = self.data(public)

        self.assertEqual(self.panel(model, 'maps')['seconds'], 33)
        self.assertEqual(self.panel(model)['seconds'], self.data(public, 'daily_playtime')['seconds'])

        text = AreaDetailsTests.AreaDetailsTests.fixture()
        one = self.source('one.txt', text)
        two = self.source('two.txt', text.replace('seed 1', 'seed 17').replace('ID = 1', 'ID = 17'))
        independent = self.data(self.report('independent', (one, two)))

        self.assertEqual(self.panel(independent)['seconds'], 480)
        self.assertEqual(self.panel(independent, 'maps')['seconds'], 296)
        self.assertEqual(self.cell(independent, 1, 23)['active_days'], 1)

    def test_cancellation_preserves_previous_report(self):
        source = self.source('synthetic.txt', AreaDetailsTests.AreaDetailsTests.fixture())
        request = ReportRequest((source,), self.root / 'report', replace_report = True)
        generator = ReportGenerator()

        generator.generate(request)
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}

        with patch.object(PlaytimeHeatmapBuilder, 'build', side_effect = GenerationCancelled('Синтетическая отмена')):
            with self.assertRaises(GenerationCancelled):
                generator.generate(request)

        self.assertEqual(before, {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()})

        with self.assertRaises(GenerationCancelled):
            PlaytimeHeatmapBuilder.build([], [], 'UTC', {'by_date': {}}, ExecutionContext(cancelled = lambda: True))
