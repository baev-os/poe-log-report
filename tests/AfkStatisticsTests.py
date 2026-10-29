import hashlib
import json
import unittest
import SessionHistoryTests
import SharedHistoryTests

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone

from itertools import permutations

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

from poe_log_analyze.stages.composition.AfkStatisticsBuilder import AfkStatisticsBuilder
from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection
from poe_log_analyze.stages.reconstruction.PlaytimeBuilder import PlaytimeBuilder


class AfkStatisticsTests(unittest.TestCase):
    """AFK follows proven boundaries, areas, and branches without assuming log silence means inactivity."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @staticmethod
    def line(second, message, start = '2026-09-01T23:59:30'):
        return SessionHistoryTests.SessionHistoryTests.line(second, message, start)

    @classmethod
    def fixture(cls):
        return '\n' * 500 + ''.join(cls.line(second, message) for second, message in (
            (0, 'Client-Safe Instance ID = 1'),
            (0, 'Generating level 80 area "MapWorldsDunes" with seed 1'), (0, ': You have entered Dunes.'),
            (10, ': AFK mode is now ON. Autoreply "Synthetic"'),
            (15, ': AFK mode is now ON. Autoreply "Repeated"'),
            (30, 'Generating level 1 area "HideoutOssuary" with seed 2'), (32, ': You have entered Synthetic <Hideout &>.'),
            (40, ': AFK mode is now OFF.'), (50, ': AFK mode is now ON. Autoreply "Synthetic"'),
            (55, 'Generating level 1 area "1_1_town" with seed 3'), (57, ': You have entered Synthetic Town.'),
            (65, ': AFK mode is now OFF.'),
            (70, 'Client-Safe Instance ID = 4'),
            (70, 'Generating level 80 area "MapWorldsCitySquare" with seed 4'), (72, ': You have entered City Square.'),
            (80, ': AFK mode is now ON. Autoreply "Synthetic"'), (90, 'Closing game gracefully'),
            (120, ': 3 Items identified')))

    def source(self, name, text):
        path = self.root / name
        path.write_text(text)

        return path

    def report(self, name, sources, **options):
        result = ReportGenerator().generate(ReportRequest(tuple(sources), self.root / name, **options))
        return result.report_path.parent

    @staticmethod
    def data(public, name = 'afk'):
        return json.loads((public.parent / 'project/data' / (name + '.json')).read_text())

    def activity(self, events):
        rows = []

        for line, (second, kind) in enumerate(events, 1):
            stamp = (datetime(2026, 9, 1, tzinfo = timezone.utc) + timedelta(seconds = second)).isoformat() if second is not None else None
            rows.append({'line_number': line, 'record_id': line, 'status': 'recognized', 'type': kind, 'timestamp': stamp})

        ledger = self.root / 'ledger.jsonl'
        raw = ''.join(json.dumps(row) + '\n' for row in rows).encode()
        ledger.write_bytes(raw)

        return PlaytimeBuilder.build_activity(ledger, hashlib.sha256(raw).hexdigest())

    @staticmethod
    def seconds(model):
        return sum((datetime.fromisoformat(afk['ended_at']) - datetime.fromisoformat(afk['entered_at'])).total_seconds()
                   for part in model['intervals'] for afk in part['afk_intervals'])

    def test_repeated_on_off_and_session_boundaries(self):
        model = self.activity([(0, 'area.enter'), (10, 'screen.afk_off'), (20, 'screen.afk_on'),
            (25, 'screen.afk_on'), (40, 'screen.afk_off'), (45, 'screen.afk_off'),
            (50, 'screen.afk_on'), (60, 'game.closing'), (90, 'screen.items_identified'),
            (100, 'area.enter'), (110, 'screen.afk_off'), (120, 'game.closing')])

        self.assertEqual((model['seconds'], self.seconds(model)), (80, 30))

        parts = model['intervals'][0]['afk_intervals']

        self.assertEqual([part['open_at_end'] for part in parts], [False, True])
        self.assertEqual(parts[0]['first_line'], 3)
        self.assertEqual(model['intervals'][1]['afk_intervals'], [])

    def test_missing_time_gap_clock_eof_and_initial_afk(self):
        cases = (
            ([(0, 'screen.afk_on'), (5, 'area.enter'), (10, 'screen.afk_off')], 5),
            ([(0, 'area.enter'), (5, 'screen.afk_on'), (10, 'screen.items_identified')], 5),
            ([(0, 'area.enter'), (5, 'screen.afk_on'), (10, 'screen.items_identified'),
              (None, 'screen.afk_off'), (20, 'game.closing')], 5),
            ([(0, 'area.enter'), (5, 'screen.afk_on'), (10, 'screen.items_identified'),
              (2000, 'area.enter'), (2010, 'game.closing')], 5),
            ([(0, 'area.enter'), (5, 'screen.afk_on'), (10, 'screen.items_identified'),
              (2, 'area.enter'), (7, 'game.closing')], 5),
            ([(0, 'area.enter'), (5, 'screen.afk_on'), (10, 'screen.items_identified'),
              (20, 'log.open'), (30, 'area.enter'), (40, 'game.closing')], 5),
            ([(0, 'area.enter'), (5, 'screen.afk_on'), (10, 'screen.items_identified'),
              (None, 'area.enter'), (20, 'area.enter'), (30, 'game.closing')], 5),
        )

        for events, expected in cases:
            with self.subTest(events = events):
                self.assertEqual(self.seconds(self.activity(events)), expected)

    def test_summaries_areas_rates_timeline_and_ru_en_pdf(self):
        source = self.source('synthetic.txt', self.fixture())
        before = source.read_bytes()

        for language, title in (('ru', 'Распределение времени и AFK'), ('en', 'Time breakdown and AFK')):
            public = self.report(language, (source, source), report_language = language, generate_pdf = True)
            model = self.data(public)
            summary = model['summary']

            self.assertEqual((summary['seconds'], summary['afk_seconds'], summary['remaining_seconds']), (90, 55, 35))
            self.assertEqual([(row['code'], row['seconds'], row['afk_seconds']) for row in summary['categories']],
                             [('map', 30, 20), ('hideout', 23, 13), ('other', 13, 8), ('unallocated', 24, 14)])
            self.assertEqual([day['afk_seconds'] for day in model['by_date'].values()], [20, 35])
            self.assertEqual(sum(row['seconds'] for row in model['rows']), 55)

            session = self.data(public, 'sessions')['rows'][0]
            track = next(track for track in session['timeline']['tracks'] if track['code'] == 'afk')

            self.assertEqual(sum(row['seconds'] for row in track['items']), 55)

            pace = self.data(public, 'map_pace')['summary']

            self.assertEqual((pace['new'], pace['rate'], pace['remaining_seconds']), (2, 80, 35))
            self.assertAlmostEqual(pace['rate_without_afk'], 2 * 3600 / 35)

            for page in ('index.html', 'maps/2026-09-02/index.html', session['path']):
                self.assertIn(title, (public / page).read_text())

            page = (public / session['path']).read_text()

            self.assertIn('Synthetic &lt;Hideout &amp;&gt;', page)
            self.assertNotIn('Synthetic <Hideout', page)
            self.assertIn('session-color-afk', page)
            self.assertTrue(all(row['href'].startswith('events/page-2.html#line-') for row in model['rows']))

            pdf = '\n'.join(page.extract_text() for page in PdfReader(public / 'report.pdf').pages)

            self.assertIn(title, pdf)
            self.assertIn('00:00:55', pdf)

        self.assertEqual(source.read_bytes(), before)

    def test_period_export_without_source_and_afk_before_period(self):
        source = self.source('synthetic.txt', self.fixture())

        public = self.report('full', (source,))
        original = self.data(public)
        source.unlink()

        selected = self.report('selected', (public.parents[1] / 'analysis',), mode = ReportMode.EXPORT,
                               period = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2)))
        model = self.data(selected)

        self.assertEqual((model['summary']['seconds'], model['summary']['afk_seconds']), (60, 35))
        self.assertEqual(model['summary'], original['by_date']['2026-09-02'])
        self.assertTrue(all(row['entered_at'].startswith('2026-09-02') for row in model['rows']))
        self.assertEqual(self.data(selected, 'map_pace')['summary']['remaining_seconds'], 25)

    def test_shared_prefix_branches_input_order_and_independent_equal_clocks(self):
        fixture = SharedHistoryTests.SharedHistoryTests
        first = self.source('one.txt', fixture.prefix() + fixture.ending(12, 20, 30, 'Oshabi: Synthetic first branch.'))
        second = self.source('two.txt', fixture.prefix() + fixture.ending(14, 25, 40, 'The Maven: Synthetic second branch.'))
        short = self.source('short.txt', fixture.prefix())

        for index, sources in enumerate(permutations((first, second, short))):
            public = self.report('branches-' + str(index), sources)
            model = self.data(public)

            self.assertEqual((model['summary']['seconds'], model['summary']['afk_seconds']), (58, 12))
            self.assertEqual(next(row for row in model['summary']['categories'] if row['code'] == 'map')['afk_seconds'], 12)

        independent = self.source('independent.txt', first.read_text().replace('Client-Safe Instance ID = 1', 'Client-Safe Instance ID = 9'))

        public = self.report('independent', (first, independent))
        model = self.data(public)

        self.assertEqual((model['summary']['seconds'], model['summary']['afk_seconds']), (56, 16))
        self.assertEqual(len(model['by_session']), 2)

    def test_dst_midnight_and_exact_visit_clipping_without_mutation(self):
        selection = ReportPeriodSelection(ReportPeriod(date(2026, 10, 25), date(2026, 10, 25)),
                                          'Europe/Berlin', ExecutionContext())
        visit = {'entered_at': '2026-10-24T23:00:00+02:00', 'ended_at': '2026-10-26T01:00:00+01:00',
                 'seconds': 27 * 3600, 'bounded': True, 'afk_seconds': 26 * 3600,
                 'afk_intervals': [{'entered_at': '2026-10-24T23:30:00+02:00', 'ended_at': '2026-10-26T00:30:00+01:00'}]}
        before = deepcopy(visit)
        clipped = selection.visit(visit)

        self.assertEqual((clipped['seconds'], clipped['afk_seconds']), (25 * 3600, 25 * 3600))
        self.assertEqual(visit, before)

        days = AfkStatisticsBuilder.days(datetime.fromisoformat(visit['entered_at']).timestamp(),
                                         datetime.fromisoformat(visit['ended_at']).timestamp(), selection)

        self.assertEqual(days, [('2026-10-24', 3600), ('2026-10-25', 25 * 3600), ('2026-10-26', 3600)])

    def test_empty_all_afk_zero_denominator_and_cancel(self):
        source = self.source('empty.txt', '')

        public = self.report('empty', (source,))

        self.assertEqual(self.data(public)['summary']['afk_seconds'], 0)
        self.assertIsNone(self.data(public, 'map_pace')['summary']['rate_without_afk'])

        source.write_text(''.join(self.line(second, message) for second, message in (
            (0, ': You have entered Synthetic Zone.'), (0, ': AFK mode is now ON. Autoreply "Synthetic"'),
            (10, 'Closing game gracefully'))))

        public = self.report('all-afk', (source,))

        self.assertEqual(self.data(public)['summary']['remaining_seconds'], 0)
        self.assertIsNone(self.data(public, 'map_pace')['summary']['rate_without_afk'])

        with patch.object(AfkStatisticsBuilder, 'spans', side_effect = GenerationCancelled):
            with self.assertRaises(GenerationCancelled):
                self.report('cancelled', (source,))

        self.assertFalse((self.root / 'cancelled').exists())
