import hashlib
import json
import unittest
import AdditionalAnalyticsTests
import MapPaceTests

from datetime import date

from itertools import permutations

from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import patch

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.stages.composition.analytics.MarkerIntervalsBuilder import MarkerIntervalsBuilder


class SevenAnalyticsTests(unittest.TestCase):
    """Seven projections, source evidence, and verifiable pages in both languages."""

    VIEWS = ('map_cycles', 'window_focus', 'remaining_monsters', 'return_profile',
             'session_edges', 'action_obstacles', 'marker_intervals')
    PAGES = ('cycles', 'focus', 'remaining', 'returns', 'session_edges', 'obstacles', 'marker_intervals')

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @classmethod
    def fixture(cls):
        events = [line for line in AdditionalAnalyticsTests.AdditionalAnalyticsTests.fixture().splitlines(keepends = True) if line.strip()]

        for second, message in ((20, '[WINDOW] Lost focus'), (30, '[WINDOW] Lost focus'), (70, '[WINDOW] Gained focus'),
                                (45, ': 20 monsters remain.'), (120, ': 0 monsters remain.'), (350, ': 1 monster remains.'),
                                (185, ': 7 monsters remain.'), (170, ': Not enough room for item.'),
                                (175, ': Not enough room for item.'), (176, ': Failed to use item: Item is unusable.'),
                                (177, ': Failed to use item: Item is unusable.'), (86650, '[WINDOW] Lost focus')):
            events.append(MapPaceTests.MapPaceTests.line(second, message, '2026-09-01T00:00:00'))

        return '\n' * 500 + ''.join(sorted(events, key = lambda line: line[:19]))

    def source(self, text = None, name = 'synthetic.txt'):
        path = self.root / name
        path.write_text(self.fixture() if text is None else text, encoding = 'utf-8')

        return path

    def report(self, name, sources, **options):
        return ReportGenerator().generate(ReportRequest(tuple(sources), self.root / name, **options)).report_path.parent

    @staticmethod
    def data(public, name):
        return json.loads((public.parent / 'project/data' / (name + '.json')).read_text(encoding = 'utf-8'))

    def test_all_seven_copy_dedup_ru_en_and_export_without_source(self):
        source = self.source()
        digest = hashlib.sha256(source.read_bytes()).hexdigest()

        public = self.report('ru', (source, source), report_language = 'ru', generate_pdf = True)
        models = {name: self.data(public, name) for name in self.VIEWS}
        cycle = models['map_cycles']['rows'][0]

        self.assertEqual((cycle['seconds'], cycle['map_seconds'], cycle['outside_seconds'], cycle['unallocated_seconds']), (300, 120, 174, 6))
        self.assertEqual(cycle['remaining_seconds'], 270)

        focus = models['window_focus']

        self.assertEqual((focus['signals']['Lost'], focus['signals']['Gained'], focus['elapsed_seconds']), (3, 1, 50))
        self.assertEqual((focus['balance']['seconds'], focus['balance']['afk_seconds']), (50, 20))
        self.assertEqual(models['remaining_monsters']['observed_count'], 2)
        self.assertEqual(models['remaining_monsters']['unobserved_count'], 11)
        self.assertEqual([row['count'] for row in models['remaining_monsters']['bins']], [1, 1, 0, 0])
        self.assertEqual(len(models['remaining_monsters']['unassigned']), 1)
        self.assertEqual(models['return_profile']['returned_count'], 1)
        self.assertEqual(models['return_profile']['returned']['seconds'], 60)
        self.assertEqual(models['return_profile']['episodes'][0]['span']['seconds'], 42)
        self.assertEqual(models['session_edges']['no_map_sessions'], 1)
        self.assertEqual(models['action_obstacles']['count'], 4)
        self.assertEqual([row['count'] for row in models['action_obstacles']['groups']], [2, 2])
        self.assertEqual(len(models['action_obstacles']['gaps']), 1)

        marker = next(row for row in models['marker_intervals']['groups'] if row['code'] == 'blight')

        self.assertEqual((len(marker['intervals']), marker['median_maps'], marker['longest_observed']), (4, 0, 7))
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), digest)

        manifest = json.loads((public.parent / 'report-manifest.json').read_text())

        self.assertEqual(manifest['report_schema_version'], '39')

        for name in self.VIEWS:
            self.assertIn(name, manifest['views_sha256'])

        source.unlink()

        exported = self.report('en', (self.root / 'ru/analysis',), mode = ReportMode.EXPORT, report_language = 'en')

        for result in (public, exported):
            for page in self.PAGES:
                html = (result / f'analytics/{page}/index.html').read_text()

                self.assertIn('analytics-navigation', html)
                self.assertNotIn('None', html)
                self.assertIn('events/page-2.html#line-' if page in ('focus', 'remaining', 'obstacles', 'session_edges') else 'maps/runs/', html)

            self.assertIn('Synthetic &lt;Dunes &amp; Hills&gt;', (result / 'analytics/remaining/index.html').read_text())

        self.assertEqual(len(self.data(exported, 'analytics_navigation')['pages']), 29)
        self.assertTrue((public / 'report.pdf').is_file())

    def test_source_branches_and_short_copy_in_all_orders(self):
        line = MapPaceTests.MapPaceTests.line
        prefix = '\n' * 500 + ''.join(line(second, message, '2026-09-01T00:00:00') for second, message in (
            (0, 'Client-Safe Instance ID = 1'), (0, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
            (0, ': You have entered Synthetic Map.'), (10, '[WINDOW] Lost focus'),
            (15, 'Sister Cassia: Synthetic marker.'), (20, ': 10 monsters remain.'), (25, ': Not enough room for item.')))
        sources = [self.source(prefix, 'short.txt')]

        for value in (40, 70):
            suffix = ''.join(line(second, message, '2026-09-01T00:00:00') for second, message in (
                (value, '[WINDOW] Gained focus'), (value + 1, ': Not enough room for item.'),
                (value + 10, ': 0 monsters remain.'), (value + 20, 'Closing game gracefully')))
            sources.append(self.source(prefix + suffix, f'branch-{value}.txt'))

        for number, ordered in enumerate(permutations(sources)):
            result = self.report('branches-' + str(number), ordered)

            self.assertEqual(self.data(result, 'window_focus')['ambiguous'], 1)
            self.assertEqual(self.data(result, 'window_focus')['elapsed_seconds'], 0)
            self.assertEqual(self.data(result, 'remaining_monsters')['ambiguous_count'], 1)

            groups = self.data(result, 'action_obstacles')['groups']

            self.assertEqual((len(groups), groups[0]['count'], groups[0]['branched']), (1, 3, True))
            self.assertEqual(self.data(result, 'session_edges')['branched_sessions'], 1)
            self.assertEqual(self.data(result, 'map_cycles')['rows'], [])

    def test_independent_equal_timestamps_do_not_create_links(self):
        source = self.source()
        other = self.source(self.fixture().replace('Synthetic <Dunes & Hills>', 'Synthetic Independent'), 'independent.txt')

        result = self.report('independent', (source, other))

        self.assertEqual(self.data(result, 'window_focus')['elapsed_seconds'], 100)
        self.assertEqual(self.data(result, 'remaining_monsters')['observed_count'], 4)
        self.assertEqual(self.data(result, 'return_profile')['returned_count'], 2)
        self.assertEqual(self.data(result, 'action_obstacles')['count'], 8)

    def test_period_preserves_context_and_empty_period_is_valid(self):
        line = MapPaceTests.MapPaceTests.line
        source = self.source('\n' * 500 + ''.join(line(second, message, '2026-09-01T23:50:00') for second, message in (
            (0, 'Client-Safe Instance ID = 1'), (0, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
            (0, ': You have entered Synthetic Map.'), (60, 'Generating level 1 area "HideoutOssuary" with seed 9'),
            (62, ': You have entered Synthetic Hideout.'), (300, '[WINDOW] Lost focus'), (900, '[WINDOW] Gained focus'),
            (1200, 'Client-Safe Instance ID = 2'), (1200, 'Generating level 80 area "MapWorldsDunes" with seed 2'),
            (1200, ': You have entered Synthetic Map.'), (1260, 'Closing game gracefully'))))

        result = self.report('period', (source,), period = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2)))
        cycle = self.data(result, 'map_cycles')['rows'][0]

        self.assertEqual((cycle['seconds'], cycle['excluded']), (600, ['clipped']))

        focus = self.data(result, 'window_focus')

        self.assertEqual((focus['signals']['Lost'], focus['signals']['Gained'], focus['elapsed_seconds']), (0, 1, 300))
        self.assertEqual(focus['elapsed_summary']['complete'], 0)

        empty = self.report('empty', (source,), period = ReportPeriod(date(2027, 1, 1), date(2027, 1, 1)))

        self.assertEqual(self.data(empty, 'remaining_monsters')['map_count'], 0)
        self.assertEqual(self.data(empty, 'window_focus')['rows'], [])
        self.assertEqual(self.data(empty, 'session_edges')['rows'], [])

    def test_cancellation_preserves_current_report_and_cleans_workspace(self):
        source = self.source()
        request = ReportRequest((source,), self.root / 'report', replace_report = True)

        result = ReportGenerator().generate(request)
        entry = (self.root / 'index.html').read_bytes()
        before = (result.report_path.parent / 'analytics/remaining/index.html').read_bytes()

        with patch.object(MarkerIntervalsBuilder, 'build', side_effect = GenerationCancelled):
            with self.assertRaises(GenerationCancelled):
                ReportGenerator().generate(request)

        self.assertEqual((self.root / 'index.html').read_bytes(), entry)
        self.assertEqual((result.report_path.parent / 'analytics/remaining/index.html').read_bytes(), before)
        self.assertFalse((self.root / 'build').exists())
