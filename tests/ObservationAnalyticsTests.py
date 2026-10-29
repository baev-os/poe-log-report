import hashlib
import json
import unittest
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

from poe_log_analyze.stages.composition.analytics.AreaPresenceBuilder import AreaPresenceBuilder


class ObservationAnalyticsTests(unittest.TestCase):
    """Seven new analytics, source links, and a complete verifiable report."""

    VIEWS = ('network_health', 'passive_history', 'marker_timing', 'area_route_patterns',
             'trade_api', 'level_progress', 'area_presence')
    PAGES = ('network', 'passives', 'marker_timing', 'routes', 'trade_api', 'level_progress', 'presence')

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @classmethod
    def fixture(cls, start = '2026-09-01T00:00:00'):
        messages = (
            (0, 'Client-Safe Instance ID = 1'), (0, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
            (0, ': You have entered Synthetic <Map & One>.'), (1, 'Connect time to instance server was 10ms'),
            (2, 'Connected to synthetic.invalid in 20ms.'), (3, 'Resyncing 0'),
            (4, 'Successfully allocated passive skill id: Synthetic_A, name: Synthetic <Node & A>'),
            (5, 'Successfully unallocated passive skill id: Synthetic_A, name: Synthetic <Node & A>'),
            (6, 'Successfully allocated mastery effect id: 1, mastery: SyntheticMastery, name: Synthetic Mastery'),
            (7, '[Settlers] GoldRespec|PassivesAllocated 5|GoldCost 100'),
            (8, ': SyntheticHero (Ranger) is now level 88'), (9, ': SyntheticVisitor has joined the area.'),
            (10, '[ETrade] Requesting to instance for api type 1, request_id = 1'),
            (11, 'Sister Cassia: Synthetic observation.'), (12, ': SyntheticHero has been slain.'),
            (15, '[ETrade] Response from instance for request_id 1, error = 0, took 0 ms'),
            (18, ': SyntheticVisitor has left the area.'),
            (20, 'Generating level 1 area "HideoutOssuary" with seed 9'), (22, ': You have entered Synthetic Hideout.'),
            (25, 'Connect time to instance server was 30ms'),
            (27, '[ETrade] Requesting to instance for api type 2, request_id = 2'),
            (30, ': SyntheticHero (Ranger) is now level 89'),
            (35, '[ETrade] Requesting to instance for api type 1, request_id = 3'),
            (36, '[ETrade] Response from instance for request_id 3, error = 5, took 200 ms'),
            (40, 'Client-Safe Instance ID = 1'), (40, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
            (42, ': You have entered Synthetic <Map & One>.'), (45, 'Einhar, Beastmaster: Synthetic observation.'),
            (50, ': SyntheticGuest has joined the area.'), (51, ': SyntheticGuest has joined the area.'),
            (60, 'Generating level 1 area "HideoutOssuary" with seed 9'), (62, ': You have entered Synthetic Hideout.'),
            (65, ': SyntheticHero (Ranger) is now level 91'), (70, 'Connect time to instance server was 0ms'),
            (72, '[ETrade] Requesting to instance for api type 2, request_id = 2'),
            (73, '[ETrade] Response from instance for request_id 2, error = 0, took 5 ms'),
            (75, ': SyntheticVisitor has left the area.'),
            (80, 'Client-Safe Instance ID = 2'), (80, 'Generating level 80 area "MapWorldsDunes" with seed 2'),
            (80, ': You have entered Synthetic <Map & Two>.'),
            (85, 'Successfully allocated passive skill id: Synthetic_B, name: Synthetic Node B'),
            (90, 'Closing game gracefully'))
        return '\n' * 500 + ''.join(MapPaceTests.MapPaceTests.line(second, message, start) for second, message in messages)

    def source(self, text = None, name = 'synthetic.txt'):
        path = self.root / name
        path.write_text(self.fixture() if text is None else text, encoding = 'utf-8')

        return path

    def report(self, name, sources, **options):
        return ReportGenerator().generate(ReportRequest(tuple(sources), self.root / name, **options)).report_path.parent

    @staticmethod
    def data(public, name):
        return json.loads((public.parent / 'project/data' / (name + '.json')).read_text())

    def test_all_seven_ru_en_pdf_export_and_deduplicated_proofs(self):
        source = self.source()
        digest = hashlib.sha256(source.read_bytes()).hexdigest()

        public = self.report('ru', (source, source), report_language = 'ru', generate_pdf = True)
        models = {name: self.data(public, name) for name in self.VIEWS}
        network = models['network_health']
        sample = next(row for row in network['summaries'] if row['code'] == 'network.instance_latency')

        self.assertEqual((sample['stats']['count'], sample['stats']['median'], sample['stats']['p95']), (3, 10, 30))
        self.assertEqual((network['sample_count'], network['resync_count']), (4, 1))
        self.assertEqual(models['passive_history']['summary'], {'count': 5, 'allocated': 2, 'unallocated': 1,
                         'delta': 1, 'masteries': 1, 'gold_records': 1})

        markers = {row['code']: row for row in models['marker_timing']['rows']}

        self.assertEqual((markers['blight']['offset_seconds'], markers['blight']['returned']), (11, False))
        self.assertEqual((markers['bestiary']['offset_seconds'], markers['bestiary']['returned']), (45, True))

        routes = models['area_route_patterns']

        self.assertEqual((routes['edge_count'], routes['chain_count'], routes['loop_count'], routes['same_instance_count']), (4, 3, 3, 1))

        api = models['trade_api']

        self.assertEqual((api['request_count'], api['response_count'], api['matched_count'], api['unknown_count']), (4, 3, 2, 2))
        self.assertEqual((api['summary']['min'], api['summary']['median'], api['summary']['p95']), (0, 100, 200))

        levels = models['level_progress']['rows']

        self.assertEqual([row['state'] for row in levels], ['first', 'consecutive', 'gap'])
        self.assertEqual((levels[1]['wall_seconds'], levels[1]['seconds'], len(levels[1]['death_hrefs'])), (22, 22, 1))

        presence = models['area_presence']

        self.assertEqual((presence['joined_count'], presence['left_count'], presence['matched_count'], presence['unknown_count']), (3, 2, 1, 2))
        self.assertEqual(presence['summary']['median_seconds'], 9)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), digest)

        source.unlink()

        exported = self.report('en', (self.root / 'ru/analysis',), mode = ReportMode.EXPORT, report_language = 'en')

        for result in (public, exported):
            manifest = json.loads((result.parent / 'report-manifest.json').read_text())

            self.assertEqual(manifest['report_schema_version'], '39')

            for name in self.VIEWS:
                self.assertIn(name, manifest['views_sha256'])

            for page in self.PAGES:
                html = (result / f'analytics/{page}/index.html').read_text()

                self.assertNotIn('None', html)
                self.assertIn('events/page-2.html#line-', html)

            self.assertIn('Synthetic &lt;Node &amp; A&gt;', (result / 'analytics/passives/index.html').read_text())
            self.assertEqual(len(self.data(result, 'analytics_navigation')['pages']), 29)

        self.assertTrue((public / 'report.pdf').is_file())

    def test_branches_short_copy_and_all_input_orders(self):
        prefix = '\n' * 500 + ''.join(MapPaceTests.MapPaceTests.line(second, message) for second, message in (
            (0, 'Client-Safe Instance ID = 1'), (0, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
            (0, ': You have entered Synthetic Map.'), (1, ': SyntheticHero (Ranger) is now level 88'),
            (2, ': SyntheticVisitor has joined the area.'),
            (3, '[ETrade] Requesting to instance for api type 1, request_id = 1'),
            (4, 'Sister Cassia: Synthetic marker.')))
        sources = [self.source(prefix, 'short.txt')]

        for second in (20, 40):
            text = prefix + ''.join(MapPaceTests.MapPaceTests.line(time, message) for time, message in (
                (second, ': SyntheticVisitor has left the area.'),
                (second + 1, '[ETrade] Response from instance for request_id 1, error = 0, took 10 ms'),
                (second + 2, ': SyntheticHero (Ranger) is now level 89'),
                (second + 3, 'Closing game gracefully')))
            sources.append(self.source(text, f'branch-{second}.txt'))

        for number, ordered in enumerate(permutations(sources)):
            public = self.report('branches-' + str(number), ordered)

            self.assertEqual(self.data(public, 'trade_api')['matched_count'], 0)
            self.assertEqual(self.data(public, 'trade_api')['rows'][0]['state'], 'ambiguous')
            self.assertEqual(self.data(public, 'area_presence')['rows'][0]['state'], 'ambiguous')
            self.assertEqual([row['state'] for row in self.data(public, 'level_progress')['rows']], ['first', 'ambiguous', 'ambiguous'])
            self.assertIsNone(self.data(public, 'marker_timing')['rows'][0]['offset_seconds'])

    def test_independent_equal_clocks_do_not_create_shared_links(self):
        source = self.source()
        other = self.source(self.fixture().replace('Map & One', 'Independent & One'), 'independent.txt')

        public = self.report('independent', (source, other))

        self.assertEqual(self.data(public, 'network_health')['sample_count'], 8)
        self.assertEqual(self.data(public, 'trade_api')['matched_count'], 4)
        self.assertEqual(self.data(public, 'area_presence')['matched_count'], 2)
        self.assertEqual(self.data(public, 'level_progress')['consecutive_count'], 2)

    def test_period_preserves_original_pairs_and_empty_period(self):
        source = self.source(self.fixture('2026-09-01T23:59:30'))

        public = self.report('period', (source,), period = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2)))
        levels = self.data(public, 'level_progress')['rows']

        self.assertEqual(levels[0]['state'], 'consecutive')
        self.assertEqual(levels[0]['wall_seconds'], 22)
        self.assertIsNone(levels[0]['span'])
        self.assertIn('incomplete', levels[0]['excluded'])

        api = self.data(public, 'trade_api')

        self.assertEqual(api['request_count'], 2)
        self.assertEqual(api['matched_count'], 1)

        empty = self.report('empty', (source,), period = ReportPeriod(date(2027, 1, 1), date(2027, 1, 1)))

        for name in self.VIEWS:
            self.assertEqual(self.data(empty, name)['rows'], [])

    def test_cancelled_last_projection_preserves_current_report(self):
        source = self.source()
        request = ReportRequest((source,), self.root / 'report', replace_report = True)

        result = ReportGenerator().generate(request)
        entry, before = (self.root / 'index.html').read_bytes(), (result.report_path.parent / 'analytics/network/index.html').read_bytes()

        with patch.object(AreaPresenceBuilder, 'build', side_effect = GenerationCancelled):
            with self.assertRaises(GenerationCancelled):
                ReportGenerator().generate(request)

        self.assertEqual((self.root / 'index.html').read_bytes(), entry)
        self.assertEqual((result.report_path.parent / 'analytics/network/index.html').read_bytes(), before)
        self.assertFalse((self.root / 'build').exists())
