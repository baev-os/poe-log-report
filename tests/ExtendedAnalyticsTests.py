import hashlib
import json
import unittest
import ObservationCalculationsTests
import MapPaceTests

from copy import deepcopy
from datetime import date

from itertools import permutations

from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import patch

from ExtendedAnalyticsFixture import ExtendedAnalyticsFixture

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.stages.composition.analytics.MemoryHistoryBuilder import MemoryHistoryBuilder
from poe_log_analyze.stages.composition.analytics.StartupHistoryBuilder import StartupHistoryBuilder
from poe_log_analyze.stages.composition.analytics.ClientEnvironmentBuilder import ClientEnvironmentBuilder
from poe_log_analyze.stages.composition.analytics.AcquisitionHistoryBuilder import AcquisitionHistoryBuilder
from poe_log_analyze.stages.composition.analytics.MilestoneHistoryBuilder import MilestoneHistoryBuilder


class ExtendedAnalyticsTests(unittest.TestCase):
    """Six analytics: original units, boundaries, copies, period, and export without raw logs."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def source(self, text = None, name = 'synthetic.txt'):
        path = self.root / name
        path.write_text(ExtendedAnalyticsFixture.text() if text is None else text, encoding = 'utf-8')

        return path

    def report(self, name, sources, **options):
        return ReportGenerator().generate(ReportRequest(tuple(sources), self.root / name, **options)).report_path.parent

    @staticmethod
    def data(public, name):
        return json.loads((public.parent / 'project/data' / (name + '.json')).read_text())

    def test_all_six_ru_en_pdf_export_units_and_source_proofs(self):
        source = self.source()
        digest = hashlib.sha256(source.read_bytes()).hexdigest()

        public = self.report('ru', (source, source), report_language = 'ru', generate_pdf = True)
        models = {name: self.data(public, name) for name in ExtendedAnalyticsFixture.VIEWS}
        memory = models['memory_history']

        self.assertEqual(len(memory['rows']), 3)
        self.assertEqual(memory['rows'][1]['changes']['used'], 128)
        self.assertIsNone(memory['rows'][2]['changes']['used'])

        group = next(row for row in memory['groups'] if row['dimension'] == 'all' and row['field'] == 'used' and row['unit'] == 'MB')

        self.assertEqual((group['stats']['count'], group['stats']['min'], group['stats']['median']), (2, 0, 64))

        startup = models['startup_history']

        self.assertEqual((startup['summary']['complete'], startup['rows'][0]['seconds']), (1, 10))
        self.assertEqual([row['seconds'] for row in startup['slowest']], [10])
        self.assertEqual(next(row for row in startup['stages'] if row['stage'] == 'Game')['stats']['min'], 0)

        environment = models['client_environment']

        self.assertEqual(len(environment['groups']), 4)
        self.assertEqual(sum(row['seconds'] for row in environment['exposure']), 29)
        self.assertAlmostEqual(environment['issues'][0]['per_hour'], 900)

        acquisitions = [row for row in models['acquisition_history']['groups'] if row['dimension'] == 'all']
        artifacts = {row['artifact']: row['quantity'] for row in acquisitions if row['artifact']}

        self.assertEqual(artifacts, {'Greater Black Scythe Artifact': 5, 'Grand Black Scythe Artifact': 3})
        self.assertIsNone(next(row for row in acquisitions if row['code'] == 'screen.bestiary_added')['quantity'])

        milestones = models['milestone_history']['rows']
        clocks = [row['clock_seconds'] for row in milestones if row['clock_seconds'] is not None]

        self.assertEqual(clocks, [3723, 93784])
        self.assertEqual(next(row for row in milestones if row['code'] == 'screen.resistance_reward')['seconds'], 3)

        coverage = models['measurement_coverage']['rows']

        self.assertEqual(len(coverage), 28)
        self.assertEqual(next(row for row in coverage if row['page'] == 'memory')['usable'], 3)
        self.assertEqual(next(row for row in coverage if row['page'] == 'memory')['unknown_context'], 1)
        self.assertIsNone(next(row for row in coverage if row['page'] == 'mechanics')['unknown_context'])
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), digest)

        source.unlink()

        exported = self.report('en', (self.root / 'ru/analysis',), mode = ReportMode.EXPORT, report_language = 'en')

        for result in (public, exported):
            manifest = json.loads((result.parent / 'report-manifest.json').read_text())

            self.assertEqual(manifest['report_schema_version'], '39')
            self.assertEqual(len(self.data(result, 'analytics_navigation')['pages']), 29)

            for name in ExtendedAnalyticsFixture.VIEWS:
                self.assertIn(name, manifest['views_sha256'])

            for page in ExtendedAnalyticsFixture.PAGES:
                html = (result / f'analytics/{page}/index.html').read_text()

                self.assertNotIn('None', html)
                self.assertIn('analytics-navigation', html)

            self.assertIn('Synthetic &lt;Quest &amp; Reward&gt;', (result / 'analytics/milestones/index.html').read_text())

        self.assertTrue((public / 'report.pdf').is_file())

    def test_period_keeps_original_predecessors_and_start_marker(self):
        source = self.source(ExtendedAnalyticsFixture.text('2026-09-01T23:59:50'))
        period = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2))

        public = self.report('period', (source,), timezone = 'UTC', period = period)
        memory = self.data(public, 'memory_history')['rows']

        self.assertEqual(len(memory), 2)
        self.assertEqual(memory[0]['changes']['used'], 128)
        self.assertTrue(memory[0]['previous']['timestamp'].startswith('2026-09-01'))
        self.assertEqual(self.data(public, 'startup_history')['rows'], [])
        self.assertEqual(self.data(public, 'client_environment')['groups'][0]['stats']['count'], 1)

        empty = self.report('empty', (source,), period = ReportPeriod(date(2030, 1, 1), date(2030, 1, 1)))

        for name in ExtendedAnalyticsFixture.VIEWS[:-1]:
            self.assertEqual(self.data(empty, name)['rows'], [])

        self.assertTrue(all(row['count'] == 0 and row['share'] is None
                            for row in self.data(empty, 'measurement_coverage')['rows']))

    def test_source_branches_short_copy_and_input_order_preserve_exposure(self):
        prefix = ''.join(MapPaceTests.MapPaceTests.line(second, message) for second, message in (
            (0, '[ENGINE] Init'), (1, '[ENGINE] Running Engine version 1.2.3'),
            (2, '[ENGINE] Build Revision: 100'), (3, '[RENDER] Starting device: Vulkan'),
            (4, '[RENDER] Driver Version: 1.2.3'), (5, '[MEMORY] Used=1 MB, OsUsed=1 GB, Total=4 GB')))
        sources = [self.source(prefix, 'short.txt'), self.source(prefix + MapPaceTests.MapPaceTests.line(10, ': You have entered Synthetic A.'), 'a.txt'),
                   self.source(prefix + MapPaceTests.MapPaceTests.line(20, ': You have entered Synthetic B.'), 'b.txt')]

        for number, order in enumerate(permutations(sources)):
            public = self.report('branch-' + str(number), order)

            self.assertEqual(len(self.data(public, 'memory_history')['rows']), 1)

            startup = self.data(public, 'startup_history')['rows']

            self.assertEqual((len(startup), startup[0]['state'], len(startup[0]['choices'])), (1, 'ambiguous', 2))
            self.assertEqual(sum(row['seconds'] for row in self.data(public, 'client_environment')['exposure']), 24)

    def test_independent_equal_clocks_keep_both_clients(self):
        a = self.source()
        b = self.source('Synthetic independent prefix\n' + ExtendedAnalyticsFixture.text(), 'b.txt')

        public = self.report('independent', (a, b))

        self.assertEqual(len(self.data(public, 'memory_history')['rows']), 6)
        self.assertEqual(sum(row['seconds'] for row in self.data(public, 'client_environment')['exposure']), 58)

    def test_calculations_do_not_mutate_or_invent_clock_totals(self):
        event = ObservationCalculationsTests.ObservationCalculationsTests.event(3, 'screen.played_time_minutes', minutes = '0', seconds = '0')
        _, spans, index = ObservationCalculationsTests.ObservationCalculationsTests.fixture([event])
        before = deepcopy(index.evidence)

        self.assertEqual(MilestoneHistoryBuilder.build(index, spans)['rows'][0]['clock_seconds'], 0)
        self.assertEqual(before, index.evidence)

        index.selection.control = ExecutionContext(cancelled = lambda: True)

        for builder in (MemoryHistoryBuilder, ClientEnvironmentBuilder, AcquisitionHistoryBuilder):
            with self.assertRaises(GenerationCancelled):
                builder.build(index)

        for builder in (StartupHistoryBuilder, MilestoneHistoryBuilder):
            with self.assertRaises(GenerationCancelled):
                builder.build(index, spans)

    def test_cancelled_generation_preserves_current_report(self):
        source = self.source()

        public = self.report('report', (source,), replace_report = True)
        before = (public / 'analytics/memory/index.html').read_bytes()

        with patch.object(ClientEnvironmentBuilder, 'build', side_effect = GenerationCancelled):
            with self.assertRaises(GenerationCancelled):
                self.report('report', (source,), replace_report = True)

        self.assertEqual((public / 'analytics/memory/index.html').read_bytes(), before)
