import json
import unittest
import MapPaceTests
import SessionTimelineTests

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

from poe_log_analyze.stages.composition.DayOverviewBuilder import DayOverviewBuilder
from poe_log_analyze.stages.composition.MapExplorerBuilder import MapExplorerBuilder
from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection


class MapExplorerTests(unittest.TestCase):
    """Instance selection and day overview preserve measurements, provenance, and boundaries."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def source(self, name, text):
        path = self.root / name
        path.write_text(text)

        return path

    def report(self, name, sources, **options):
        return ReportGenerator().generate(ReportRequest(tuple(sources), self.root / name, **options)).report_path.parent

    @staticmethod
    def data(public, name):
        return json.loads((public.parent / 'project/data' / (name + '.json')).read_text())

    def test_ru_en_instances_returns_metrics_evidence_and_export_without_source(self):
        text = MapPaceTests.MapPaceTests.fixture().replace(
            MapPaceTests.MapPaceTests.line(60, 'Generating level 1 area "HideoutOssuary" with seed 9'),
            MapPaceTests.MapPaceTests.line(5, 'Sister Cassia: Synthetic observation.') +
            MapPaceTests.MapPaceTests.line(60, 'Generating level 1 area "HideoutOssuary" with seed 9'))
        source = self.source('synthetic.txt', text)
        before = source.read_bytes()

        public = self.report('first', (source, source))
        model = self.data(public, 'map_explorer')

        self.assertEqual((model['version'], len(model['rows'])), ('2', 2))

        pace = self.data(public, 'map_pace')['summary']

        for key in ('count', 'complete', 'excluded', 'map_seconds', 'returns', 'mean_seconds', 'median_seconds'):
            self.assertEqual(model['summary'][key], pace[key], key)

        self.assertEqual(model['mechanics'], ['blight'])

        first = model['rows'][0]

        self.assertEqual((first['date'], first['levels'], first['returns'], first['seconds']), ('2026-09-01', [80], 1, 88))
        self.assertEqual(len(first['visits']), 2)
        self.assertTrue(first['observed'])
        self.assertEqual(source.read_bytes(), before)

        analysis = public.parents[1] / 'analysis'
        source.unlink()

        for language in ('ru', 'en'):
            exported = self.report(language, (analysis,), mode = ReportMode.EXPORT, report_language = language, generate_pdf = True)

            self.assertEqual(self.data(exported, 'map_explorer'), model)

            page = (exported / 'explore/index.html').read_text()

            self.assertIn('Synthetic &lt;City &amp; Square&gt;', page)
            self.assertIn('data-cohort="b"', page)
            self.assertIn('MapExplorer.js', page)
            self.assertNotIn('explorer.method', page)
            self.assertGreater(len(PdfReader(exported / 'report.pdf').pages), 0)

            for row in model['rows']:
                for item in [*row['visits'], *row['evidence']]:
                    path, anchor = item['href'].split('#')

                    self.assertIn(f'id="{anchor}"', (exported / path).read_text())

    def test_period_keeps_first_entry_date_and_excludes_partial_mean(self):
        source = self.source('synthetic.txt', MapPaceTests.MapPaceTests.fixture())

        public = self.report('slice', (source,), period = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2)))
        rows = self.data(public, 'map_explorer')['rows']

        self.assertEqual((rows[0]['date'], rows[0]['seconds']), ('2026-09-01', 28))
        self.assertIn('clipped', rows[0]['excluded'])
        self.assertEqual(self.data(public, 'map_explorer')['summary']['median_seconds'], 60)
        self.assertEqual(self.data(public, 'day_overview')['by_date']['2026-09-02']['seconds'], 180)

    def test_day_sessions_midnight_loads_levels_deaths_and_eof(self):
        source = self.source('synthetic.txt', SessionTimelineTests.SessionTimelineTests.fixture())

        public = self.report('days', (source, source))
        days = self.data(public, 'day_overview')['by_date']
        first, second = days['2026-09-01'], days['2026-09-02']

        self.assertEqual((first['seconds'], second['seconds']), (60, 50))
        self.assertEqual((first['sessions'][0]['seconds'], second['sessions'][0]['seconds']), (60, 20))
        self.assertEqual(first['sessions'][0]['href'], second['sessions'][0]['href'])
        self.assertEqual(first['sessions'][0]['ending_reasons'], ['game.closing'])
        self.assertEqual((first['loading_seconds'], second['loading_seconds']), ('1.25', '0.75'))
        self.assertEqual({item['event']['type'] for item in first['events']}, {'screen.level_up'})
        self.assertEqual({item['event']['type'] for item in second['events']}, {'screen.level_up', 'screen.slain'})
        self.assertEqual(sum(day['seconds'] for day in days.values()), self.data(public, 'daily_playtime')['seconds'])
        self.assertIn('Hero&lt;&amp;&gt;', (public / 'maps/2026-09-01/index.html').read_text())
        self.assertIn('events/page-2.html#line-', (public / 'maps/2026-09-02/index.html').read_text())

    def test_events_only_day_and_empty_export(self):
        source = self.source('event.txt', MapPaceTests.MapPaceTests.line(0, ': SyntheticHero (Duelist) is now level 10'))

        public = self.report('event', (source,))
        day = self.data(public, 'day_overview')['by_date']['2026-09-01']

        self.assertEqual((day['seconds'], day['sessions'], len(day['events'])), (0, [], 1))
        self.assertTrue((public / 'maps/2026-09-01/index.html').is_file())
        self.assertIn('2026-09-01/index.html', (public / 'maps/index.html').read_text())

        empty = self.report('empty', (source,), period = ReportPeriod(date(2030, 1, 1), None))

        self.assertEqual(self.data(empty, 'map_explorer')['rows'], [])
        self.assertEqual(self.data(empty, 'day_overview')['by_date'], {})
        self.assertTrue((empty / 'explore/index.html').is_file())

    def test_unknown_zero_durations_and_same_name_different_ids(self):
        from AreaDetailsTests import AreaDetailsTests
        zero = AreaDetailsTests.run_record(1, 'MapWorldsDunes', '<Same>', '2026-09-01T00:00:00+05:00', '2026-09-01T00:00:00+05:00', 'map')
        unknown = AreaDetailsTests.run_record(3, 'MapWorldsCitySquare', '<Same>', None, None, 'map')
        runs = [zero, unknown]
        pace = {'rows': [{'line': row['first_line'], 'name': row['name'], 'timestamp': row['started_at'],
                         'seconds': 0, 'returns': 0, 'new': 0, 'excluded': ['incomplete'] if index else []}
                        for index, row in enumerate(runs)]}
        selection = ReportPeriodSelection(ReportPeriod(), 'Asia/Almaty', ExecutionContext())
        before = deepcopy((runs, pace))

        result = MapExplorerBuilder.build(pace, runs, selection)

        self.assertEqual([row['observed'] for row in result['rows']], [True, False])
        self.assertEqual(result['summary']['median_seconds'], 0)
        self.assertEqual(len({row['type'] for row in result['rows']}), 2)
        self.assertEqual(len({row['label'] for row in result['types']}), 2)
        self.assertIsNone(result['rows'][1]['date'])
        self.assertEqual((runs, pace), before)

    def test_independent_equal_clocks_and_shared_branches(self):
        from SharedHistoryTests import SharedHistoryTests
        one = self.source('one.txt', MapPaceTests.MapPaceTests.fixture())
        two = self.source('two.txt', MapPaceTests.MapPaceTests.fixture().replace('seed 1', 'seed 17').replace('ID = 1', 'ID = 17'))

        public = self.report('independent', (one, two))

        self.assertEqual(self.data(public, 'map_explorer')['summary']['count'], 4)
        self.assertEqual(sum(day['seconds'] for day in self.data(public, 'day_overview')['by_date'].values()), 480)

        one.write_text(SharedHistoryTests.prefix() + SharedHistoryTests.ending(12, 20, 30, 'Oshabi: Synthetic branch.'))
        two.write_text(SharedHistoryTests.prefix() + SharedHistoryTests.ending(14, 25, 40, 'The Maven: Synthetic branch.'))

        public = self.report('branches', (one, two))
        model = self.data(public, 'map_explorer')

        self.assertEqual((model['summary']['count'], model['summary']['complete'], model['summary']['map_seconds']), (1, 0, 33))
        self.assertIn('branched', model['rows'][0]['excluded'])

    def test_day_dst_and_decimal_sum_do_not_change_inputs(self):
        interval = {'first_line': 1, 'started_at': '2026-11-01T00:30:00-04:00', 'ended_at': '2026-11-02T00:30:00-05:00', 'seconds': 90000}
        session = {'id': '1', 'path': 'sessions/1/index.html', 'start': 'start', 'end': 'end', 'ending_reasons': ['eof']}
        loading = {'rows': [{'date': '2026-11-01', 'seconds': '0.1'}, {'date': '2026-11-01', 'seconds': '0.2'}]}

        from poe_log_analyze.stages.composition.DailyPlaytimeBuilder import DailyPlaytimeBuilder

        daily = DailyPlaytimeBuilder.build({'intervals': [interval]}, 'America/New_York')
        selection = ReportPeriodSelection(ReportPeriod(), 'America/New_York', ExecutionContext())
        areas = {'by_date': {day['date']: {} for day in daily['days']}}
        inputs = ({'by_date': {}}, loading, {'rows': [session]}, [interval], daily, areas)
        before = deepcopy(inputs)

        result = DayOverviewBuilder.build(*inputs, selection)

        self.assertEqual([day['seconds'] for day in result['by_date'].values()], [88200, 1800])
        self.assertEqual(result['by_date']['2026-11-01']['loading_seconds'], '0.3')
        self.assertEqual(inputs, before)

    def test_cancellation_preserves_current_report(self):
        source = self.source('synthetic.txt', MapPaceTests.MapPaceTests.fixture())
        request = ReportRequest((source,), self.root / 'report', replace_report = True)
        generator = ReportGenerator()

        generator.generate(request)
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}

        with patch.object(MapExplorerBuilder, 'build', side_effect = GenerationCancelled('Синтетическая отмена')):
            with self.assertRaises(GenerationCancelled):
                generator.generate(request)

        self.assertEqual(before, {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()})
