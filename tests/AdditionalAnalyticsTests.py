import hashlib
import json
import unittest
import MapObservationAnalyticsTests
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

from poe_log_analyze.stages.composition.MapConsistencyBuilder import MapConsistencyBuilder


class AdditionalAnalyticsTests(unittest.TestCase):
    """All five views, local evidence, and the saved analysis."""

    VIEWS = ('session_rhythm', 'mechanic_combinations', 'trade_activity', 'map_consistency', 'disconnect_returns')
    PAGES = ('rhythm', 'mechanics', 'trading', 'consistency', 'recovery')

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @classmethod
    def fixture(cls):
        lines = MapObservationAnalyticsTests.MapObservationAnalyticsTests.fixture().splitlines(keepends = True)
        events = [line for line in lines if line.strip()]
        events.extend(line.replace('Sister Cassia: Synthetic marker.', 'Oshabi: Synthetic marker.')
                      for line in list(events) if 'Sister Cassia: Synthetic marker.' in line)

        for second, message in ((180, ': Trade accepted.'), (190, '@From SyntheticBuyer: Hi, I would like to buy your Synthetic <Item & Value> listed for 1 synthetic in Synthetic League'),
                                (295, ': Trade accepted.'), (440, ': Trade cancelled.'), (450, ': Trade accepted.'),
                                (86550, 'Abnormal disconnect: An unexpected disconnection occurred.'),
                                (86610, ': You have entered Synthetic Hideout.'), (86700, 'Closing game gracefully')):
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

    def test_all_five_ru_en_duplicate_sources_and_saved_export(self):
        source = self.source()
        digest = hashlib.sha256(source.read_bytes()).hexdigest()

        ru = self.report('ru', (source, source), report_language = 'ru', generate_pdf = True)
        models = {name: self.data(ru, name) for name in self.VIEWS}

        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), digest)
        self.assertEqual(models['mechanic_combinations']['multiple_count'], 5)
        self.assertEqual(models['mechanic_combinations']['pairs'][0]['count'], 5)
        self.assertEqual(models['trade_activity']['summary'],
                         {'accepted': 3, 'cancelled': 1, 'incoming_request': 1, 'outgoing_request': 0})
        self.assertEqual([row['count'] for row in models['trade_activity']['between_exchanges']], [0, 1])
        self.assertEqual(len(models['trade_activity']['gaps']), 2)
        self.assertEqual(models['disconnect_returns']['median_seconds'], 60)
        self.assertEqual(models['disconnect_returns']['count'], 1)
        self.assertEqual(models['map_consistency']['modes']['all']['groups'][0]['summary']['complete'], 1)

        first = next(iter(models['session_rhythm']['by_session'].values()))

        self.assertEqual(sum(row['new'] for session in models['session_rhythm']['by_session'].values() for row in session['bins']), 13)
        self.assertEqual(sum(row['afk_seconds'] for row in first['bins']), 150)

        manifest = json.loads((ru.parent / 'report-manifest.json').read_text())

        for name in self.VIEWS:
            self.assertIn(name, manifest['views_sha256'])

        source.unlink()

        en = self.report('en', (self.root / 'ru/analysis',), mode = ReportMode.EXPORT, report_language = 'en')

        for public in (ru, en):
            for page in self.PAGES:
                html = (public / f'analytics/{page}/index.html').read_text(encoding = 'utf-8')

                self.assertIn('analytics-navigation', html)
                self.assertNotIn('None', html)
                self.assertIn('events/page-2.html#line-' if page in ('trading', 'recovery') else 'maps/runs/', html)

            self.assertIn('Synthetic &lt;Item &amp; Value&gt;', (public / 'analytics/trading/index.html').read_text())
            self.assertIn('<svg', (public / 'analytics/consistency/index.html').read_text())

        self.assertEqual(self.data(en, 'disconnect_returns')['median_seconds'], 60)
        self.assertTrue((ru / 'report.pdf').is_file())

    def test_recovery_branches_short_copy_and_independent_equal_clocks(self):
        prefix = ''.join(MapPaceTests.MapPaceTests.line(second, message, '2026-09-01T00:00:00') for second, message in (
            (0, ': You have entered Synthetic Hideout.'),
            (10, 'Abnormal disconnect: An unexpected disconnection occurred.')))
        short = self.source(prefix, 'short.txt')
        left = self.source(prefix + MapPaceTests.MapPaceTests.line(40, ': You have entered Synthetic Left.', '2026-09-01T00:00:00'), 'left.txt')
        right = self.source(prefix + MapPaceTests.MapPaceTests.line(70, ': You have entered Synthetic Right.', '2026-09-01T00:00:00'), 'right.txt')

        for index, sources in enumerate(permutations((short, left, right))):
            public = self.report('branch-' + str(index), sources)
            result = self.data(public, 'disconnect_returns')

            self.assertEqual((result['count'], result['states']['ambiguous'], result['sample_count']), (1, 1, 0))
            self.assertEqual(sorted(option['seconds'] for option in result['rows'][0]['choices']), [30, 60])

        independent = self.source(left.read_text().replace('Synthetic Hideout', 'Synthetic Independent'), 'independent.txt')
        result = self.data(self.report('independent', (left, independent)), 'disconnect_returns')

        self.assertEqual((result['count'], result['sample_count']), (2, 2))

    def test_period_keeps_original_rhythm_anchor_and_return_context(self):
        source = self.source(''.join(MapPaceTests.MapPaceTests.line(second, message, '2026-09-01T23:00:00') for second, message in (
            (0, ': You have entered Synthetic Hideout.'), (900, 'Sister Cassia: Synthetic heartbeat.'),
            (1800, 'Sister Cassia: Synthetic heartbeat.'), (2700, 'Sister Cassia: Synthetic heartbeat.'),
            (3700, ': Trade accepted.'), (3900, 'Abnormal disconnect: An unexpected disconnection occurred.'),
            (3960, ': You have entered Synthetic Hideout.'), (4000, 'Closing game gracefully'))))

        public = self.report('period', (source,), period = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2)))
        sessions = list(self.data(public, 'session_rhythm')['by_session'].values())

        self.assertTrue(any(row['bins'] and row['bins'][0]['index'] == 2 for row in sessions))
        self.assertEqual(self.data(public, 'trade_activity')['summary']['accepted'], 1)
        self.assertEqual(self.data(public, 'disconnect_returns')['count'], 1)

        empty = self.report('empty', (source,), period = ReportPeriod(date(2027, 1, 1), date(2027, 1, 1)))

        self.assertEqual(self.data(empty, 'session_rhythm')['by_session'], {})
        self.assertEqual(self.data(empty, 'mechanic_combinations')['map_count'], 0)

    def test_cancellation_keeps_previous_report_and_cleans_workspace(self):
        source = self.source()
        request = ReportRequest((source,), self.root / 'report', replace_report = True)

        ReportGenerator().generate(request)
        before = (self.root / 'index.html').read_bytes()
        report = (self.root / 'report/public/analytics/consistency/index.html').read_bytes()

        with patch.object(MapConsistencyBuilder, 'build', side_effect = GenerationCancelled()):
            with self.assertRaises(GenerationCancelled):
                ReportGenerator().generate(request)

        self.assertEqual((self.root / 'index.html').read_bytes(), before)
        self.assertEqual((self.root / 'report/public/analytics/consistency/index.html').read_bytes(), report)
        self.assertFalse((self.root / 'build').exists())
