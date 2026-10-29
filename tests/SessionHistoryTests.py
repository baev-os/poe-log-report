import json
import unittest

from copy import deepcopy
from datetime import date, datetime, timedelta

from pathlib import Path
from tempfile import TemporaryDirectory

from pypdf import PdfReader

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection
from poe_log_analyze.stages.composition.sessions.SessionHistoryBuilder import SessionHistoryBuilder
from poe_log_analyze.stages.merging.SharedSessions import SharedSessions


class SessionHistoryTests(unittest.TestCase):
    """Sessions preserve boundaries, provenance, and shared measurements across summaries."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @staticmethod
    def line(second, message, start = '2026-09-01T23:59:00'):
        stamp = datetime.fromisoformat(start) + timedelta(seconds = second)
        return f'{stamp:%Y/%m/%d %H:%M:%S} 1 abcd [INFO Client 1] {message}\n'

    @classmethod
    def fixture(cls):
        return '\n' * 500 + ''.join(cls.line(second, message) for second, message in (
            (0, 'Client-Safe Instance ID = 1'),
            (0, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
            (0, ': You have entered Dunes.'),
            (1, '[LOADING SCREEN] (Dunes) Duration = 1.25 seconds'),
            (2, 'Sister Cassia: Synthetic observation.'),
            (5, ': Hero<&> (Duelist) is now level 89'),
            (30, 'Generating level 1 area "HideoutOssuary" with seed 2'),
            (31, ': You have entered Synthetic Hideout.'),
            (35, ': 7 Items identified'),
            (60, 'Client-Safe Instance ID = 1'),
            (60, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
            (61, ': You have entered Dunes.'),
            (70, ': Hero<&> has been slain.'),
            (80, 'Generating level 1 area "HideoutOssuary" with seed 2'),
            (80, 'Abnormal disconnect: An unexpected disconnection occurred.'),
            (3660, 'Generating level 1 area "HideoutOssuary" with seed 3'),
            (3661, ': You have entered Synthetic Hideout.'),
            (3662, '[LOADING SCREEN] (Hideout) Duration = 0.75 seconds'),
            (3665, ': 3 Items identified'),
            (3681, 'Generating level 80 area "MapWorldsDunes" with seed 3'),
            (3681, 'Abnormal disconnect: An unexpected disconnection occurred.'),
            (7260, 'Generating level 80 area "MapWorldsDunes" with seed 4'),
            (7260, ': You have entered Dunes.'),
            (7270, ': Hero<&> (Duelist) is now level 90'),
        ))

    def source(self, name, text):
        path = self.root / name
        path.write_text(text, encoding = 'utf-8')

        return path

    def report(self, name, sources, **options):
        result = ReportGenerator().generate(ReportRequest(tuple(sources), self.root / name, **options))
        return result.report_path.parent

    @staticmethod
    def data(public, name = 'sessions'):
        return json.loads((public.parent / 'project/data' / (name + '.json')).read_text())

    def test_midnight_returns_counters_localization_links_and_pdf(self):
        source = self.source('synthetic.txt', self.fixture())
        original = source.read_bytes()

        for language, title in (('ru', 'Игровые сессии'), ('en', 'Play sessions')):
            public = self.report(language, (source, source), report_language = language, generate_pdf = True)
            model = self.data(public)
            first, second, third = model['rows']

            self.assertEqual((model['count'], model['seconds'], model['incomplete']), (3, 110, 1))
            self.assertEqual(model['seconds'], self.data(public, 'activity')['seconds'])
            self.assertEqual(model['seconds'], sum(day['seconds'] for day in self.data(public, 'daily_playtime')['days']))
            self.assertEqual((first['start'], first['end']), ('01.09.2026 23:59:00', '02.09.2026 00:00:20'))
            self.assertEqual((first['statistics']['maps']['count'], first['statistics']['maps']['visits']), (1, 2))
            self.assertEqual(first['statistics']['maps']['seconds'], 49)
            self.assertEqual(first['statistics']['zone_totals']['seconds'], 78)
            self.assertEqual(len(first['maps']), 2)
            self.assertEqual(first['mechanics'][0]['count'], 1)
            self.assertEqual([row['observations']['loading_seconds'] for row in model['rows']], ['1.25', '0.75', '0'])
            self.assertEqual([row['observations']['items_identified'] for row in model['rows']], [7, 3, 0])
            self.assertEqual([item['event']['type'] for item in first['events']],
                             ['screen.level_up', 'screen.slain', 'network.abnormal_disconnect'])
            self.assertEqual(third['branches'][0]['reason'], 'eof')
            self.assertFalse(first['clipped'])
            self.assertFalse(first['branched'])
            self.assertEqual(first['next'], second['path'])
            self.assertEqual(third['previous'], second['path'])
            self.assertIsNone(first['previous'])
            self.assertIsNone(third['next'])

            page = (public / first['path']).read_text()

            self.assertIn('Hero&lt;&amp;&gt;', page)
            self.assertNotIn('Hero<&>', page)
            self.assertIn('уровень 89' if language == 'ru' else 'level 89', page)
            self.assertIn(title, (public / 'sessions/index.html').read_text())
            self.assertIn(title, '\n'.join(page.extract_text() for page in PdfReader(public / 'report.pdf').pages))

            for href in [first['start_href'], *(row['href'] for row in first['maps']),
                         *(item['href'] for item in first['events'])]:
                target, anchor = href.split('#')

                self.assertNotEqual(target, 'events/index.html')
                self.assertIn(f'id="{anchor}"', (public / target).read_text())

        self.assertEqual(source.read_bytes(), original)

    def test_period_clips_time_keeps_original_boundaries_and_exports_without_source(self):
        source = self.source('synthetic.txt', self.fixture())

        public = self.report('full', (source,))
        analysis = public.parents[1] / 'analysis'
        source.unlink()

        selected = self.report('selected', (analysis,), mode = ReportMode.EXPORT,
                               period = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2)))
        model = self.data(selected)
        first = model['rows'][0]

        self.assertEqual((model['count'], model['seconds']), (3, 50))
        self.assertEqual(first['start'], '02.09.2026 00:00:00')
        self.assertEqual(first['branches'][0]['start'], '01.09.2026 23:59:00')
        self.assertTrue(first['clipped'])
        self.assertEqual(first['statistics']['maps']['seconds'], 19)
        self.assertEqual(first['mechanics'], [])
        self.assertEqual(first['observations']['items_identified'], 0)
        self.assertEqual(first['observations']['loading_seconds'], '0')
        self.assertNotIn('screen.level_up', [item['event']['type'] for item in first['events']])

        empty = self.report('empty', (analysis,), mode = ReportMode.EXPORT,
                            period = ReportPeriod(date(2026, 10, 1), None))

        self.assertEqual((self.data(empty)['count'], self.data(empty)['rows']), (0, []))
        self.assertEqual({path.name for path in (empty / 'sessions').iterdir()}, {'index.html', 'compare'})

    def test_branch_ranges_do_not_capture_another_session_between_continuations(self):
        prefix = ''.join(self.line(second, message) for second, message in (
            (0, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
            (1, ': You have entered Dunes.'),
            (10, ': Hero (Duelist) is now level 89')))
        first = self.source('one.txt', prefix + self.line(15, ': 5 Items identified')
                            + self.line(20, 'Abnormal disconnect: An unexpected disconnection occurred.')
                            + self.line(3600, ': You have entered Synthetic Hideout.')
                            + self.line(3601, ': 100 Items identified')
                            + self.line(3602, ': OtherHero (Duelist) is now level 50'))
        second = self.source('two.txt', prefix + self.line(10, ': 7 Items identified')
                             + self.line(30, ': BranchHero (Duelist) is now level 90'))
        short = self.source('short.txt', prefix)

        for index, sources in enumerate(((first, second, short), (second, short, first))):
            public = self.report(str(index), sources)
            sessions = self.data(public)['rows']

            self.assertEqual(len(sessions), 2)
            self.assertEqual([row['seconds'] for row in sessions], [39, 2])
            self.assertEqual([row['observations']['items_identified'] for row in sessions], [12, 100])
            self.assertTrue(sessions[0]['branched'])
            self.assertEqual(len(sessions[0]['branches']), 2)
            self.assertEqual([item['event']['message']['fields']['character'] for item in sessions[0]['events']
                              if item['event']['type'] == 'screen.level_up'], ['Hero', 'BranchHero'])
            self.assertEqual(self.data(public)['seconds'], self.data(public, 'activity')['seconds'])

    def test_zero_duration_tail_preserves_events_and_short_copy_does_not_add_incompleteness(self):
        prefix = self.line(0, ': You have entered Synthetic Hideout.')
        short = self.source('short.txt', prefix)
        first = self.source('one.txt', prefix + self.line(0, ': FirstHero (Duelist) is now level 10')
                            + self.line(0, 'Abnormal disconnect: An unexpected disconnection occurred.'))
        second = self.source('two.txt', prefix + self.line(0, ': SecondHero (Duelist) is now level 20')
                             + self.line(0, 'Abnormal disconnect: An unexpected disconnection occurred.'))

        public = self.report('zero', (short, first, second, first))
        model = self.data(public)

        self.assertEqual((model['count'], model['seconds'], model['incomplete']), (1, 0, 0))
        self.assertEqual(len(model['rows'][0]['branches']), 2)
        self.assertEqual(len(model['rows'][0]['events']), 4)

    def test_independent_sources_with_equal_timestamps_keep_separate_counters(self):
        sources = []

        for seed, count in ((1, 7), (2, 11)):
            sources.append(self.source(f'{seed}.txt', self.line(0, f'Generating level 80 area "MapWorldsDunes" with seed {seed}')
                                       + self.line(1, ': You have entered Dunes.')
                                       + self.line(2, f': {count} Items identified')
                                       + self.line(20, 'Abnormal disconnect: An unexpected disconnection occurred.')))

        model = self.data(self.report('independent', sources))

        self.assertEqual((model['count'], model['seconds']), (2, 38))
        self.assertEqual([row['observations']['items_identified'] for row in model['rows']], [7, 11])
        self.assertTrue(all(not row['branched'] for row in model['rows']))

    def test_gap_and_clock_regression_end_at_last_observation(self):
        source = self.source('boundaries.txt', ''.join(self.line(second, message) for second, message in (
            (0, ': You have entered Synthetic Hideout.'),
            (10, ': 1 Items identified'),
            (2000, ': You have entered Dunes.'),
            (2010, ': 2 Items identified'),
            (1000, ': You have entered Synthetic Hideout.'),
            (1010, ': 3 Items identified'))))
        rows = self.data(self.report('boundaries', (source,)))['rows']

        self.assertEqual([row['seconds'] for row in rows], [10, 10, 10])
        self.assertEqual([row['branches'][0]['reason'] for row in rows], ['gap', 'eof', 'clock'])
        self.assertTrue(all(row['incomplete'] for row in rows))

    def test_dst_and_empty_input(self):
        source = self.source('dst.txt', self.line(0, ': You have entered Synthetic Hideout.', '2026-03-29T01:59:50')
                             + self.line(0, 'Abnormal disconnect: An unexpected disconnection occurred.', '2026-03-29T03:00:10'))
        model = self.data(self.report('dst', (source,), timezone = 'Europe/Berlin'))

        self.assertEqual((model['count'], model['seconds']), (1, 20))

        empty = self.source('empty.txt', '')

        self.assertEqual(self.data(self.report('empty', (empty,)))['rows'], [])

    def test_projection_does_not_mutate_boundaries_and_line_mapping_observes_cancellation(self):
        definition = {'first_line': 2, 'line_ranges': [[2, 4]], 'branches': [
            {'first_line': 2, 'last_line': 4, 'started_at': '2026-09-01T10:00:00+05:00',
             'ended_at': '2026-09-01T10:00:20+05:00', 'reason': 'eof', 'incomplete': True}]}
        intervals = [{**definition['branches'][0], 'seconds': 20}]
        original = deepcopy((definition, intervals))
        control = ExecutionContext()
        selection = ReportPeriodSelection(ReportPeriod(), 'Asia/Almaty', control)
        model = SessionHistoryBuilder([definition], intervals, [], selection).result({'by_date': {}})

        self.assertEqual((definition, intervals), original)
        self.assertEqual(model['seconds'], 20)
        self.assertEqual(SharedSessions.line_ranges([0, 1, 2, 10, 11], 1, 4, control), [[1, 2], [10, 11]])

        control.cancelled = lambda: True

        with self.assertRaises(GenerationCancelled):
            SharedSessions.line_ranges(list(range(2000)), 1, 1999, control)
