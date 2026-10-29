import json
import unittest
import MapOutlierTests
import MapPaceTests
import SharedHistoryTests

from copy import deepcopy
from datetime import date
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

from poe_log_analyze.stages.composition.MapRunDetailsBuilder import MapRunDetailsBuilder
from poe_log_analyze.stages.composition.MapRunTimelineBuilder import MapRunTimelineBuilder
from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection


class MapRunDetailsTests(unittest.TestCase):
    """Cards preserve instances, visits, provenance, and shared metrics."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @staticmethod
    def fixture():
        rows = MapOutlierTests.MapOutlierTests.fixture().splitlines(keepends = True)[500:]
        rows.extend(MapPaceTests.MapPaceTests.line(second, message, '2026-09-01T23:00:00') for second, message in (
            (5001, '[LOADING SCREEN] (Synthetic <Dunes & Hills>) Duration = 1.2 seconds'),
            (5015, 'Deadlock detected with timeout 1000ms; no running graph'),
            (5183, '[LOADING SCREEN] (Synthetic Hideout) Duration = 2.3 seconds'),
            (5190, ': AFK mode is now ON. Autoreply "Synthetic"'),
            (5200, ': AFK mode is now OFF.'),
            (5211, '[LOADING SCREEN] (Synthetic <Dunes & Hills>) Duration = 2 seconds')))

        return '\n' * 500 + ''.join(sorted(rows, key = lambda row: row[:19]))

    def source(self, text, name = 'synthetic.txt'):
        path = self.root / name
        path.write_text(text)

        return path

    def report(self, name, sources, **options):
        return ReportGenerator().generate(ReportRequest(tuple(sources), self.root / name, **options)).report_path.parent

    @staticmethod
    def data(public, name = 'map_run_details'):
        return json.loads((public.parent / 'project/data' / (name + '.json')).read_text())

    @staticmethod
    def returned(model):
        return next(page for page in model['pages'] if page['returns'])

    def test_ru_en_totals_context_navigation_links_and_pdf(self):
        source = self.source(self.fixture())
        original = source.read_bytes()

        for language in ('ru', 'en'):
            public = self.report(language, (source, source), report_language = language, generate_pdf = True)
            model = self.data(public)

            self.assertEqual(len(model['pages']), 7)

            run = self.returned(model)

            self.assertEqual((run['seconds'], run['afk_seconds'], run['remaining_seconds']), (240, 180, 60))
            self.assertEqual((run['gap_balance']['seconds'], run['gap_balance']['afk_seconds']), (30, 10))
            self.assertEqual(run['gaps'][0]['zones'][0]['seconds'], 26)
            self.assertEqual((len(run['loading']), len(run['issues'])), (3, 1))
            self.assertEqual(run['comparisons']['all']['median_seconds'], 60)
            self.assertEqual(run['comparisons']['all']['difference_seconds'], 180)
            self.assertEqual(run['comparisons']['without_afk']['difference_seconds'], 0)
            self.assertEqual(run['comparisons']['all']['peers'], 6)
            self.assertTrue(run['previous'] and run['next'])

            tracks = {track['code']: track['items'] for track in run['timeline']['tracks']}

            self.assertEqual(sum(item['seconds'] for item in tracks['areas'] if item['category'] == 'map'), 240)
            self.assertEqual(sum(item['seconds'] for item in tracks['afk']), 190)
            self.assertEqual(len(tracks['loading']), 3)
            self.assertEqual(len(tracks['events']), 3)

            html = (public / run['path']).read_text()

            self.assertIn('Synthetic &lt;Dunes &amp; Hills&gt;', html)
            self.assertIn('events/page-2.html#line-', html)
            self.assertIn('stability-record-', html)
            self.assertIn('id="visit-' + str(run['visits'][1]['line']) + '"', html)

            for path in ('flow/index.html', 'explore/index.html', 'pace/index.html', 'maps/2026-09-02/index.html'):
                self.assertIn(run['path'], (public / path).read_text())

            self.assertTrue((public / 'report.pdf').exists())

        self.assertEqual(source.read_bytes(), original)

    def test_comparison_excludes_self_wrong_level_missing_afk_and_zero_baseline(self):
        fixture = MapOutlierTests.MapOutlierTests
        rows = [fixture.record(i, value) for i, value in enumerate((0, 0, 0, 0, 0, 120))]
        rows += [fixture.record(6, 600, level = 81)]
        rows[0]['remaining_seconds'] = None
        original = deepcopy(rows)
        result = MapRunDetailsBuilder.comparisons(rows, ExecutionContext())

        self.assertEqual(result[5]['all']['median_seconds'], 0)
        self.assertEqual(result[5]['all']['difference_seconds'], 120)
        self.assertIsNone(result[5]['all']['percent'])
        self.assertEqual(result[5]['without_afk']['status'], 'insufficient')
        self.assertEqual(result[0]['without_afk']['status'], 'excluded')
        self.assertEqual(result[6]['all']['status'], 'insufficient')
        self.assertEqual(rows, original)

    def test_copied_prefix_forks_keep_visits_and_disable_navigation_in_every_order(self):
        fixture = SharedHistoryTests.SharedHistoryTests
        first = self.source(fixture.prefix() + fixture.ending(12, 20, 30, 'Oshabi: Synthetic.'), 'first.txt')
        second = self.source(fixture.prefix() + fixture.ending(14, 25, 40, 'The Maven: Synthetic.'), 'second.txt')
        short = self.source(fixture.prefix(), 'short.txt')

        for index, sources in enumerate(permutations((first, second, short))):
            pages = self.data(self.report('fork-' + str(index), sources))['pages']

            self.assertEqual(len(pages), 1)

            run = pages[0]

            self.assertEqual((len(run['visits']), run['seconds']), (1, 33))
            self.assertIsNone(run['previous'])
            self.assertIsNone(run['next'])
            self.assertEqual(run['comparisons']['all']['status'], 'excluded')
            self.assertTrue(run['visits'][0]['branches'])

            track = run['timeline']['tracks'][0]['items']

            self.assertEqual(sum(item['seconds'] for item in track), 33)

    def test_period_clips_visits_and_gaps_and_exports_without_source(self):
        source = self.source(MapPaceTests.MapPaceTests.fixture())

        public = self.report('full', (source,))
        source.unlink()

        sliced = self.report('sliced', (public.parents[1] / 'analysis',), mode = ReportMode.EXPORT,
                             period = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2)))
        run = self.returned(self.data(sliced))

        self.assertEqual(run['seconds'], 28)
        self.assertEqual(run['gap_balance']['seconds'], 32)
        self.assertEqual(run['comparisons']['all']['status'], 'excluded')
        self.assertTrue((sliced / run['path']).exists())

        empty = self.report('empty-period', (public.parents[1] / 'analysis',), mode = ReportMode.EXPORT,
                            period = ReportPeriod(date(2026, 10, 1), date(2026, 10, 1)))

        self.assertEqual(self.data(empty)['pages'], [])

    def test_equal_clocks_keep_context_in_independent_files(self):
        one = self.source(self.fixture(), 'one.txt')
        two = self.source(self.fixture().replace('Synthetic <Dunes & Hills>', 'Synthetic Other')
                          .replace('Deadlock detected with timeout 1000ms; no running graph', 'Synthetic ordinary message'), 'two.txt')
        model = self.data(self.report('independent', (one, two)))

        self.assertEqual(len(model['pages']), 14)

        returned = [page for page in model['pages'] if page['returns']]

        self.assertEqual(sorted(len(page['issues']) for page in returned), [0, 1])
        self.assertEqual([page['gap_balance']['seconds'] for page in returned], [30, 30])

        for page in returned:
            self.assertTrue(all(load['from_area'] in (page['name'], 'Synthetic Hideout') for load in page['loading']))

    def test_same_identifiers_after_another_map_keep_reconstructed_runs_separate(self):
        rows = ((0, 'Client-Safe Instance ID = 1'),
                (0, 'Generating level 80 area "MapWorldsDunes" with seed 1'), (0, ': You have entered Dunes.'),
                (20, 'Client-Safe Instance ID = 2'),
                (20, 'Generating level 80 area "MapWorldsCitySquare" with seed 2'), (20, ': You have entered City Square.'),
                (40, 'Client-Safe Instance ID = 1'),
                (40, 'Generating level 80 area "MapWorldsDunes" with seed 1'), (40, ': You have entered Dunes.'),
                (60, 'Generating level 1 area "HideoutOssuary" with seed 9'), (60, ': You have entered Hideout.'),
                (80, 'Closing game gracefully'))
        source = self.source(''.join(MapPaceTests.MapPaceTests.line(second, text) for second, text in rows))

        public = self.report('other-map', (source,))
        pages = self.data(public)['pages']

        self.assertEqual(len(pages), 3)
        self.assertEqual([page['seconds'] for page in pages], [20, 20, 20])
        self.assertEqual([page['gaps'] for page in pages], [[], [], []])
        self.assertEqual(pages[0]['next']['path'], pages[1]['path'])
        self.assertEqual(self.data(public, 'map_pace')['summary']['map_seconds'], 60)

    def test_zero_unknown_and_empty_inputs(self):
        prefix = ''.join(MapPaceTests.MapPaceTests.line(0, message) for message in (
            'Client-Safe Instance ID = 1', 'Generating level 80 area "MapWorldsDunes" with seed 1', ': You have entered Dunes.'))
        unknown = self.data(self.report('unknown', (self.source(prefix, 'unknown.txt'),)))['pages'][0]

        self.assertFalse(unknown['observed'])
        self.assertIsNone(unknown['timeline']['tracks'][0]['items'][0]['seconds'])

        zero = self.data(self.report('zero', (self.source(prefix + MapPaceTests.MapPaceTests.line(0,
            'Generating level 1 area "HideoutOssuary" with seed 9'), 'zero.txt'),)))['pages'][0]

        self.assertTrue(zero['observed'])
        self.assertEqual(zero['seconds'], 0)
        self.assertEqual(self.data(self.report('empty', (self.source('', 'empty.txt'),)))['pages'], [])

    def test_branched_return_keeps_unknown_gap_instead_of_zero(self):
        line = MapPaceTests.MapPaceTests.line
        prefix = ''.join(line(second, message) for second, message in (
            (0, 'Client-Safe Instance ID = 1'), (0, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
            (0, ': You have entered Dunes.'), (60, 'Generating level 1 area "HideoutOssuary" with seed 9'),
            (62, ': You have entered Hideout.'), (90, 'Client-Safe Instance ID = 1'),
            (90, 'Generating level 80 area "MapWorldsDunes" with seed 1'), (92, ': You have entered Dunes.')))
        sources = []

        for second in (120, 130):
            sources.append(self.source(prefix + line(second, 'Generating level 1 area "HideoutOssuary" with seed 9')
                                       + line(second + 2, ': You have entered Hideout.')
                                       + line(second + 5, 'Closing game gracefully'), str(second) + '.txt'))

        run = self.returned(self.data(self.report('branched-return', sources)))

        self.assertEqual(run['unknown_gaps'], 1)
        self.assertIsNone(run['gap_balance']['seconds'])
        self.assertEqual(run['gap_balance']['duration'], '—')
        self.assertIsNone(run['next'])
        self.assertEqual(len(run['visits']), 2)
        self.assertTrue(run['visits'][1]['branches'])

    def test_dst_uses_real_seconds_and_cancellation_is_checked(self):
        selection = ReportPeriodSelection(ReportPeriod(), 'Europe/Berlin', ExecutionContext())
        run = {'name': 'Synthetic', 'visits': [{'entry_line': 1, 'bounded': True, 'seconds': 2,
               'entered_at': '2026-10-25T02:59:59+02:00', 'ended_at': '2026-10-25T02:00:01+01:00'}]}
        page = {'path': 'maps/runs/1/index.html', 'gaps': [], 'loading': [], 'issues': [], 'afk_rows': [], 'visits': []}
        original = deepcopy(run)

        chart = MapRunTimelineBuilder.build(page, run, selection)

        self.assertEqual(chart['end'] - chart['start'], 2)
        self.assertEqual(chart['tracks'][0]['items'][0]['seconds'], 2)
        self.assertEqual(run, original)

        with patch.object(ExecutionContext, 'check', side_effect = GenerationCancelled):
            with self.assertRaises(GenerationCancelled):
                MapRunTimelineBuilder.build(page, run, selection)

    def test_cancellation_preserves_current_report_and_data(self):
        source = self.source(MapPaceTests.MapPaceTests.fixture())
        request = ReportRequest((source,), self.root / 'report', replace_report = True)

        ReportGenerator().generate(request)
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}

        with patch.object(MapRunDetailsBuilder, 'build', side_effect = GenerationCancelled('Синтетическая отмена')):
            with self.assertRaises(GenerationCancelled):
                ReportGenerator().generate(request)

        self.assertEqual(before, {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()})
