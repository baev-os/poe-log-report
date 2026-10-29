import json
import unittest
import MapOutlierTests
import MapPaceTests
import SharedHistoryTests

from copy import deepcopy
from datetime import date

from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import Mock, patch

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.stages.composition.sessions.SessionComparisonBuilder import SessionComparisonBuilder


class SessionComparisonTests(unittest.TestCase):
    """Comparison uses session provenance and existing report measurements."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @staticmethod
    def fixture():
        events = (
            (0, 'Client-Safe Instance ID = 101'),
            (0, 'Generating level 80 area "MapWorldsDunes" with seed 101'),
            (0, ': You have entered Synthetic <Dunes & Hills>.'),
            (1, '[LOADING SCREEN] (Synthetic Map) Duration = 0.75 seconds'),
            (120, 'Generating level 1 area "HideoutOssuary" with seed 999'),
            (121, ': You have entered Synthetic Hideout.'),
            (200, 'Client-Safe Instance ID = 102'),
            (200, 'Generating level 80 area "MapWorldsDunes" with seed 102'),
            (200, ': You have entered Synthetic <Dunes & Hills>.'),
            (201, '[LOADING SCREEN] (Synthetic Map) Duration = 1.25 seconds'),
            (230, ': AFK mode is now ON. Autoreply "Synthetic"'),
            (240, ': SecondHero has been slain.'),
            (250, 'Sister Cassia: Synthetic message.'),
            (260, ': AFK mode is now OFF.'),
            (440, 'Generating level 1 area "HideoutOssuary" with seed 999'),
            (441, ': You have entered Synthetic Hideout.'),
            (500, 'Client-Safe Instance ID = 103'),
            (500, 'Generating level 81 area "MapWorldsDunes" with seed 103'),
            (500, ': You have entered Synthetic <Dunes & Hills>.'),
            (560, 'Generating level 1 area "HideoutOssuary" with seed 999'),
            (561, ': You have entered Synthetic Hideout.'),
            (600, 'Closing game gracefully'))
        return MapOutlierTests.MapOutlierTests.fixture() + ''.join(
            MapPaceTests.MapPaceTests.line(second, message, '2026-09-03T18:00:00') for second, message in events)

    def source(self, text):
        path = self.root / 'synthetic.txt'
        path.write_text(text)

        return path

    def report(self, name, inputs, **options):
        return ReportGenerator().generate(ReportRequest(tuple(inputs), self.root / name, **options)).report_path.parent

    @staticmethod
    def data(public, name = 'session_comparison'):
        return json.loads((public.parent / 'project/data' / (name + '.json')).read_text())

    @staticmethod
    def metrics(row, mode = 'all'):
        return {item['code']: item['value'] for item in row['modes'][mode]['metrics']}

    def test_ru_en_metrics_types_context_unchanged_input_and_pdf(self):
        source = self.source(self.fixture())
        original = source.read_bytes()

        for language in ('ru', 'en'):
            public = self.report(language, (source, source), report_language = language, generate_pdf = True)
            model = self.data(public)

            self.assertEqual(model['version'], '1')
            self.assertEqual(len(model['by_session']), 2)

            first, second = model['by_session'].values()
            a, b = self.metrics(first), self.metrics(second)

            self.assertEqual((a['new'], a['returns'], a['play'], a['afk'], a['median']), (7, 1, 6200, 180, 60))
            self.assertEqual((b['new'], b['returns'], b['play'], b['afk'], b['median']), (3, 0, 600, 30, 120))
            self.assertEqual((b['loading'], b['loading_count'], b['deaths'], b['mechanic:blight']), (2, 2, 1, 1))
            self.assertEqual((b['map'], b['hideout'] + b['other'] + b['unallocated']), (420, 180))
            self.assertEqual(b['rate'], 18)
            self.assertAlmostEqual(self.metrics(second, 'without_afk')['rate'], 3 * 3600 / 570)
            self.assertEqual([row['median_seconds'] for row in second['modes']['all']['types']], [180, 60])
            self.assertEqual([row['median_seconds'] for row in second['modes']['without_afk']['types']], [165, 60])
            self.assertEqual((a['outliers'], b['outliers']), (2, 1))
            self.assertEqual((self.metrics(first, 'without_afk')['outliers'], self.metrics(second, 'without_afk')['outliers']), (1, 1))
            self.assertEqual(len(first['gaps']), a['gap_count'])
            self.assertIn('events/page-2.html#', second['deaths'][0]['href'])

            html = (public / 'sessions/compare/index.html').read_text()

            self.assertIn('Synthetic &lt;Dunes &amp; Hills&gt;', html)
            self.assertNotIn('Synthetic <Dunes', html)
            self.assertIn('data-relative-from=', html)
            self.assertIn('SessionComparison.js', html)

            manifest = json.loads((public.parent / 'report-manifest.json').read_text())

            self.assertIn('session_comparison', manifest['views_sha256'])
            self.assertEqual(manifest['pdf']['content_version'], '12')
            self.assertEqual(sum(self.metrics(row)['play'] for row in model['by_session'].values()), self.data(public, 'activity')['seconds'])

        self.assertEqual(source.read_bytes(), original)

    def test_period_and_export_without_raw_source(self):
        source = self.source(self.fixture())

        public = self.report('full', (source,))
        source.unlink()

        exported = self.report('period', (public.parents[1] / 'analysis',), mode = ReportMode.EXPORT,
            period = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2)))
        model = self.data(exported)

        self.assertEqual(len(model['by_session']), 1)

        row = next(iter(model['by_session'].values()))

        self.assertEqual(self.metrics(row)['new'], 3)
        self.assertEqual(self.metrics(row)['outliers'], 0)
        self.assertTrue(self.data(exported, 'sessions')['rows'][0]['clipped'])

    def test_independent_equal_clocks_do_not_merge_comparison_inputs(self):
        source = self.source(self.fixture())
        other = self.root / 'independent.txt'
        other.write_text(self.fixture().replace('Client-Safe Instance ID = ', 'Client-Safe Instance ID = 8'))
        model = self.data(self.report('independent', (source, other)))

        self.assertEqual(len(model['by_session']), 4)
        self.assertEqual(sorted(self.metrics(row)['new'] for row in model['by_session'].values()), [3, 3, 7, 7])
        self.assertEqual(sum(self.metrics(row)['deaths'] for row in model['by_session'].values()), 4)

    def test_branches_preserve_time_and_exclude_ambiguous_durations(self):
        fixture = SharedHistoryTests.SharedHistoryTests
        source = self.source(fixture.prefix() + fixture.ending(12, 20, 30, 'Oshabi: Synthetic.'))
        other = self.root / 'branch.txt'
        other.write_text(fixture.prefix() + fixture.ending(14, 25, 40, 'The Maven: Synthetic.'))

        public = self.report('branches', (source, other))
        row = next(iter(self.data(public)['by_session'].values()))
        values = self.metrics(row)

        self.assertIsNone(values['median'])
        self.assertEqual((values['complete'], values['excluded'], values['gap_count']), (0, 1, 0))
        self.assertEqual(values['play'], self.data(public, 'sessions')['seconds'])

    def test_types_preserve_null_zero_level_identity_and_input(self):
        rows = [MapOutlierTests.MapOutlierTests.record(i, seconds) for i, seconds in enumerate((0, 10, 20))]
        rows[1]['remaining_seconds'] = None
        rows[2]['excluded'] = ['clipped']
        rows += [MapOutlierTests.MapOutlierTests.record(4, 300, level = None),
                 MapOutlierTests.MapOutlierTests.record(5, 300, area_id = ''),
                 MapOutlierTests.MapOutlierTests.record(6, 40, level = 81),
                 MapOutlierTests.MapOutlierTests.record(7, 50, area_id = 'MapWorldsBeach')]

        for row in rows:
            row['new'] = 1

        original = deepcopy(rows)
        groups, ungrouped = SessionComparisonBuilder.types(rows, 'remaining_seconds', ExecutionContext())

        self.assertEqual((len(groups), ungrouped), (3, 2))

        dunes = next(group for group in groups if group['area_id'] == 'MapWorldsDunes' and group['level'] == 80)

        self.assertEqual((dunes['median_seconds'], dunes['complete'], dunes['excluded']), (0, 1, 2))
        self.assertEqual(rows, original)

        with patch.object(ExecutionContext, 'check', side_effect = GenerationCancelled):
            with self.assertRaises(GenerationCancelled):
                SessionComparisonBuilder.types(rows, 'seconds', ExecutionContext())

    def test_empty_zero_and_unknown_measurements(self):
        public = self.report('empty', (self.source(''),))

        self.assertEqual(self.data(public)['by_session'], {})

        text = MapPaceTests.MapPaceTests.line(0, ': You have entered Synthetic Hideout.')
        text += MapPaceTests.MapPaceTests.line(0, 'Closing game gracefully')

        public = self.report('zero', (self.source(text),))
        row = next(iter(self.data(public)['by_session'].values()))

        self.assertEqual(self.metrics(row)['play'], 0)
        self.assertIsNone(self.metrics(row)['rate'])
        self.assertIsNone(self.metrics(row)['median'])

    def test_cancellation_preserves_current_report(self):
        source = self.source(self.fixture())
        request = ReportRequest((source,), self.root / 'report', replace_report = True)
        generator = ReportGenerator()

        generator.generate(request)
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}

        with patch.object(SessionComparisonBuilder, 'types', side_effect = GenerationCancelled('Синтетическая отмена')):
            with self.assertRaises(GenerationCancelled):
                generator.generate(request)

        self.assertEqual(before, {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()})

    def test_cross_session_return_uses_visit_membership_and_excludes_whole_instance(self):
        membership = Mock()
        membership.session.side_effect = [1, 2]
        membership.selection.period = ReportPeriod()
        membership.selection.zone_name = 'UTC'
        row = MapOutlierTests.MapOutlierTests.record(10, 40)
        row.update(new = 1, session_id = '1', excluded = ['multiple_sessions'])
        row['visits'] = [{'line': line, 'level': 80, 'seconds': 20, 'afk_seconds': 0, 'remaining_seconds': 20,
                          'href': f'areas/synthetic/index.html#visit-{line}'} for line in (10, 20)]
        sessions, balances = [], {}

        for key in ('1', '2'):
            sessions.append({'id': key, 'seconds': 20, 'mechanics': [], 'events': [],
                             'observations': {'loading_seconds': '0', 'loading_count': 0}})
            balances[key] = {'seconds': 20, 'afk_seconds': 0, 'remaining_seconds': 20,
                            'categories': [{'code': code, 'seconds': 20 if code == 'map' else 0}
                                           for code in ('map', 'hideout', 'other', 'unallocated')]}

        views = {'map_explorer': {'rows': [row]}, 'map_pace': {'gaps': {'rows': []}},
                 'map_outliers': {'modes': {'all': {'rows': []}, 'without_afk': {'rows': []}}},
                 'sessions': {'rows': sessions}, 'afk': {'by_session': balances}}
        before = deepcopy(views)
        runs = [{'visits': [{'entry_line': line, 'entered_at': '2026-09-01T00:00:00+00:00'} for line in (10, 20)]}]

        model = SessionComparisonBuilder.build(views, membership, runs, ExecutionContext())
        a, b = (self.metrics(model['by_session'][key]) for key in ('1', '2'))

        self.assertEqual((a['new'], a['returns'], b['new'], b['returns']), (1, 0, 0, 1))
        self.assertEqual((a['excluded'], b['excluded']), (1, 1))
        self.assertIsNone(a['median'])
        self.assertIsNone(b['median'])
        self.assertEqual(views, before)

    def test_dst_timeline_uses_elapsed_utc_seconds(self):
        text = MapPaceTests.MapPaceTests.line(0, ': You have entered Synthetic Hideout.', '2026-03-29T01:59:50')
        text += MapPaceTests.MapPaceTests.line(0, 'Closing game gracefully', '2026-03-29T03:00:10')

        public = self.report('dst', (self.source(text),), timezone = 'Europe/Berlin')
        row = next(iter(self.data(public)['by_session'].values()))

        self.assertEqual(self.metrics(row)['play'], 20)

        chart = self.data(public, 'sessions')['rows'][0]['timeline']

        self.assertEqual(chart['end'] - chart['start'], 20)
