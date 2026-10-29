import itertools
import json
import unittest
import LoadingStatisticsTests

from copy import deepcopy
from datetime import date, datetime, timedelta
from decimal import Decimal

from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import patch

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.stages.composition.LoadingRouteStatisticsBuilder import LoadingRouteStatisticsBuilder
from poe_log_analyze.stages.composition.LoadingStatisticsBuilder import LoadingStatisticsBuilder
from poe_log_analyze.stages.reconstruction.LoadingRouteTracker import LoadingRouteTracker
from poe_log_analyze.stages.reconstruction.MapActivityBuilder import MapActivityBuilder


class LoadingRouteTests(unittest.TestCase):
    """Establish direction before merging; obtain duration only from the loading record."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @staticmethod
    def fixture():
        events = ((0, ': You have entered Synthetic <Hideout & Hub>.'),
            (1, '[LOADING SCREEN] (Synthetic <Hideout & Hub>) Duration = 0.1 seconds'),
            (10, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
            (11, ': You have entered Synthetic Dunes.'),
            (12, '[LOADING SCREEN] (Synthetic Dunes) Duration = 1.25 seconds'),
            (20, 'Generating level 1 area "HideoutOssuary" with seed 99'),
            (21, ': You have entered Synthetic <Hideout & Hub>.'),
            (22, '[LOADING SCREEN] (Synthetic <Hideout & Hub>) Duration = 0.75 seconds'),
            (70, 'Generating level 80 area "MapWorldsDunes" with seed 2'),
            (71, ': You have entered Synthetic Dunes.'),
            (72, '[LOADING SCREEN] (Synthetic Dunes) Duration = 2.5 seconds'),
            (73, '[LOADING SCREEN] (Synthetic Dunes) Duration = 0.5 seconds'),
            (80, 'Generating level 1 area "HideoutOssuary" with seed 99'),
            (81, ': You have entered Synthetic <Hideout & Hub>.'),
            (82, '[LOADING SCREEN] (Synthetic <Hideout & Hub>) Duration = 1 seconds'),
            (100, 'Closing game gracefully'),
            (110, '[LOADING SCREEN] (Synthetic <Hideout & Hub>) Duration = 9 seconds'))
        return '\n' * 500 + ''.join(LoadingStatisticsTests.LoadingStatisticsTests.line(second, message)
                                    for second, message in events)

    @staticmethod
    def event(line, second, kind, fields = None):
        moment = datetime(2026, 9, 1) + timedelta(seconds = second) if second is not None else None
        return {'line_number': line, 'record_id': line, 'status': 'recognized', 'type': kind,
                'timestamp': moment.isoformat() + '+00:00' if moment else None, 'fields': fields or {}}

    @staticmethod
    def tracker():
        return LoadingRouteTracker(set(MapActivityBuilder.BOUNDARIES), 1800, ExecutionContext())

    def source(self, text, name = 'synthetic.txt'):
        path = self.root / name
        path.write_text(text)

        return path

    def report(self, name, inputs, **options):
        return ReportGenerator().generate(ReportRequest(tuple(inputs), self.root / name, **options)).report_path.parent

    @staticmethod
    def data(public, name = 'loading_routes'):
        return json.loads((public.parent / 'project/data' / (name + '.json')).read_text())

    def test_direction_single_use_resets_and_unmatched_records(self):
        tracker = self.tracker()
        rows = [self.event(1, 0, 'area.enter', {'area': 'A'}),
                self.event(2, 1, 'area.generate'), self.event(3, 2, 'area.enter', {'area': 'B'}),
                self.event(4, 3, 'loading.duration', {'area': 'B', 'seconds': '1.2'}),
                self.event(5, 3, 'loading.duration', {'area': 'B', 'seconds': '0'}),
                self.event(6, 4, 'area.enter', {'area': 'C'}),
                self.event(7, 5, 'loading.duration', {'area': 'D', 'seconds': '2'}),
                self.event(8, 6, 'area.enter', {'area': 'E'}),
                self.event(9, 10, 'loading.duration', {'area': 'E', 'seconds': '1'})]
        before = deepcopy(rows)

        for row in rows:
            tracker.add(row)

        self.assertEqual(rows, before)
        self.assertEqual(tracker.rows[0], {'line': 4, 'from_area': 'A', 'from_line': 1,
                                         'to_area': 'B', 'to_line': 3, 'reason': 'matched'})
        self.assertEqual([row['reason'] for row in tracker.rows], ['matched', 'no_entry', 'different_area', 'outside_loading'])
        self.assertTrue(all(row['from_area'] is None for row in tracker.rows[1:]))

    def test_boundaries_gap_clock_missing_time_and_new_generation(self):
        for boundary in MapActivityBuilder.BOUNDARIES:
            tracker = self.tracker()
            tracker.add(self.event(1, 0, 'area.enter', {'area': 'A'}))
            tracker.add(self.event(2, 1, boundary))
            tracker.add(self.event(3, 2, 'area.enter', {'area': 'B'}))
            tracker.add(self.event(4, 2, 'loading.duration', {'area': 'B', 'seconds': '0'}))

            self.assertEqual(tracker.rows[0]['reason'], 'unknown_source')

        for second in (-1, 1801, None):
            tracker = self.tracker()
            tracker.add(self.event(1, 0, 'area.enter', {'area': 'A'}))
            tracker.add(self.event(2, second, 'area.enter', {'area': 'B'}))
            tracker.add(self.event(3, second, 'loading.duration', {'area': 'B', 'seconds': '0'}))

            self.assertIsNone(tracker.rows[0]['from_area'])

        tracker = self.tracker()
        tracker.add(self.event(1, 0, 'area.enter', {'area': 'A'}))
        tracker.add(self.event(2, 1, 'area.generate'))
        tracker.add(self.event(3, 1, 'loading.duration', {'area': 'A', 'seconds': '1'}))

        self.assertEqual(tracker.rows[0]['reason'], 'no_entry')

    def test_percentile_nearest_rank_precision_zero_and_undated(self):
        calculator = LoadingStatisticsBuilder(ReportPeriod(), 'UTC', ExecutionContext())
        rows = [{'seconds': str(i)} for i in range(1, 21)]
        stats = LoadingRouteStatisticsBuilder.statistics(rows, calculator)

        self.assertEqual((stats['p95_seconds'], stats['median_seconds'], stats['small_sample']), ('19', '10.5', False))
        self.assertIsNone(LoadingRouteStatisticsBuilder.statistics([], calculator)['p95_seconds'])
        self.assertEqual(LoadingRouteStatisticsBuilder.statistics([{'seconds': '0'}], calculator)['p95_seconds'], '0')

        calculator.add(LoadingStatisticsTests.LoadingStatisticsTests.record(1, '0.00004', None, 'A '))
        calculator.add(LoadingStatisticsTests.LoadingStatisticsTests.record(2, '0', None, 'A'))

        model = LoadingRouteStatisticsBuilder.build(calculator.result(), [], ExecutionContext())

        self.assertEqual((model['count'], model['known'], model['unknown']), (2, 0, 2))
        self.assertEqual(len(model['routes']), 2)
        self.assertEqual(model['routes'][0]['p95'], '0.00004')
        self.assertEqual(model['routes'][0]['chart']['bars'], [])
        self.assertEqual(LoadingRouteStatisticsBuilder.chart([])['bars'], [])

    def test_offset_change_continuation_and_calendar_gaps(self):
        tracker = self.tracker()
        first = self.event(1, 0, 'area.enter', {'area': 'A'})
        second = self.event(2, 1, 'area.enter', {'area': 'B'})
        loading = self.event(3, 2, 'loading.duration', {'area': 'B', 'seconds': '0.25'})
        first['timestamp'] = '2026-10-25T02:59:59+02:00'
        second['timestamp'] = '2026-10-25T02:00:00+01:00'
        loading['timestamp'] = '2026-10-25T02:00:00.250000+01:00'

        for row in (first, second, loading, {**loading, 'line_number': 4}):
            tracker.add(row)

        self.assertEqual(len(tracker.rows), 1)
        self.assertEqual(tracker.rows[0]['from_area'], 'A')

        chart = LoadingRouteStatisticsBuilder.chart([
            {'date': day, 'p95_seconds': '0', 'median_seconds': '0'}
            for day in ('2026-09-01', '2026-09-02', '2026-10-01')])

        self.assertEqual(len(chart['bars']), 3)

        one, two, three = (row['x'] for row in chart['bars'])

        self.assertAlmostEqual((three - two) / (two - one), 29)
        self.assertTrue(all(row['median_height'] == row['p95_height'] == 0 for row in chart['bars']))

    def test_ru_en_report_totals_copy_deduplication_links_and_pdf(self):
        source = self.source(self.fixture())
        original = source.read_bytes()

        for language in ('ru', 'en'):
            public = self.report(language, (source, source), report_language = language, generate_pdf = True)
            model = self.data(public)
            loading = self.data(public, 'loading')

            self.assertEqual((model['count'], model['known'], model['unknown']), (7, 3, 4))
            self.assertEqual(sum(Decimal(route['total_seconds']) for route in model['routes']), Decimal('15.1'))
            self.assertEqual(loading['summary']['total_seconds'], '15.10')

            route = next(row for row in model['routes'] if row['from_area'] == 'Synthetic <Hideout & Hub>')

            self.assertEqual((route['count'], route['median_seconds'], route['p95_seconds']), (2, '1.875', '2.5'))
            self.assertEqual([day['date'] for day in route['days']], ['2026-09-01', '2026-09-02'])
            self.assertTrue(all(row['from_href'].startswith('events/page-2.html#') for row in route['rows']))

            html = (public / 'loading/index.html').read_text()

            self.assertIn('Synthetic &lt;Hideout &amp; Hub&gt;', html)
            self.assertNotIn('Synthetic <Hideout', html)
            self.assertIn('id="' + route['anchor'] + '"', html)
            self.assertIn('loading_routes', json.loads((public.parent / 'report-manifest.json').read_text())['views_sha256'])
            self.assertTrue((public / 'report.pdf').exists())

        self.assertEqual(source.read_bytes(), original)

    def test_period_keeps_source_before_midnight_and_export_without_raw_log(self):
        source = self.source(self.fixture())

        public = self.report('full', (source,))
        source.unlink()

        exported = self.report('selected', (public.parents[1] / 'analysis',), mode = ReportMode.EXPORT,
                               period = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2)))
        model = self.data(exported)

        self.assertEqual((model['count'], model['known']), (4, 1))

        route = next(row for row in model['routes'] if row['from_area'] == 'Synthetic <Hideout & Hub>')

        self.assertEqual(route['rows'][0]['from_line'], 507)
        self.assertEqual(route['median_seconds'], '2.5')

    def test_branches_after_common_entry_keep_parent_route_in_all_input_orders(self):
        line = LoadingStatisticsTests.LoadingStatisticsTests.line
        prefix = ''.join(line(t, text) for t, text in ((0, ': You have entered A.'), (10, ': You have entered B.')))
        one = self.source(prefix + line(11, '[LOADING SCREEN] (B) Duration = 1 seconds')
                          + line(12, ': You have entered C.') + line(13, '[LOADING SCREEN] (C) Duration = 1 seconds'), 'one.txt')
        two = self.source(prefix + line(11, '[LOADING SCREEN] (B) Duration = 2 seconds')
                          + line(12, ': You have entered D.') + line(13, '[LOADING SCREEN] (D) Duration = 1 seconds'), 'two.txt')
        short = self.source(prefix, 'short.txt')

        for index, inputs in enumerate(itertools.permutations((one, two, short))):
            model = self.data(self.report('branches-' + str(index), inputs))
            routes = {(row['from_area'], row['to_area']): row for row in model['routes']}

            self.assertEqual(set(routes), {('A', 'B'), ('B', 'C'), ('B', 'D')})
            self.assertEqual((routes[('A', 'B')]['count'], routes[('A', 'B')]['total_seconds']), (2, '3'))
            self.assertEqual((model['known'], model['unknown']), (4, 0))

    def test_independent_equal_clocks_zero_empty_and_cancellation(self):
        source = self.source(self.fixture())
        second = self.source(self.fixture().replace('Synthetic <Hideout & Hub>', 'Independent Hub'), 'second.txt')
        model = self.data(self.report('independent', (source, second)))

        self.assertEqual((model['count'], model['known'], model['unknown']), (14, 6, 8))

        public = self.report('empty', (self.source('', 'empty.txt'),))

        self.assertEqual(self.data(public)['routes'], [])

        with patch.object(ExecutionContext, 'check', side_effect = GenerationCancelled):
            with self.assertRaises(GenerationCancelled):
                self.tracker().add(self.event(1, 0, 'area.enter', {'area': 'A'}))

    def test_cancellation_preserves_report_and_cleans_work(self):
        source = self.source(self.fixture())
        request = ReportRequest((source,), self.root / 'report', replace_report = True)

        ReportGenerator().generate(request)
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}

        with patch.object(LoadingRouteStatisticsBuilder, 'build', side_effect = GenerationCancelled('Синтетическая отмена')):
            with self.assertRaises(GenerationCancelled):
                ReportGenerator().generate(request)

        self.assertEqual(before, {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()})
