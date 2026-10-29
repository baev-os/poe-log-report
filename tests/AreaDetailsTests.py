import json
import unittest
import MapPaceTests
import SharedHistoryTests

from copy import deepcopy
from datetime import date, datetime

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

from poe_log_analyze.stages.composition.AreaDetailsBuilder import AreaDetailsBuilder
from poe_log_analyze.stages.composition.DailyAreaStatisticsBuilder import DailyAreaStatisticsBuilder
from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection
from poe_log_analyze.stages.composition.sessions.SessionHistoryBuilder import SessionHistoryBuilder


class AreaDetailsTests(unittest.TestCase):
    """Area cards preserve measurements, context, and exact links."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @classmethod
    def fixture(cls):
        text = MapPaceTests.MapPaceTests.fixture()
        first = MapPaceTests.MapPaceTests.line(0, ': You have entered Dunes.')
        back = MapPaceTests.MapPaceTests.line(92, ': You have entered Dunes.')
        text = text.replace(first, first + MapPaceTests.MapPaceTests.line(5, 'Sister Cassia: Synthetic observation.')
                            + MapPaceTests.MapPaceTests.line(10, ': SyntheticHero has been slain.'))

        return text.replace(back, back + MapPaceTests.MapPaceTests.line(95, 'The Maven: Synthetic observation.')
                            + MapPaceTests.MapPaceTests.line(96, ': SyntheticHero has committed suicide.'))

    def source(self, name, text):
        path = self.root / name
        path.write_text(text)

        return path

    def report(self, name, sources, **options):
        result = ReportGenerator().generate(ReportRequest(tuple(sources), self.root / name, **options))
        return result.report_path.parent

    @staticmethod
    def data(public, name = 'area_details'):
        return json.loads((public.parent / 'project/data' / (name + '.json')).read_text())

    @staticmethod
    def area(model, area_id):
        return next(page for page in model['pages'] if page['area_id'] == area_id)

    def test_maps_and_other_zones_match_statistics_with_returns_and_evidence_ru_en(self):
        source = self.source('synthetic.txt', self.fixture())
        original = source.read_bytes()
        routes = []

        for language in ('ru', 'en'):
            public = self.report(language, (source, source), report_language = language, generate_pdf = True)
            model = self.data(public)

            self.assertEqual(len(model['pages']), 3)

            routes.append([page['path'] for page in model['pages']])
            zones = self.data(public, 'statistics_summary')['zones']

            for zone in zones:
                page = self.area(model, zone['area_id'])

                self.assertEqual((page['count'], page['visits'], page['seconds']),
                                 (zone['count'], zone['visits'], zone['seconds']))
                self.assertEqual(sum(day['seconds'] for day in page['days']), page['seconds'])

            dunes = self.area(model, 'MapWorldsDunes')

            self.assertEqual((dunes['count'], dunes['visits'], dunes['seconds'], dunes['death_count']), (1, 2, 88, 2))
            self.assertEqual((dunes['metrics']['mean_seconds'], dunes['metrics']['median_seconds'], dunes['metrics']['returns']), (88, 88, 1))
            self.assertEqual([day['seconds'] for day in dunes['days']], [60, 28])
            self.assertEqual([row['return'] for day in dunes['days'] for row in day['rows']], [False, True])
            self.assertEqual(len(dunes['chart']['points']), 2)
            self.assertEqual(len({tick['label'] for tick in dunes['chart']['times']}), 5)

            pace = self.data(public, 'map_pace')
            pace_type = next(row for row in pace['types'] if row['area_id'] == 'MapWorldsDunes')

            self.assertEqual(dunes['metrics']['mean_seconds'], pace_type['mean_seconds'])

            html = (public / dunes['path']).read_text()

            self.assertIn('SyntheticHero', html)
            self.assertIn('events/page-2.html#line-', html)
            self.assertIn('sessions/', html)
            self.assertIn('../' + dunes['path'], (public / 'statistics/index.html').read_text())
            self.assertIn('../' + dunes['path'], (public / 'pace/index.html').read_text())

            hideout = self.area(model, 'HideoutOssuary')

            self.assertIn('../' + hideout['path'], (public / 'areas/index.html').read_text())

            city = self.area(model, 'MapWorldsCitySquare')

            self.assertIn('Synthetic &lt;City &amp; Square&gt;', (public / city['path']).read_text())
            self.assertNotIn('Synthetic <City', (public / city['path']).read_text())

            manifest = json.loads((public.parent / 'report-manifest.json').read_text())

            self.assertIn('area_details', manifest['views_sha256'])
            self.assertEqual(manifest['pdf']['content_version'], '12')
            self.assertGreater(len(PdfReader(public / 'report.pdf').pages), 0)

        self.assertEqual(routes[0], routes[1])
        self.assertEqual(source.read_bytes(), original)

    def test_period_export_without_source_and_empty_period(self):
        source = self.source('synthetic.txt', self.fixture())

        public = self.report('full', (source,))
        analysis = public.parents[1] / 'analysis'
        source.unlink()
        period = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2))

        selected = self.report('selected', (analysis,), mode = ReportMode.EXPORT, period = period)
        dunes = self.area(self.data(selected), 'MapWorldsDunes')

        self.assertEqual((dunes['visits'], dunes['seconds'], dunes['metrics']['new'], dunes['metrics']['returns']), (1, 28, 0, 1))
        self.assertEqual(dunes['metrics']['excluded'], 1)
        self.assertIsNone(dunes['metrics']['mean_seconds'])
        self.assertEqual([day['date'] for day in dunes['days']], ['2026-09-02'])

        rows = dunes['days'][0]['rows']

        self.assertEqual([event['code'] for row in rows for event in row['mechanics']], ['maven'])
        self.assertEqual(dunes['death_count'], 1)
        self.assertEqual(dunes['path'], self.area(self.data(public), 'MapWorldsDunes')['path'])

        empty = self.report('empty', (analysis,), mode = ReportMode.EXPORT, period = ReportPeriod(date(2030, 1, 1), None))

        self.assertEqual(self.data(empty)['pages'], [])
        self.assertEqual(self.data(empty)['links'], {})

    def test_branches_keep_known_seconds_and_separate_endings(self):
        first = self.source('first.txt', SharedHistoryTests.SharedHistoryTests.prefix() + SharedHistoryTests.SharedHistoryTests.ending(12, 20, 30, 'Oshabi: Synthetic first branch.'))
        second = self.source('second.txt', SharedHistoryTests.SharedHistoryTests.prefix() + SharedHistoryTests.SharedHistoryTests.ending(14, 25, 40, 'The Maven: Synthetic second branch.'))
        model = self.data(self.report('branches', (first, second)))
        dunes = self.area(model, 'MapWorldsDunes')

        self.assertEqual((dunes['visits'], dunes['seconds'], dunes['metrics']['complete']), (1, 33, 0))

        row = dunes['days'][0]['rows'][0]

        self.assertTrue(row['branched'])
        self.assertIsNone(row['exited_at'])
        self.assertEqual(len(row['branches']), 2)
        self.assertEqual(len(row['mechanics']), 3)
        self.assertTrue(dunes['chart']['points'][0]['partial'])

    def test_independent_equal_times_use_distinct_sessions_and_visits(self):
        first = self.source('first.txt', self.fixture())
        second = self.source('second.txt', self.fixture().replace('seed 1', 'seed 17').replace('ID = 1', 'ID = 17'))
        dunes = self.area(self.data(self.report('independent', (first, second))), 'MapWorldsDunes')
        rows = [row for day in dunes['days'] for row in day['rows']]

        self.assertEqual((dunes['count'], dunes['visits'], dunes['seconds']), (2, 4, 176))
        self.assertEqual(len({row['session_href'] for row in rows}), 2)
        self.assertEqual(len({row['anchor'] for row in rows}), 4)

    @staticmethod
    def run_record(line, area_id, name, start, end, kind = 'area'):
        bounded = start is not None and end is not None
        seconds = datetime.fromisoformat(end).timestamp() - datetime.fromisoformat(start).timestamp() if bounded else None

        return {'id': str(line), 'area_id': area_id, 'name': name, 'kind_code': kind, 'first_line': line,
                'date': start[:10] if start else 'undated', 'started_at': start, 'identity_complete': True,
                'visits': [{'entry_line': line, 'end_line': line + 1, 'entered_at': start, 'ended_at': end,
                            'bounded': bounded, 'seconds': seconds}]}

    @staticmethod
    def build(runs, period = ReportPeriod(), zone = 'Asia/Almaty'):
        selection = ReportPeriodSelection(period, zone, ExecutionContext())
        selected = selection.runs(runs)
        sessions = SessionHistoryBuilder([], [], selected, selection)
        daily = DailyAreaStatisticsBuilder.build(selected, zone, set(), selection.control)

        return AreaDetailsBuilder.build(runs, selected, selection, sessions, daily)

    def test_identity_safe_routes_unknown_time_zero_and_input_preservation(self):
        stamp = '2026-09-01T00:00:00+05:00'
        runs = [self.run_record(1, '../../unsafe', 'Same name', stamp, stamp),
                self.run_record(5, 'other', 'Same name', stamp, stamp),
                self.run_record(9, '', '<script> & /name', None, None),
                self.run_record(13, '', '<script> & /name', None, None, kind = 'town')]
        before = deepcopy(runs)

        model = self.build(runs)

        self.assertEqual(len(model['pages']), 4)
        self.assertEqual(len({page['path'] for page in model['pages']}), 4)

        for page in model['pages']:
            self.assertRegex(page['path'], r'^areas/[0-9a-f]{64}/index.html$')

        zero = self.area(model, '../../unsafe')

        self.assertEqual((zero['metrics']['complete'], zero['metrics']['mean_seconds']), (1, 0))
        self.assertEqual(zero['duration'], '00:00:00')

        unknown = self.area(model, '')

        self.assertEqual(unknown['days'][0]['date'], 'undated')
        self.assertIsNone(unknown['days'][0]['rows'][0]['seconds'])
        self.assertIsNone(unknown['metrics']['mean_seconds'])
        self.assertEqual(unknown['duration'], '—')
        self.assertEqual(unknown['chart']['points'], [])
        self.assertEqual(runs, before)

    def test_midnight_clipping_and_dst_preserve_elapsed_time(self):
        runs = [self.run_record(1, 'area', 'Synthetic area', '2026-09-01T23:59:50+05:00', '2026-09-02T00:00:10+05:00')]
        before = deepcopy(runs)
        full = self.build(runs)['pages'][0]

        self.assertEqual((full['visits'], full['seconds'], len(full['days'])), (1, 20, 1))

        clipped = self.build(runs, ReportPeriod(date(2026, 9, 2), date(2026, 9, 2)))['pages'][0]
        row = clipped['days'][0]['rows'][0]

        self.assertEqual((clipped['visits'], clipped['seconds'], clipped['metrics']['excluded']), (1, 10, 1))
        self.assertTrue(row['clipped'])
        self.assertEqual(row['original_entry'], runs[0]['started_at'])
        self.assertEqual(row['calendar_href'], 'maps/2026-09-02/index.html')
        self.assertEqual(runs, before)

        dst = [self.run_record(1, 'area', 'Synthetic area', '2026-11-01T01:50:00-04:00', '2026-11-01T01:10:00-05:00')]
        page = self.build(dst, zone = 'America/New_York')['pages'][0]

        self.assertEqual((page['seconds'], page['metrics']['mean_seconds']), (1200, 1200))
        self.assertEqual(page['days'][0]['date'], '2026-11-01')

    def test_cancellation_preserves_previous_report(self):
        source = self.source('synthetic.txt', self.fixture())
        request = ReportRequest((source,), self.root / 'report', replace_report = True)
        generator = ReportGenerator()

        generator.generate(request)
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}

        with patch.object(AreaDetailsBuilder, 'build', side_effect = GenerationCancelled('Синтетическая отмена')):
            with self.assertRaises(GenerationCancelled):
                generator.generate(request)

        self.assertEqual(before, {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()})

        selection = ReportPeriodSelection(ReportPeriod(), 'UTC', ExecutionContext(cancelled = lambda: True))

        with self.assertRaises(GenerationCancelled):
            AreaDetailsBuilder.build([], [], selection, SessionHistoryBuilder([], [], [], selection), {'by_date': {}})
