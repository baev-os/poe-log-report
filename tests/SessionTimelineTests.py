import hashlib
import json
import unittest
import SessionHistoryTests
import SharedHistoryTests

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

from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection
from poe_log_analyze.stages.composition.sessions.SessionTimelineBuilder import SessionTimelineBuilder
from poe_log_analyze.stages.reconstruction.PlaytimeBuilder import PlaytimeBuilder


class SessionTimelineTests(unittest.TestCase):
    """Exit boundaries, session lanes, and exact links independent of copied timestamps."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @staticmethod
    def line(second, message, start = '2026-09-01T23:59:00'):
        return SessionHistoryTests.SessionHistoryTests.line(second, message, start)

    def source(self, name, text):
        path = self.root / name
        path.write_text(text)

        return path

    def report(self, name, sources, **options):
        result = ReportGenerator().generate(ReportRequest(tuple(sources), self.root / name, **options))
        return result.report_path.parent

    @staticmethod
    def data(public, name = 'sessions'):
        return json.loads((public.parent / 'project/data' / (name + '.json')).read_text())

    @staticmethod
    def track(session, code):
        return next(track['items'] for track in session['timeline']['tracks'] if track['code'] == code)

    @classmethod
    def fixture(cls):
        return SessionHistoryTests.SessionHistoryTests.fixture().replace(
            'Abnormal disconnect: An unexpected disconnection occurred.', 'Closing game gracefully')

    def test_graceful_exit_ends_observations_and_clears_area_context_ru_en_pdf(self):
        source = self.source('synthetic.txt', '\n' * 500 + ''.join(self.line(second, message) for second, message in (
            (0, 'Client-Safe Instance ID = 1'),
            (0, 'Generating level 80 area "MapWorldsDunes" with seed 1'), (0, ': You have entered Dunes.'),
            (1, '[LOADING SCREEN] (Dunes) Duration = 0.75 seconds'), (5, 'Closing game gracefully'),
            (8, 'Sister Cassia: Synthetic message after exit.'), (20, ': FirstHero (Duelist) is now level 10'),
            (30, 'Client-Safe Instance ID = 1'),
            (30, 'Generating level 80 area "MapWorldsDunes" with seed 1'), (30, ': You have entered Dunes.'),
            (35, 'Closing game gracefully'), (40, ': 3 Items identified'))))
        before = source.read_bytes()

        for language, label in (('ru', 'Выход из игры'), ('en', 'Game closed')):
            public = self.report(language, (source, source), report_language = language, generate_pdf = True)
            model = self.data(public)

            self.assertEqual((model['version'], model['count'], model['seconds'], model['incomplete']), ('2', 2, 10, 0))
            self.assertTrue(all(row['ending_reasons'] == ['game.closing'] for row in model['rows']))
            self.assertTrue(all(row['ending_label'] == label for row in model['rows']))
            self.assertFalse(any(row['events'] or row['mechanics'] for row in model['rows']))

            runs = [run for day in self.data(public, 'maps')['by_date'].values() for run in day['runs']]

            self.assertEqual(len(runs), 2)
            self.assertTrue(all(run['end_reason_code'] == 'game.closing' for run in runs))
            self.assertIsNone(runs[0]['visits'][0]['ended_at'])
            self.assertIn(label, (public / 'sessions/index.html').read_text())
            self.assertIn(label, '\n'.join(page.extract_text() for page in PdfReader(public / 'report.pdf').pages))
            self.assertEqual(self.track(model['rows'][0], 'events')[0]['label_key'], 'session_end.game.closing')
            self.assertIn('events/page-2.html#line-', (public / model['rows'][0]['path']).read_text())

        self.assertEqual(source.read_bytes(), before)

    def test_tracks_time_breakdown_markers_and_period_export_without_source(self):
        source = self.source('synthetic.txt', self.fixture())

        public = self.report('full', (source,))
        model = self.data(public)
        first = model['rows'][0]

        self.assertEqual((first['seconds'], first['ending_reasons']), (80, ['game.closing']))

        areas, loads, events = (self.track(first, key) for key in ('areas', 'loading', 'events'))

        self.assertEqual(sum(item['seconds'] or 0 for item in areas), 78)
        self.assertEqual(sum(row['seconds'] for row in first['timeline']['breakdown']), 78)
        self.assertEqual(first['timeline']['unallocated'], '00:00:02')
        self.assertEqual(len(areas), 3)
        self.assertEqual((loads[0]['from'], loads[0]['to'], loads[0]['seconds'], loads[0]['clipped']), (0, 1 / 80, 1.25, True))
        self.assertEqual({item['label_key'] for item in events}, {'mechanic.blight', 'event_title.screen.level_up',
                                                               'event_title.screen.slain', 'session_end.game.closing'})
        self.assertIn('Hero<&>', next(item['label'] for item in events if item['label_key'] == 'event_title.screen.level_up'))
        self.assertTrue(any('02.09.2026' in tick['label'] for tick in first['timeline']['ticks']))

        page = (public / first['path']).read_text()

        self.assertIn('Hero&lt;&amp;&gt;', page)
        self.assertIn('data-session-zoom', page)
        self.assertIn('#visit-', page)

        analysis = public.parents[1] / 'analysis'
        source.unlink()

        exported = self.report('export', (analysis,), mode = ReportMode.EXPORT,
                               period = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2)))
        selected = self.data(exported)['rows'][0]

        self.assertEqual(selected['ending_reasons'], ['game.closing'])
        self.assertEqual(selected['seconds'], 20)
        self.assertTrue(selected['clipped'])
        self.assertEqual(self.track(selected, 'loading'), [])
        self.assertTrue(all(0 <= item['from'] <= item['to'] <= 1 for track in selected['timeline']['tracks'] for item in track['items']))

    def test_gaps_eof_and_clock_keep_explicit_causes_and_do_not_infer_exit(self):
        source = self.source('synthetic.txt', ''.join(self.line(second, message) for second, message in (
            (0, ': You have entered Dunes.'), (10, ': 1 Items identified'), (2000, 'Closing game gracefully'),
            (2001, ': You have entered Dunes.'), (2010, ': 2 Items identified'),
            (1000, ': You have entered Dunes.'), (1010, ': 3 Items identified'))))
        rows = self.data(self.report('gaps', (source,)))['rows']

        self.assertEqual([row['ending_reasons'] for row in rows], [['gap'], ['eof'], ['clock']])
        self.assertTrue(all(row['incomplete'] and row['seconds'] < 30 for row in rows))
        self.assertTrue(all(row['ending_label'] != 'Incomplete session' for row in rows))

    def test_shared_branches_use_separate_lanes_and_short_copy_cannot_hide_exit(self):
        prefix = SharedHistoryTests.SharedHistoryTests.prefix()
        one = self.source('one.txt', prefix + SharedHistoryTests.SharedHistoryTests.ending(12, 20, 30, 'Oshabi: Synthetic first branch.').replace(
            'Abnormal disconnect: An unexpected disconnection occurred.', 'Closing game gracefully'))
        two = self.source('two.txt', prefix + SharedHistoryTests.SharedHistoryTests.ending(14, 25, 40, 'The Maven: Synthetic second branch.'))
        short = self.source('short.txt', prefix)
        rows = self.data(self.report('branches', (one, two, short, one)))['rows']

        self.assertEqual(len(rows), 1)

        row = rows[0]

        self.assertFalse(row['incomplete'])
        self.assertEqual(set(row['ending_reasons']), {'game.closing', 'network.abnormal_disconnect'})
        self.assertEqual(sum(item['seconds'] or 0 for item in self.track(row, 'areas')), row['statistics']['zone_totals']['seconds'])
        self.assertEqual(len([item for item in self.track(row, 'events') if item['label_key'] == 'mechanic.blight']), 1)
        self.assertGreater(max(item['lane'] for item in self.track(row, 'areas')), 0)

    def test_independent_equal_clocks_keep_separate_timeline_events(self):
        one = self.source('one.txt', self.fixture())
        two = self.source('two.txt', self.fixture().replace('ID = 1', 'ID = 17').replace('seed 1', 'seed 17').replace('Hero<&>', 'SecondHero'))
        rows = self.data(self.report('independent', (one, two)))['rows']
        first_sessions = [row for row in rows if row['seconds'] == 80]

        self.assertEqual(len(first_sessions), 2)

        names = [' '.join(item['label'] for item in self.track(row, 'events')) for row in first_sessions]

        self.assertEqual(sum('SecondHero' in text for text in names), 1)
        self.assertEqual(sum('Hero<&>' in text for text in names), 1)

    def test_dst_unknown_zero_empty_and_chart_does_not_mutate_inputs(self):
        text = self.line(0, ': You have entered Synthetic Hideout.', '2026-03-29T01:59:50')
        text += self.line(0, 'Closing game gracefully', '2026-03-29T03:00:10')

        public = self.report('dst', (self.source('dst.txt', text),), timezone = 'Europe/Berlin')
        chart = self.data(public)['rows'][0]['timeline']

        self.assertEqual(chart['end'] - chart['start'], 20)
        self.assertIn('+0100', chart['ticks'][0]['label'])
        self.assertIn('+0200', chart['ticks'][-1]['label'])

        zero = self.source('zero.txt', self.line(0, ': You have entered Dunes.') + self.line(0, 'Closing game gracefully'))
        session = self.data(self.report('zero', (zero,)))['rows'][0]
        before = deepcopy(session)
        result = SessionTimelineBuilder.chart(session, [], [], [], ReportPeriodSelection(ReportPeriod(), 'UTC', ExecutionContext()))

        self.assertEqual(result['start'], result['end'])
        self.assertEqual(session, before)
        self.assertEqual(self.data(self.report('empty', (self.source('empty.txt', ''),)))['rows'], [])

    def test_cancellation_preserves_report(self):
        source = self.source('synthetic.txt', self.fixture())
        request = ReportRequest((source,), self.root / 'report', replace_report = True)
        generator = ReportGenerator()

        generator.generate(request)
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}

        with patch.object(SessionTimelineBuilder, 'build', side_effect = GenerationCancelled('Синтетическая отмена')):
            with self.assertRaises(GenerationCancelled):
                generator.generate(request)

        self.assertEqual(before, {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()})

    def test_missing_exit_time_and_new_log_are_not_confirmed_endings(self):
        for kind, stamp, reason in (('game.closing', None, 'missing_time'),
                                    ('log.open', '2026-09-01T10:00:10+05:00', 'log.open')):
            rows = [{'line_number': 1, 'record_id': 1, 'status': 'recognized', 'type': 'area.enter', 'timestamp': '2026-09-01T10:00:00+05:00'},
                    {'line_number': 2, 'record_id': 2, 'status': 'recognized', 'type': 'screen.items_identified', 'timestamp': '2026-09-01T10:00:05+05:00'},
                    {'line_number': 3, 'record_id': 3, 'status': 'recognized', 'type': kind, 'timestamp': stamp}]
            ledger = self.root / 'lines.jsonl'
            ledger.write_text(''.join(json.dumps(row) + '\n' for row in rows))

            activity = PlaytimeBuilder.build_activity(ledger, hashlib.sha256(ledger.read_bytes()).hexdigest())

            self.assertEqual((activity['seconds'], activity['incomplete']), (5, 1))
            self.assertEqual(activity['intervals'][0]['reason'], reason)
