import json
import unittest
import AfkStatisticsTests
import SharedHistoryTests

from copy import deepcopy
from datetime import date

from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import patch

from pypdf import PdfReader

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.stages.composition.AfkMeasurements import AfkMeasurements
from poe_log_analyze.stages.composition.DailyPlaytimeBuilder import DailyPlaytimeBuilder
from poe_log_analyze.stages.composition.PlaytimeHeatmapBuilder import PlaytimeHeatmapBuilder


class AfkAnalyticsTests(unittest.TestCase):
    """Comparisons and charts share AFK intervals, days, and denominators."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @staticmethod
    def fixture():
        return AfkStatisticsTests.AfkStatisticsTests.fixture().replace('2026/09/01', '2026/09/06').replace('2026/09/02', '2026/09/07')

    def source(self, name, text):
        path = self.root / name
        path.write_text(text)

        return path

    def report(self, name, sources, **options):
        return ReportGenerator().generate(ReportRequest(tuple(sources), self.root / name, **options)).report_path.parent

    @staticmethod
    def data(public, name):
        return json.loads((public.parent / 'project/data' / (name + '.json')).read_text())

    @staticmethod
    def panel(model, code = 'all', reduced = False):
        return next(panel for panel in model['without_afk' if reduced else 'panels'] if panel['filter'] == code)

    def test_comparison_weeks_graphs_and_pdf_ru_en_keep_common_totals(self):
        source = self.source('synthetic.txt', self.fixture())
        before = source.read_bytes()

        for language, label in (('ru', 'Карт в час без отмеченного AFK'), ('en', 'Maps per hour excluding marked AFK')):
            public = self.report(language, (source, source), report_language = language, generate_pdf = True,
                period = ReportPeriod(date(2026, 9, 6), date(2026, 9, 7)),
                comparison_period = ReportPeriod(date(2026, 9, 6), date(2026, 9, 6)))
            afk = self.data(public, 'afk')
            model = self.data(public, 'period_comparison')

            self.assertEqual((model['a']['afk_seconds'], model['a']['remaining_seconds']), (20, 10))
            self.assertEqual(model['a']['maps_per_hour_without_afk'], 360)

            for key in ('afk_seconds', 'remaining_seconds', 'afk_share'):
                self.assertEqual(model['b'][key], afk['summary'][key])

            self.assertAlmostEqual(model['b']['maps_per_hour_without_afk'], 7200 / 35)

            share = next(row for row in model['sections'][0]['rows'] if row['code'] == 'afk_share')

            self.assertAlmostEqual(share['delta'], 55 * 100 / 90 - 20 * 100 / 30)
            self.assertIn('п.п.' if language == 'ru' else 'pp', share['delta_text'])

            weekly = self.data(public, 'weekly_pace')
            rows = weekly['panels'][0]['rows']

            self.assertEqual([row['afk_seconds'] for row in rows], [20, 35])
            self.assertEqual([row['rate_without_afk'] for row in rows], [360, 144])
            self.assertEqual(weekly['panels'][0]['charts'][0]['ticks'], weekly['panels'][0]['charts'][1]['ticks'])

            reduced = self.data(public, 'daily_playtime_without_afk')
            full = self.data(public, 'daily_playtime')

            self.assertEqual([day['seconds'] for day in reduced['days']], [10, 25])
            self.assertEqual(reduced['ticks'], full['ticks'])
            self.assertEqual([(day['date'], day['x']) for day in reduced['days']], [(day['date'], day['x']) for day in full['days']])

            heatmap = self.data(public, 'playtime_heatmap')

            self.assertEqual(self.panel(heatmap, reduced = True)['seconds'], reduced['seconds'])
            self.assertEqual([self.panel(heatmap, code, True)['seconds'] for code in ('maps', 'hideout', 'special')], [10, 10, 0])

            html = (public / 'index.html').read_text()

            self.assertIn('data-time-mode', html)
            self.assertIn('heatmap-all-without-afk-0-0', html)
            self.assertIn(label, (public / 'comparison/index.html').read_text())

            pdf = '\n'.join(page.extract_text() for page in PdfReader(public / 'report.pdf').pages)

            self.assertIn(label, ' '.join(pdf.split()))

        self.assertEqual(source.read_bytes(), before)

    def test_types_share_denominator_empty_weeks_and_period_export(self):
        source = self.source('synthetic.txt', self.fixture())

        public = self.report('full', (source,), period = ReportPeriod(date(2026, 9, 6), date(2026, 9, 22)))
        weekly = self.data(public, 'weekly_pace')

        for panel in weekly['panels']:
            self.assertEqual([row['remaining_seconds'] for row in panel['rows']], [10, 25, 0, 0])
            self.assertIsNone(panel['rows'][2]['rate_without_afk'])
            self.assertIsNone(panel['rows'][2]['afk_share'])

        self.assertEqual(next(row['delta'] for row in weekly['panels'][0]['rows'][1]['changes']
                              if row['code'] == 'afk_seconds'), 15)

        source.unlink()

        selected = self.report('export', (public.parents[1] / 'analysis',), mode = ReportMode.EXPORT,
            period = ReportPeriod(date(2026, 9, 7), date(2026, 9, 7)))

        self.assertEqual(self.data(selected, 'daily_playtime_without_afk')['seconds'], 25)
        self.assertEqual(self.data(selected, 'weekly_pace')['panels'][0]['rows'][0]['rate_without_afk'], 144)
        self.assertEqual(self.panel(self.data(selected, 'playtime_heatmap'), reduced = True)['seconds'], 25)

    def test_dst_complement_and_heatmap_repeated_hour_are_exact(self):
        interval = {'started_at': '2026-10-25T00:00:00+02:00', 'ended_at': '2026-10-25T04:00:00+01:00',
                    'seconds': 18000, 'afk_intervals': [{'entered_at': '2026-10-25T01:30:00+02:00',
                                                       'ended_at': '2026-10-25T02:30:00+01:00'}]}
        before = deepcopy(interval)
        control = ExecutionContext()
        reduced = AfkMeasurements.without([interval], control)

        self.assertEqual(sum(part['seconds'] for part in reduced), 10800)

        model = PlaytimeHeatmapBuilder.build([interval], [], 'Europe/Berlin', {'by_date': {}}, control,
            afk_rows = [{**interval['afk_intervals'][0], 'category': 'unallocated'}])
        cells = self.panel(model, reduced = True)['rows'][6]['cells']

        self.assertEqual([cell['seconds'] for cell in cells[:4]], [3600, 1800, 1800, 3600])
        self.assertEqual(model['maximum_seconds'], 7200)
        self.assertEqual(interval, before)

    def test_special_area_subtracts_only_its_measured_afk(self):
        source = self.source('special.txt', self.fixture().replace('1_1_town', 'Delve_Main'))

        public = self.report('special', (source,))
        model = self.data(public, 'playtime_heatmap')

        self.assertEqual(self.panel(model, 'special')['seconds'], 13)
        self.assertEqual(self.panel(model, 'special', True)['seconds'], 5)
        self.assertEqual(self.panel(model, 'maps', True)['seconds'], 10)
        self.assertEqual(self.panel(model, reduced = True)['seconds'], 35)

    def test_fully_afk_day_stays_on_daily_axis_but_not_heatmap_day_list(self):
        line = AfkStatisticsTests.AfkStatisticsTests.line
        source = self.source('all-afk.txt', ''.join(line(second, message) for second, message in (
            (0, ': You have entered Synthetic Zone.'), (0, ': AFK mode is now ON. Autoreply "Synthetic"'),
            (90, 'Closing game gracefully'))))

        public = self.report('full', (source,), period = ReportPeriod(date(2026, 9, 1), date(2026, 9, 2)),
                             comparison_period = ReportPeriod(date(2026, 8, 1), date(2026, 8, 1)))
        reduced = self.data(public, 'daily_playtime_without_afk')

        self.assertEqual([day['seconds'] for day in reduced['days']], [0, 0])
        self.assertEqual([day['date'] for day in reduced['days']], ['2026-09-01', '2026-09-02'])

        heatmap = self.data(public, 'playtime_heatmap')

        self.assertEqual(self.panel(heatmap, reduced = True)['active_days'], 0)
        self.assertTrue(all(not cell['days'] for row in self.panel(heatmap, reduced = True)['rows'] for cell in row['cells']))

        comparison = self.data(public, 'period_comparison')

        self.assertIsNone(comparison['a']['afk_share'])
        self.assertEqual(comparison['b']['afk_share'], 100)
        self.assertIsNone(comparison['b']['maps_per_hour_without_afk'])
        self.assertIsNone(self.data(public, 'weekly_pace')['panels'][0]['rows'][0]['rate_without_afk'])

    def test_copies_branches_and_independent_clocks_keep_remaining_time(self):
        fixture = SharedHistoryTests.SharedHistoryTests
        first = self.source('one.txt', fixture.prefix() + fixture.ending(12, 20, 30, 'Oshabi: Synthetic first branch.'))
        second = self.source('two.txt', fixture.prefix() + fixture.ending(14, 25, 40, 'The Maven: Synthetic second branch.'))

        for index, sources in enumerate(((first, second, first), (second, first))):
            public = self.report('branched-' + str(index), sources)

            self.assertEqual(self.data(public, 'daily_playtime_without_afk')['seconds'], 46)

            heatmap = self.data(public, 'playtime_heatmap')

            self.assertEqual(self.panel(heatmap, reduced = True)['seconds'], 46)
            self.assertEqual(self.panel(heatmap, 'maps', True)['seconds'], 21)
            self.assertEqual(self.data(public, 'weekly_pace')['panels'][0]['rows'][0]['remaining_seconds'], 46)

        independent = self.source('independent.txt', first.read_text().replace('ID = 1', 'ID = 9'))

        public = self.report('independent', (first, independent))

        self.assertEqual(self.data(public, 'daily_playtime_without_afk')['seconds'], 40)
        self.assertEqual(self.panel(self.data(public, 'playtime_heatmap'), reduced = True)['seconds'], 40)

    def test_overlapping_afk_parts_complement_empty_input_and_cancellation(self):
        interval = {'started_at': '2026-09-01T00:00:00+00:00', 'ended_at': '2026-09-01T00:01:00+00:00',
                    'seconds': 60, 'afk_intervals': [
                        {'entered_at': '2026-08-31T23:59:00+00:00', 'ended_at': '2026-09-01T00:00:20+00:00'},
                        {'entered_at': '2026-09-01T00:00:10+00:00', 'ended_at': '2026-09-01T00:00:30+00:00'},
                        {'entered_at': '2026-09-01T00:00:40+00:00', 'ended_at': '2026-09-01T00:02:00+00:00'}]}

        self.assertEqual(AfkMeasurements.summary([interval], ExecutionContext())['remaining_seconds'], 10)

        empty = DailyPlaytimeBuilder.build({'intervals': []}, 'UTC')

        self.assertEqual(DailyPlaytimeBuilder.build({'intervals': []}, 'UTC', reference = empty)['days'], [])

        with patch.object(ExecutionContext, 'check', side_effect = GenerationCancelled):
            with self.assertRaises(GenerationCancelled):
                AfkMeasurements.without([interval], ExecutionContext())
