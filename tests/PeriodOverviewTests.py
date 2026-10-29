import json
import unittest
import MapPaceTests
import MapRunDetailsTests
import SharedHistoryTests

from copy import deepcopy
from datetime import date
from itertools import permutations

from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import patch

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.stages.composition.PeriodOverviewBuilder import PeriodOverviewBuilder


class PeriodOverviewTests(unittest.TestCase):
    """The overview preserves measurements, period, links, and source-projection limitations."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def source(self, text, name = 'synthetic.txt'):
        path = self.root / name
        path.write_text(text)

        return path

    def report(self, name, sources, **options):
        return ReportGenerator().generate(ReportRequest(tuple(sources), self.root / name, **options)).report_path.parent

    @staticmethod
    def data(public, name = 'period_overview'):
        return json.loads((public.parent / 'project/data' / (name + '.json')).read_text())

    @staticmethod
    def highlight(model, code):
        return next(item for item in model['highlights'] if item['code'] == code)

    def test_ru_en_totals_ranks_links_duplicate_sources_and_pdf(self):
        source = self.source(MapRunDetailsTests.MapRunDetailsTests.fixture())
        before = source.read_bytes()

        for language in ('ru', 'en'):
            public = self.report(language, (source, source), report_language = language, generate_pdf = True)
            model = self.data(public)
            afk = self.data(public, 'afk')['summary']

            self.assertEqual((model['seconds'], model['afk_seconds']), (6200, 190))
            self.assertEqual(sum(row['seconds'] for row in model['categories']), model['seconds'])
            self.assertEqual([row['seconds'] for row in model['categories']], [row['seconds'] for row in afk['categories']])
            self.assertEqual((model['popular'][0]['count'], model['popular'][0]['visits']), (7, 8))
            self.assertEqual(model['outliers']['all']['count'], 2)
            self.assertEqual(model['outliers']['without_afk']['count'], 1)
            self.assertEqual(self.highlight(model, 'day_new')['row']['new'], 4)
            self.assertEqual(self.highlight(model, 'day_new')['row']['label'], '2026-09-01')
            self.assertEqual(self.highlight(model, 'session_new')['row']['new'], 7)
            self.assertEqual(self.highlight(model, 'day_loading_share')['row']['loading_seconds'], '5.5')
            self.assertFalse(model['comparison']['enabled'])

            for route in ('index.html', 'playtime/index.html'):
                html = (public / route).read_text()

                self.assertIn('id="period-overview"', html)
                self.assertIn('Synthetic &lt;Dunes &amp; Hills&gt;', html)
                self.assertIn(model['outliers']['all']['rows'][0]['href'], html)
                self.assertIn(model['popular'][0]['href'], html)
                self.assertLess(html.index('id="period-overview"'), html.index('class="playtime"'))

            self.assertTrue((public / 'report.pdf').exists())

        self.assertEqual(source.read_bytes(), before)

    def test_comparison_gaps_match_independent_exports_and_keep_zero_unknown(self):
        source = self.source(MapPaceTests.MapPaceTests.fixture())
        a, b = ReportPeriod(date(2026, 9, 1), date(2026, 9, 1)), ReportPeriod(date(2026, 9, 2), date(2026, 9, 2))

        public = self.report('current', (source,), period = b, comparison_period = a)
        model = self.data(public)
        comparison = model['comparison']

        self.assertTrue(comparison['enabled'])
        self.assertEqual(comparison['gaps']['b']['seconds'], 64)

        gap = next(row for row in comparison['rows'] if row['code'] == 'gap_mean')

        self.assertEqual((gap['a'], gap['b'], gap['delta'], gap['change_percent']), (None, 32, None, None))
        self.assertEqual(gap['delta_text'], '—')

        source.unlink()

        baseline = self.report('baseline', (self.root / 'current/analysis',), mode = ReportMode.EXPORT, period = a)
        gaps = self.data(baseline, 'map_pace')['gaps']

        for key in ('seconds', 'count', 'excluded_pairs', 'unassigned_visits'):
            self.assertEqual(comparison['gaps']['a'][key], gaps[key])

        current_metrics = self.data(public, 'period_comparison')['sections'][0]['rows']

        for row in comparison['rows'][:-1]:
            self.assertEqual(row, next(metric for metric in current_metrics if metric['code'] == row['code']))

        html = (public / 'index.html').read_text()

        self.assertIn('id="overview-comparison"', html)
        self.assertTrue(self.highlight(model, 'session_seconds')['row']['flags'])

    def test_shared_branches_keep_distribution_and_flags_in_every_order(self):
        fixture = SharedHistoryTests.SharedHistoryTests
        sources = (self.source(fixture.prefix() + fixture.ending(12, 20, 30, 'Oshabi: Synthetic.'), 'a.txt'),
                   self.source(fixture.prefix() + fixture.ending(14, 25, 40, 'The Maven: Synthetic.'), 'b.txt'),
                   self.source(fixture.prefix(), 'short.txt'))
        totals = []

        for index, order in enumerate(permutations(sources)):
            public = self.report('fork-' + str(index), order)
            model = self.data(public)
            totals.append([row['seconds'] for row in model['categories']])

            self.assertEqual(sum(totals[-1]), model['seconds'])
            self.assertEqual(model['popular'][0]['count'], 1)
            self.assertEqual(model['outliers']['all']['excluded'], 1)
            self.assertIn('branched', self.highlight(model, 'session_seconds')['row']['flags'])

        self.assertTrue(all(total == totals[0] for total in totals))

    def test_independent_equal_clocks_do_not_merge_sessions(self):
        first = self.source(MapPaceTests.MapPaceTests.fixture(), 'first.txt')
        second = self.source(MapPaceTests.MapPaceTests.fixture().replace('Client 1', 'Client 2'), 'second.txt')
        model = self.data(self.report('independent', (first, second)))

        self.assertEqual(model['seconds'], 480)
        self.assertEqual(self.highlight(model, 'session_seconds')['row']['seconds'], 240)
        self.assertEqual(self.highlight(model, 'session_seconds')['ties'], 1)
        self.assertEqual(self.highlight(model, 'day_new')['row']['new'], 2)

    def test_empty_period_unknown_duration_and_empty_input(self):
        source = self.source(MapPaceTests.MapPaceTests.fixture())
        period = ReportPeriod(date(2026, 10, 1), date(2026, 10, 1))
        empty = self.data(self.report('period-empty', (source,), period = period))

        self.assertEqual((empty['seconds'], empty['popular']), (0, []))
        self.assertIsNone(empty['afk_share'])
        self.assertTrue(all(item['row'] is None for item in empty['highlights']))

        line = MapPaceTests.MapPaceTests.line
        unknown = self.source(''.join(line(0, message) for message in (
            'Generating level 80 area "MapWorldsDunes" with seed 1', ': You have entered Dunes.')), 'unknown.txt')
        model = self.data(self.report('unknown', (unknown,)))

        self.assertTrue(model['popular'][0]['incomplete_visits'])
        self.assertEqual(model['popular'][0]['duration'], '—')
        self.assertIsNone(self.highlight(model, 'day_seconds')['row'])

        model = self.data(self.report('empty', (self.source('', 'empty.txt'),)))

        self.assertFalse(model['popular'])

    def test_decimal_ratios_ties_dates_and_zero_denominator(self):
        cls = PeriodOverviewBuilder
        early = cls.candidate('1', '30.09.2026', 'first', 1, 1, '0.3', [], 1.0)
        later = cls.candidate('2', '01.10.2026', 'second', 1, 1, '0.30', [], 2.0)
        unknown = cls.candidate('3', 'unknown', 'third', 0, 0, '0.5', [], 3.0)
        before = deepcopy([later, early, unknown])
        result = cls.winner(before, 'loading_share')

        self.assertEqual((result['row']['id'], result['row']['loading_share'], result['ties']), ('1', 30, 1))
        self.assertIsNone(unknown['loading_share'])
        self.assertEqual(before, [later, early, unknown])
        self.assertIsNone(cls.winner([unknown], 'seconds')['row'])

    def test_projection_preserves_input_views_and_cancellation(self):
        public = self.report('original', (self.source(MapPaceTests.MapPaceTests.fixture()),))
        names = ('afk', 'sessions', 'map_pace', 'day_overview', 'statistics_summary', 'area_details',
                 'map_outliers', 'map_run_details', 'period_comparison', 'report_period')
        views = {name: self.data(public, name) for name in names}
        activity = self.data(public, 'activity')
        before = deepcopy(views)

        PeriodOverviewBuilder.build(views, activity, ExecutionContext())

        self.assertEqual(views, before)

        with patch.object(ExecutionContext, 'check', side_effect = GenerationCancelled):
            with self.assertRaises(GenerationCancelled):
                PeriodOverviewBuilder.build(views, activity, ExecutionContext())

    def test_cancelled_overview_keeps_current_report_and_removes_work(self):
        source = self.source(MapPaceTests.MapPaceTests.fixture())
        request = ReportRequest((source,), self.root / 'report', replace_report = True)

        ReportGenerator().generate(request)
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}

        with patch.object(PeriodOverviewBuilder, 'build', side_effect = GenerationCancelled):
            with self.assertRaises(GenerationCancelled):
                ReportGenerator().generate(request)

        self.assertEqual(before, {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()})
