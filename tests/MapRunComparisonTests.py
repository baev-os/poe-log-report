import json
import unittest
import MapOutlierTests
import MapPaceTests
import MapRunDetailsTests
import SessionComparisonTests
import SharedHistoryTests

from copy import deepcopy
from datetime import date, datetime
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

from poe_log_analyze.stages.composition.MapRunComparisonBuilder import MapRunComparisonBuilder


class MapRunComparisonTests(unittest.TestCase):
    """A/B preserves measurements, unknown values, and provenance of prepared cards."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @staticmethod
    def fixture():
        second = SessionComparisonTests.SessionComparisonTests.fixture()[len(MapOutlierTests.MapOutlierTests.fixture()):]
        second = second.replace('level 81 area "MapWorldsDunes"', 'level 81 area "MapWorldsCitySquare"')
        unfinished = ''.join(MapPaceTests.MapPaceTests.line(0, message, '2026-09-04T18:00:00') for message in (
            'Client-Safe Instance ID = 201', 'Generating level 80 area "MapWorldsDunes" with seed 201',
            ': You have entered Synthetic Map.'))

        return MapRunDetailsTests.MapRunDetailsTests.fixture() + second + unfinished

    def source(self, text, name = 'synthetic.txt'):
        path = self.root / name
        path.write_text(text)

        return path

    def report(self, name, sources, **options):
        return ReportGenerator().generate(ReportRequest(tuple(sources), self.root / name, **options)).report_path.parent

    @staticmethod
    def data(public, name = 'map_run_comparison'):
        return json.loads((public.parent / 'project/data' / (name + '.json')).read_text())

    @staticmethod
    def metrics(row):
        return {item['code']: item['value'] for item in row['metrics']}

    def test_ru_en_metrics_evidence_peer_selection_and_pdf(self):
        source = self.source(self.fixture())
        original = source.read_bytes()

        for language in ('ru', 'en'):
            public = self.report(language, (source, source), report_language = language, generate_pdf = True)
            model = self.data(public)

            self.assertEqual(model['version'], '1')
            self.assertEqual(len(model['by_run']), 11)

            run = next(row for row in model['by_run'].values() if self.metrics(row)['returns'])

            self.assertEqual(self.metrics(run), {'map': 240, 'afk': 180, 'remaining': 60, 'visits': 2,
                'returns': 1, 'gaps': 30, 'gap_afk': 10, 'gap_count': 1, 'unknown_gaps': 0,
                'loading_count': 3, 'loading': 5.5, 'deaths': 1, 'issues': 1})

            peer = model['by_run'][run['suggested']]

            self.assertEqual((peer['area_id'], peer['level']), (run['area_id'], run['level']))
            self.assertNotEqual(peer['id'], run['id'])

            groups = {group['code']: group['rows'] for group in run['groups']}

            self.assertEqual(len(groups['mechanics:blight']), 1)
            self.assertEqual(len(groups['death_messages:screen.slain']), 1)
            self.assertTrue(any(code.startswith('issues:') for code in groups))
            self.assertTrue(all('events/page-2.html#line-' in event['href'] for rows in groups.values() for event in rows))
            self.assertAlmostEqual(run['timeline']['min'], -0.2, places = 5)
            self.assertEqual(run['timeline']['max'], 270)

            html = (public / 'maps/compare/index.html').read_text()

            self.assertIn('Synthetic &lt;Dunes &amp; Hills&gt;', html)
            self.assertNotIn('Synthetic <Dunes', html)
            self.assertIn('stability-record-', html)
            self.assertIn('maps/compare/index.html?a=' + run['id'], (public / run['path']).read_text())

            manifest = json.loads((public.parent / 'report-manifest.json').read_text())

            self.assertEqual(manifest['report_schema_version'], '39')
            self.assertIn('map_run_comparison', manifest['views_sha256'])
            self.assertEqual(manifest['pdf']['content_version'], '12')

        self.assertEqual(source.read_bytes(), original)

    def test_unknown_gaps_identity_events_and_inputs_remain_distinct(self):
        public = self.report('source', (self.source(self.fixture()),))
        details = self.data(public, 'map_run_details')
        page = next(page for page in details['pages'] if page['returns'])
        page['unknown_gaps'] = 1
        page['gaps'].append({'known': False})
        page['visits'][1]['level'] = None
        page['visits'][1]['mechanics'].extend(deepcopy(page['visits'][0]['mechanics']))
        page['excluded'].append('branched')
        page['timestamp'] = None
        original = deepcopy(details)

        result = MapRunComparisonBuilder.build(details, ExecutionContext())
        run = result['by_run'][str(page['line'])]

        self.assertIsNone(self.metrics(run)['gaps'])
        self.assertIsNone(self.metrics(run)['gap_afk'])
        self.assertEqual(self.metrics(run)['gap_count'], 1)
        self.assertIsNone(run['level'])
        self.assertIsNone(run['timeline'])
        self.assertIn('branched', run['flags'])
        self.assertEqual(len(next(group for group in run['groups'] if group['code'] == 'mechanics:blight')['rows']), 1)
        self.assertEqual(details, original)

        run['flags'].append('synthetic')
        run['groups'][0]['rows'][0]['time'] = 'synthetic'

        self.assertEqual(details, original)

    def test_period_export_keeps_original_time_origin_and_empty_selection(self):
        source = self.source(MapPaceTests.MapPaceTests.fixture())

        public = self.report('full', (source,))
        source.unlink()
        analysis = public.parents[1] / 'analysis'

        sliced = self.report('sliced', (analysis,), mode = ReportMode.EXPORT,
                             period = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2)))
        model = self.data(sliced)
        run = next(row for row in model['by_run'].values() if self.metrics(row)['returns'])

        self.assertEqual(self.metrics(run)['map'], 28)
        self.assertEqual(self.metrics(run)['gaps'], 32)
        self.assertIn('clipped', run['flags'])
        self.assertEqual(run['timeline']['min'], 0)
        self.assertEqual(run['timeline']['max'], 120)

        area = next(item for item in run['timeline']['tracks'][0]['items'] if item['category'] == 'map')

        self.assertEqual(area['relative_from'], 92)
        self.assertEqual(area['relative_to'], 120)

        empty = self.report('empty', (analysis,), mode = ReportMode.EXPORT,
                            period = ReportPeriod(date(2026, 10, 1), date(2026, 10, 1)))

        self.assertEqual(self.data(empty)['by_run'], {})
        self.assertNotIn('data-run-select=', (empty / 'maps/compare/index.html').read_text())

    def test_copied_prefix_and_forks_in_every_input_order(self):
        fixture = SharedHistoryTests.SharedHistoryTests
        first = self.source(fixture.prefix() + fixture.ending(12, 20, 30, 'Oshabi: Synthetic.'), 'first.txt')
        second = self.source(fixture.prefix() + fixture.ending(14, 25, 40, 'The Maven: Synthetic.'), 'second.txt')
        short = self.source(fixture.prefix(), 'short.txt')

        for index, sources in enumerate(permutations((first, second, short))):
            model = self.data(self.report('fork-' + str(index), sources))

            self.assertEqual(len(model['by_run']), 1)

            run = next(iter(model['by_run'].values()))

            self.assertEqual(self.metrics(run)['map'], 33)
            self.assertIn('branched', run['flags'])
            self.assertIsNone(run['suggested'])
            self.assertEqual(sum(item['seconds'] for item in run['timeline']['tracks'][0]['items']), 33)

    def test_equal_clocks_preserve_independent_context(self):
        first = self.source(self.fixture(), 'first.txt')
        second = self.source(self.fixture().replace('Synthetic <Dunes & Hills>', 'Synthetic Other')
            .replace('Deadlock detected with timeout 1000ms; no running graph', 'Synthetic message'), 'second.txt')
        model = self.data(self.report('independent', (first, second)))

        self.assertEqual(len(model['by_run']), 22)

        runs = [row for row in model['by_run'].values() if self.metrics(row)['returns']]

        self.assertEqual(sorted(self.metrics(row)['issues'] for row in runs), [0, 1])
        self.assertEqual([self.metrics(row)['map'] for row in runs], [240, 240])

    def test_unknown_duration_and_measured_zero(self):
        prefix = ''.join(MapPaceTests.MapPaceTests.line(0, message) for message in (
            'Client-Safe Instance ID = 1', 'Generating level 80 area "MapWorldsDunes" with seed 1', ': You have entered Dunes.'))
        unknown = self.data(self.report('unknown', (self.source(prefix, 'unknown.txt'),)))
        row = next(iter(unknown['by_run'].values()))

        self.assertIsNone(self.metrics(row)['map'])
        self.assertIsNone(self.metrics(row)['remaining'])
        self.assertIn('incomplete', row['flags'])
        self.assertIsNone(row['suggested'])

        zero = self.data(self.report('zero', (self.source(prefix + MapPaceTests.MapPaceTests.line(0,
            'Generating level 1 area "HideoutOssuary" with seed 9'), 'zero.txt'),)))

        self.assertEqual(self.metrics(next(iter(zero['by_run'].values())))['map'], 0)

    def test_dst_negative_loading_and_cancellation(self):
        origin = '2026-10-25T02:59:59+02:00'
        start = datetime.fromisoformat(origin).timestamp() - 1
        end = datetime.fromisoformat('2026-10-25T02:00:01+01:00').timestamp()
        page = {'timestamp': origin, 'timeline': {'start': start, 'end': end, 'height': 200,
                'tracks': [{'items': [{'from': 0, 'to': 1 / 3}, {'from': 1 / 3, 'to': 1}]}]}}
        original = deepcopy(page)
        result = MapRunComparisonBuilder.timeline(page, ExecutionContext())

        self.assertEqual((result['min'], result['max']), (-1, 2))
        self.assertEqual([(item['relative_from'], item['relative_to']) for item in result['tracks'][0]['items']], [(-1, 0), (0, 2)])
        self.assertEqual(page, original)

        with patch.object(ExecutionContext, 'check', side_effect = GenerationCancelled):
            with self.assertRaises(GenerationCancelled):
                MapRunComparisonBuilder.timeline(page, ExecutionContext())

    def test_cancellation_preserves_current_report(self):
        source = self.source(MapPaceTests.MapPaceTests.fixture())
        request = ReportRequest((source,), self.root / 'report', replace_report = True)

        ReportGenerator().generate(request)
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}

        with patch.object(MapRunComparisonBuilder, 'build', side_effect = GenerationCancelled('Синтетическая отмена')):
            with self.assertRaises(GenerationCancelled):
                ReportGenerator().generate(request)

        self.assertEqual(before, {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()})
