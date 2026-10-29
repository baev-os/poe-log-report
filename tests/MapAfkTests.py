import json
import unittest
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

from poe_log_analyze.stages.composition.AfkMeasurements import AfkMeasurements
from poe_log_analyze.stages.composition.AfkStatisticsBuilder import AfkStatisticsBuilder
from poe_log_analyze.stages.composition.MapGapBuilder import MapGapBuilder
from poe_log_analyze.stages.composition.MapRunMetrics import MapRunMetrics
from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection


class MapAfkTests(unittest.TestCase):
    """Visits, returns, rankings, and gaps share proven AFK intervals."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @staticmethod
    def fixture():
        fixture = MapPaceTests.MapPaceTests
        text = fixture.fixture()

        for anchor, event in ((fixture.line(60, 'Generating level 1 area "HideoutOssuary" with seed 9'),
                              fixture.line(10, ': AFK mode is now ON. Autoreply "Synthetic"')),
                             (fixture.line(90, 'Client-Safe Instance ID = 1'), fixture.line(80, ': AFK mode is now OFF.')),
                             (fixture.line(120, 'Generating level 1 area "HideoutOssuary" with seed 9'),
                              fixture.line(100, ': AFK mode is now ON. Autoreply "Synthetic"')),
                             (fixture.line(150, 'Client-Safe Instance ID = 2'), fixture.line(130, ': AFK mode is now OFF.'))):
            text = text.replace(anchor, event + anchor)

        return text

    def source(self, name, text):
        path = self.root / name
        path.write_text(text)

        return path

    def report(self, name, sources, **options):
        return ReportGenerator().generate(ReportRequest(tuple(sources), self.root / name, **options)).report_path.parent

    @staticmethod
    def data(public, name):
        return json.loads((public.parent / 'project/data' / (name + '.json')).read_text())

    def test_visits_returns_rankings_gaps_and_ru_en(self):
        source = self.source('synthetic.txt', self.fixture())
        before = source.read_bytes()

        for language in ('ru', 'en'):
            public = self.report(language, (source, source), report_language = language, generate_pdf = True)
            pace = self.data(public, 'map_pace')

            self.assertEqual([(r['seconds'], r['afk_seconds'], r['remaining_seconds']) for r in pace['rows']],
                             [(88, 70, 18), (60, 0, 60)])
            self.assertEqual(pace['summary']['mean_seconds'], 74)
            self.assertEqual(pace['without_afk']['summary']['mean_seconds'], 39)
            self.assertEqual(pace['without_afk']['summary']['median_seconds'], 39)
            self.assertEqual((pace['fastest'], pace['without_afk']['fastest']), ([1, 0], [0, 1]))

            gaps = pace['gaps']

            self.assertEqual((gaps['seconds'], gaps['afk_seconds'], gaps['remaining_seconds']), (64, 30, 34))
            self.assertEqual([r['afk_seconds'] for r in gaps['rows']], [20, 10])
            self.assertEqual(gaps['longest'], [0, 1])
            self.assertTrue(gaps['rows'][0]['return'])
            self.assertEqual([len(gap['afk_evidence']) for gap in gaps['rows']], [1, 1])
            self.assertTrue(all(part['href'].startswith('events/page-2.html#')
                                for gap in gaps['rows'] for part in gap['afk_evidence']))

            areas = self.data(public, 'area_details')
            dunes = next(page for page in areas['pages'] if page['area_id'] == 'MapWorldsDunes')
            visits = [row for day in dunes['days'] for row in day['rows']]

            self.assertEqual([row['afk_seconds'] for row in visits], [50, 20])
            self.assertEqual([row['remaining_seconds'] for row in visits], [10, 8])
            self.assertEqual(dunes['without_afk']['mean_seconds'], 18)

            afk = self.data(public, 'afk')

            self.assertEqual(sum(row['afk_seconds'] or 0 for row in afk['by_visit'].values()), 96)
            self.assertEqual(next(row for row in afk['summary']['categories'] if row['code'] == 'map')['afk_seconds'], 70)

            explorer = self.data(public, 'map_explorer')

            self.assertEqual(explorer['without_afk']['mean_seconds'], 39)
            self.assertEqual(explorer['rows'][0]['visits'][1]['remaining_seconds'], 8)
            self.assertIn('data-explorer-duration', (public / 'explore/index.html').read_text())
            self.assertIn('data-map-duration-panel="without_afk"', (public / 'pace/index.html').read_text())
            self.assertIn('00:01:10', (public / dunes['path']).read_text())
            self.assertEqual(self.data(public, 'statistics_summary')['maps']['seconds'], 148)

        self.assertEqual(source.read_bytes(), before)

    def test_period_clips_afk_at_midnight_and_export_needs_no_source(self):
        source = self.source('synthetic.txt', self.fixture())

        full = self.report('full', (source,))
        source.unlink()

        public = self.report('selected', (full.parents[1] / 'analysis',), mode = ReportMode.EXPORT,
            period = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2)))
        pace = self.data(public, 'map_pace')

        self.assertEqual((pace['rows'][0]['seconds'], pace['rows'][0]['afk_seconds'], pace['rows'][0]['remaining_seconds']), (28, 20, 8))
        self.assertIn('clipped', pace['rows'][0]['excluded'])
        self.assertEqual(pace['without_afk']['summary']['mean_seconds'], 60)
        self.assertEqual(pace['without_afk']['summary']['map_seconds'], 68)
        self.assertEqual(pace['gaps']['afk_seconds'], 30)
        self.assertEqual(pace['without_afk']['fastest'], [1])

    def test_branches_partial_copy_and_independent_equal_clocks(self):
        fixture = SharedHistoryTests.SharedHistoryTests
        first = self.source('one.txt', fixture.prefix() + fixture.ending(12, 20, 30, 'Oshabi: Synthetic one.'))
        second = self.source('two.txt', fixture.prefix() + fixture.ending(14, 25, 40, 'The Maven: Synthetic two.'))

        for index, sources in enumerate(((first, second, first), (second, first))):
            pace = self.data(self.report('branch-' + str(index), sources), 'map_pace')

            self.assertEqual((pace['rows'][0]['seconds'], pace['rows'][0]['afk_seconds'], pace['rows'][0]['remaining_seconds']), (33, 12, 21))
            self.assertEqual(pace['without_afk']['fastest'], [])
            self.assertEqual(pace['gaps']['count'], 0)

        short = self.source('short.txt', fixture.prefix())
        pace = self.data(self.report('prefix', (short, first, short)), 'map_pace')

        self.assertEqual((pace['rows'][0]['afk_seconds'], pace['rows'][0]['remaining_seconds']), (8, 10))

        independent = self.source('independent.txt', self.fixture().replace('ID = 1', 'ID = 7').replace('ID = 2', 'ID = 8'))
        original = self.source('original.txt', self.fixture())
        pace = self.data(self.report('independent', (original, independent)), 'map_pace')

        self.assertEqual(sum(row['afk_seconds'] for row in pace['rows']), 140)
        self.assertEqual((pace['gaps']['count'], pace['gaps']['afk_seconds']), (4, 60))

    def test_zero_unmeasured_empty_and_all_afk(self):
        line = MapPaceTests.MapPaceTests.line
        source = self.source('edge.txt', ''.join(line(second, message) for second, message in (
            (0, 'Client-Safe Instance ID = 1'), (0, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
            (0, ': You have entered Dunes.'), (0, ': AFK mode is now ON. Autoreply "Synthetic"'),
            (10, 'Client-Safe Instance ID = 2'), (10, 'Generating level 80 area "MapWorldsBeach" with seed 2'),
            (10, ': You have entered Beach.'),
            (10, 'Client-Safe Instance ID = 3'), (10, 'Generating level 80 area "MapWorldsCitySquare" with seed 3'),
            (10, ': You have entered City Square.'), (12, ': 2 Items identified'))))

        public = self.report('edge', (source,))
        pace = self.data(public, 'map_pace')

        self.assertEqual([row['remaining_seconds'] for row in pace['rows']], [0, 0, None])
        self.assertEqual(pace['without_afk']['summary']['complete'], 2)
        self.assertEqual(pace['without_afk']['summary']['mean_seconds'], 0)
        self.assertIsNone(pace['rows'][-1]['afk_seconds'])

        empty = self.report('empty', (source,), period = ReportPeriod(date(2020, 1, 1), date(2020, 1, 2)))

        self.assertEqual(self.data(empty, 'map_pace')['without_afk']['fastest'], [])

    def test_dst_gap_intersection_unknown_afk_and_cancellation(self):
        rows = [{'entered_at': '2026-10-25T01:30:00+02:00', 'ended_at': '2026-10-25T02:30:00+01:00',
                 'href': 'events/index.html#event-1', 'end_href': 'events/index.html#event-2'}]
        before = deepcopy(rows)
        selection = ReportPeriodSelection(ReportPeriod(), 'Europe/Berlin', ExecutionContext())
        parts = MapGapBuilder.afk_parts(rows, '2026-10-25T02:00:00+02:00', '2026-10-25T03:00:00+01:00', selection)

        self.assertEqual(sum(row['seconds'] for row in parts), 5400)
        self.assertEqual(rows, before)
        self.assertIsNone(AfkMeasurements.combine([AfkMeasurements.balance(60, None)])['remaining_seconds'])

        record = {'seconds': 60, 'remaining_seconds': None, 'new': 1, 'returns': 0, 'excluded': []}

        self.assertEqual(MapRunMetrics.statistics([record])['complete'], 1)

        reduced = MapRunMetrics.statistics([record], duration_field = 'remaining_seconds')

        self.assertEqual(reduced['complete'], 0)
        self.assertIsNone(reduced['map_seconds'])

        with patch.object(ExecutionContext, 'check', side_effect = GenerationCancelled):
            with self.assertRaises(GenerationCancelled):
                MapGapBuilder.afk_parts(rows, rows[0]['entered_at'], rows[0]['ended_at'], selection)

    def test_unknown_provenance_does_not_imply_zero_afk(self):
        visit = {'entry_line': 10, 'entered_at': '2026-09-01T00:00:00+00:00',
                 'ended_at': '2026-09-01T00:01:00+00:00', 'seconds': 60, 'bounded': True,
                 'origin': {'source': 'synthetic-a'}}
        run = {'kind_code': 'map', 'area_id': 'MapWorldsDunes', 'name': 'Dunes', 'visits': [visit]}
        interval = {'first_line': 10, 'started_at': visit['entered_at'], 'ended_at': visit['ended_at'],
                    'origin': {'source': 'synthetic-b'}, 'afk_intervals': []}
        selection = ReportPeriodSelection(ReportPeriod(), 'UTC', ExecutionContext())
        sessions = Mock(rows = {10: {}}, session = Mock(return_value = 10))

        model = AfkStatisticsBuilder.build([interval], [run], sessions, {'days': []}, selection)

        self.assertEqual(model['by_visit']['10']['seconds'], 60)
        self.assertIsNone(model['by_visit']['10']['afk_seconds'])
