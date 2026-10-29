import hashlib
import json
import unittest
import MapPaceTests

from datetime import date

from itertools import permutations

from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import patch

from PatternAnalyticsFixture import PatternAnalyticsFixture

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.stages.composition.analytics.FilterHistoryBuilder import FilterHistoryBuilder


class PatternAnalyticsTests(unittest.TestCase):
    """Complete pages, evidence, copies, alternatives, and report preservation."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def source(self, text = None, name = 'synthetic.txt'):
        path = self.root / name
        path.write_text(PatternAnalyticsFixture.text() if text is None else text, encoding = 'utf-8')

        return path

    def report(self, name, sources, **options):
        return ReportGenerator().generate(ReportRequest(tuple(sources), self.root / name, **options)).report_path.parent

    @staticmethod
    def data(public, name):
        return json.loads((public.parent / 'project/data' / (name + '.json')).read_text())

    def test_all_five_ru_en_pdf_export_without_source_and_duplicates(self):
        source = self.source()
        digest = hashlib.sha256(source.read_bytes()).hexdigest()

        public = self.report('ru', (source, source), report_language = 'ru', generate_pdf = True)
        pool = self.data(public, 'map_pool')

        self.assertEqual((pool['summary']['count'], pool['summary']['unique'], pool['summary']['top1']), (4, 2, 75))
        self.assertEqual([row['count'] for row in pool['streaks']], [2, 1, 1])
        self.assertEqual(len(pool['weeks']), 2)

        order = self.data(public, 'marker_order')

        self.assertEqual([row['seconds'] for row in order['rows']], [1, 1, 2])

        cards = self.data(public, 'acquisition_history')

        self.assertEqual((cards['version'], cards['card_count'], cards['unique_cards'], cards['repeated_cards']), ('2', 3, 2, 1))
        self.assertEqual([row['count'] for row in cards['cards']], [2, 1])

        filters = self.data(public, 'filter_history')

        self.assertEqual((filters['summary']['saved'], filters['summary']['reloaded'], filters['summary']['failed'],
                          filters['summary']['changes'], filters['summary']['same']), (1, 4, 1, 1, 2))

        faults = self.data(public, 'fault_intervals')
        between = [row for row in faults['rows'] if row['category'] == 'client' and not row['calendar_excluded']]

        self.assertTrue(between)

        first = next(row for row in between if row['elapsed_seconds'] == 15)

        self.assertEqual((first['seconds'], first['new_maps']), (15, 1))
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), digest)

        source.unlink()

        exported = self.report('en', (self.root / 'ru/analysis',), mode = ReportMode.EXPORT, report_language = 'en')

        for result in (public, exported):
            manifest = json.loads((result.parent / 'report-manifest.json').read_text())

            self.assertEqual(manifest['report_schema_version'], '39')
            self.assertEqual(len(self.data(result, 'analytics_navigation')['pages']), 29)
            self.assertEqual(len(self.data(result, 'measurement_coverage')['rows']), 28)

            for name in PatternAnalyticsFixture.VIEWS:
                self.assertIn(name, manifest['views_sha256'])

            for page in PatternAnalyticsFixture.PAGES:
                html = (result / f'analytics/{page}/index.html').read_text()

                self.assertNotIn('None', html)
                self.assertIn('events/page-2.html#line-' if page != 'pool' else 'maps/runs/', html)

            self.assertIn('Synthetic &lt;Card &amp; A&gt;', (result / 'analytics/acquisitions/index.html').read_text())

        self.assertTrue((public / 'report.pdf').is_file())

    def test_period_retains_predecessors_clips_faults_and_empty_result(self):
        source = self.source(PatternAnalyticsFixture.text('2026-09-01T23:59:50'))

        public = self.report('period', (source,), timezone = 'UTC', period = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2)))
        filters = self.data(public, 'filter_history')['rows']

        self.assertTrue(any(row['previous'] and row['previous']['date'] == '2026-09-01' for row in filters))
        self.assertEqual(self.data(public, 'acquisition_history')['card_count'], 0)

        faults = self.data(public, 'fault_intervals')['rows']

        self.assertTrue(any(row['clipped'] for row in faults))

        empty = self.report('empty', (source,), period = ReportPeriod(date(2030, 1, 1), date(2030, 1, 1)))

        for name in PatternAnalyticsFixture.VIEWS:
            self.assertEqual(self.data(empty, name)['rows'], [])

    def test_branches_keep_fault_choices_and_source_specific_time_in_all_orders(self):
        line = MapPaceTests.MapPaceTests.line
        prefix = ''.join(line(second, message) for second, message in (
            (0, ': You have entered Synthetic Hideout.'), (1, '[RENDER] Failed to start device')))
        sources = [self.source(prefix, 'short.txt'),
                   self.source(prefix + line(10, '[RENDER] Failed to start device'), 'a.txt'),
                   self.source(prefix + line(20, '[RENDER] Failed to start device'), 'b.txt')]

        for number, order in enumerate(permutations(sources)):
            public = self.report('branch-' + str(number), order)
            rows = self.data(public, 'fault_intervals')['rows']
            ambiguous = next(row for row in rows if row['category'] == 'client' and row['ambiguous'])

            self.assertEqual(sorted(choice['span']['seconds'] for choice in ambiguous['choices']), [9, 19])
            self.assertIn('incomplete', ambiguous['excluded'])

    def test_independent_equal_clocks_and_cancel_preserve_current_report(self):
        a, b = self.source(), self.source('Synthetic independent source\n' + PatternAnalyticsFixture.text(), 'b.txt')

        public = self.report('report', (a, b), replace_report = True)

        self.assertEqual(self.data(public, 'acquisition_history')['card_count'], 6)
        self.assertEqual(self.data(public, 'map_pool')['summary']['count'], 8)

        before = (public / 'analytics/filters/index.html').read_bytes()

        with patch.object(FilterHistoryBuilder, 'build', side_effect = GenerationCancelled):
            with self.assertRaises(GenerationCancelled):
                self.report('report', (a,), replace_report = True)

        self.assertEqual((public / 'analytics/filters/index.html').read_bytes(), before)
