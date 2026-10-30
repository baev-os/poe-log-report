import itertools
import json
import unittest

from copy import deepcopy
from datetime import date, datetime, timedelta

from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import patch

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.stages.composition.StabilityStatisticsBuilder import StabilityStatisticsBuilder
from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection
from poe_log_analyze.stages.composition.sessions.SessionHistoryBuilder import SessionHistoryBuilder
from poe_log_analyze.stages.parsing.TechnicalIssueClassifier import TechnicalIssueClassifier
from poe_log_analyze.stages.reconstruction.MapActivityBuilder import MapActivityBuilder
from poe_log_analyze.stages.reconstruction.TechnicalContextTracker import TechnicalContextTracker


class StabilityTests(unittest.TestCase):
    """Context provenance, exact message counts, and preservation of all repeats."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @staticmethod
    def line(second, message, level = 'INFO'):
        stamp = datetime(2026, 9, 1, 23, 59) + timedelta(seconds = second)
        return f'{stamp:%Y/%m/%d %H:%M:%S} {second + 1000} abc [{level} Client 42] {message}\n'

    @classmethod
    def fixture(cls):
        repeated = 'Deadlock detected with timeout 1000ms; running graph nodes: Present'
        rows = [(0, 'Generating level 1 area "HideoutOssuary" with seed 1', 'INFO'),
                (1, ': You have entered Synthetic <Hub & Base>.', 'INFO'),
                (2, '[LOADING SCREEN] (Synthetic <Hub & Base>) Duration = 0.25 seconds', 'INFO'),
                (3, repeated, 'INFO'), (4, repeated, 'INFO'),
                (5, 'Synthetic <warning & detail>', 'WARN'), (6, repeated, 'INFO'),
                (10, 'Generating level 80 area "MapWorldsDunes" with seed 2', 'INFO'),
                (11, repeated, 'INFO'), (12, ': You have entered Synthetic Dunes.', 'INFO'),
                (13, '[LOADING SCREEN] (Synthetic Dunes) Duration = 2 seconds', 'INFO'),
                (14, 'Abnormal disconnect: An unexpected disconnection occurred.', 'INFO'),
                (15, 'fatal error: Synthetic <failure & reason>', 'INFO'),
                (16, '[JOB] Irrecoverable Exception Callback: SET', 'INFO'),
                (17, '#SyntheticSpeaker: fatal error', 'INFO'),
                (70, 'Synthetic later warning', 'WARN'), (90, 'Closing game gracefully', 'INFO')]

        return b'\n' * 500 + ''.join(cls.line(*row) for row in rows).encode() + b'\xff\n'

    def source(self, raw, name = 'synthetic.txt'):
        path = self.root / name
        path.write_bytes(raw)

        return path

    def report(self, name, sources, **options):
        return ReportGenerator().generate(ReportRequest(tuple(sources), self.root / name, **options)).report_path.parent

    @staticmethod
    def data(public, name = 'stability'):
        return json.loads((public.parent / 'project/data' / (name + '.json')).read_text())

    @staticmethod
    def rows(model):
        return [row for series in model['series'].values() for row in series['rows']]

    @staticmethod
    def event(line, second, kind, fields = None, **extra):
        stamp = (datetime(2026, 9, 1) + timedelta(seconds = second)).isoformat() + '+00:00' if second is not None else None
        return {'line_number': line, 'record_id': line, 'timestamp': stamp, 'status': 'recognized',
                'type': kind, 'fields': fields or {}, **extra}

    @staticmethod
    def tracker():
        return TechnicalContextTracker(set(MapActivityBuilder.BOUNDARIES), 1800, ExecutionContext())

    def test_classifier_excludes_normal_exit_callback_chat_and_continuations(self):
        for kind in ('game.closing', 'job.exception_callback', 'chat.channel', 'reliquary.message'):
            text = 'normal exit' if kind == 'game.closing' else 'fatal error'

            self.assertIsNone(TechnicalIssueClassifier.category(self.event(1, 0, kind, text = text)))

        self.assertIsNone(TechnicalIssueClassifier.category(self.event(2, 0, 'unknown', record_id = 1, text = 'fatal error')))
        self.assertEqual(TechnicalIssueClassifier.category(self.event(1, None, 'encoding.error', status = 'error', record_id = None)), 'reading')
        self.assertEqual(TechnicalIssueClassifier.category(self.event(1, 0, 'unknown', text = 'fatal error')), 'crash')
        self.assertEqual(TechnicalIssueClassifier.category(self.event(1, 0, 'unknown', header = {'level': 'WARNING'})), 'warning')

        for kind in ('network.instance_disconnect', 'network.site_settings_ssl_failed', 'screen.join_instances_failed'):
            self.assertEqual(TechnicalIssueClassifier.category(self.event(1, 0, kind)), 'client')
            self.assertEqual(StabilityStatisticsBuilder.family('client', kind), 'network')

    def test_tracker_nearest_ties_boundaries_clock_missing_and_gap(self):
        tracker = self.tracker()
        rows = [self.event(1, 0, 'area.enter', {'area': 'A'}),
                self.event(2, 1, 'loading.duration', {'area': 'A', 'seconds': '0'}),
                self.event(3, 3, 'graph.deadlock'),
                self.event(4, 5, 'loading.duration', {'area': 'A', 'seconds': '1'}),
                self.event(5, 6, 'network.abnormal_disconnect'),
                self.event(6, 7, 'graph.deadlock')]
        original = deepcopy(rows)

        for row in rows:
            tracker.add(row)

        self.assertEqual(rows, original)
        self.assertEqual(tracker.rows[0]['loading']['line'], 2)
        self.assertEqual(tracker.rows[1]['area']['name'], 'A')
        self.assertIsNone(tracker.rows[2]['area'])
        self.assertIsNone(tracker.rows[2]['loading'])

        for second in (None, -1, 1801):
            tracker = self.tracker()
            tracker.add(self.event(1, 0, 'area.enter', {'area': 'A'}))
            tracker.add(self.event(2, second, 'graph.deadlock'))

            self.assertIsNone(tracker.rows[0]['area'])

        tracker = self.tracker()
        tracker.add(self.event(1, 0, 'graph.deadlock'))
        tracker.add(self.event(2, 61, 'loading.duration', {'area': 'A', 'seconds': '1'}))

        self.assertIsNone(tracker.rows[0]['loading'])

    def test_full_ru_en_copies_series_context_calendar_and_pdf(self):
        source = self.source(self.fixture())
        before = source.read_bytes()

        for language in ('ru', 'en'):
            public = self.report(language, (source, source), report_language = language, generate_pdf = True)
            model = self.data(public)

            self.assertEqual(model['summary']['count'], 9)
            self.assertEqual(model['summary']['counts'], {'disconnect': 1, 'network': 0, 'render': 4, 'crash': 1,
                                                        'client': 0, 'warning': 2, 'reading': 1})
            self.assertEqual((model['series_count'], model['affected_sessions'], model['summary']['unassigned']), (8, 1, 3))
            self.assertEqual([day['count'] for day in model['by_date'].values()], [7, 1, 1])

            series = list(model['series'].values())

            self.assertEqual(series[0]['count'], 2)

            first = series[0]['rows'][0]

            self.assertEqual(first['area']['name'], 'Synthetic <Hub & Base>')
            self.assertTrue(first['area']['href'].startswith('events/page-2.html#'))

            transition = next(row for row in self.rows(model) if row['line'] == 509)

            self.assertIsNone(transition['area'])
            self.assertEqual(transition['loading'][0]['area'], 'Synthetic Dunes')
            self.assertEqual(transition['loading'][0]['delta_seconds'], 2)

            html = (public / 'technical/issues/index.html').read_text()

            self.assertIn('Synthetic &lt;Hub &amp; Base&gt;', html)
            self.assertIn('id="stability-record-504"', html)
            self.assertIn('id="line-504"', html)
            self.assertIn('stability-day-2026-09-01', (public / 'maps/index.html').read_text())
            self.assertIn('stability-day-2026-09-02', (public / 'maps/2026-09-02/index.html').read_text())
            self.assertIn('stability-session-', (public / first['session_href'].split('#')[0]).read_text())
            self.assertTrue((public / 'report.pdf').exists())

        self.assertEqual(source.read_bytes(), before)

    def test_period_keeps_context_and_full_history_export_without_source(self):
        raw = (self.line(58, ': You have entered Synthetic Before.')
               + self.line(59, '[LOADING SCREEN] (Synthetic Before) Duration = 0 seconds')
               + self.line(61, 'Deadlock detected with timeout 1000ms; no running graph')
               + self.line(80, 'Closing game gracefully')).encode()
        source = self.source(raw)

        full = self.report('full', (source,))
        source.unlink()

        public = self.report('period', (full.parents[1] / 'analysis',), mode = ReportMode.EXPORT,
                             period = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2)))
        model = self.data(public)
        row = self.rows(model)[0]

        self.assertEqual(model['summary']['count'], 1)
        self.assertEqual(row['area']['name'], 'Synthetic Before')
        self.assertEqual(row['loading'][0]['line'], 2)
        self.assertEqual(self.data(public, 'loading')['summary']['count'], 0)

        empty = self.report('empty-period', (full.parents[1] / 'analysis',), mode = ReportMode.EXPORT,
                            period = ReportPeriod(date(2026, 10, 1), date(2026, 10, 1)))

        self.assertEqual(self.data(empty)['summary']['count'], 0)
        self.assertEqual(self.data(empty, 'issues')['count'], 1)

    def test_branch_context_and_series_do_not_cross_copies_in_all_orders(self):
        issue = 'Deadlock detected with timeout 1000ms; no running graph'
        prefix = (self.line(0, ': You have entered Synthetic Shared.') + self.line(1, issue)).encode()
        first = self.source(prefix + (self.line(2, issue) + self.line(3, '[LOADING SCREEN] (Branch A) Duration = 1 seconds')).encode(), 'a.txt')
        second = self.source(prefix + (self.line(2, issue).replace('abc', 'def') + self.line(3, '[LOADING SCREEN] (Branch B) Duration = 2 seconds')).encode(), 'b.txt')
        short = self.source(prefix, 'short.txt')

        for index, sources in enumerate(itertools.permutations((first, second, short))):
            model = self.data(self.report('branches-' + str(index), sources))

            self.assertEqual((model['summary']['count'], model['series_count']), (3, 3))

            shared = next(row for row in self.rows(model) if row['time'].endswith('23:59:01 +0100'))

            self.assertEqual({load['area'] for load in shared['loading']}, {'Branch A', 'Branch B'})

            tails = [row for row in self.rows(model) if row != shared]

            self.assertEqual(sorted(len(row['loading']) for row in tails), [1, 1])

    def test_independent_equal_clocks_and_empty_log(self):
        raw = self.fixture()
        one = self.source(raw, 'one.txt')
        two = self.source(raw.replace(b'Synthetic <Hub & Base>', b'Synthetic Independent'), 'two.txt')
        model = self.data(self.report('independent', (one, two)))

        self.assertEqual((model['summary']['count'], model['series_count'], model['affected_sessions']), (18, 16, 2))

        empty = self.data(self.report('empty', (self.source(b'', 'empty.txt'),)))

        self.assertEqual(empty['summary']['count'], 0)
        self.assertEqual(empty['chart']['bars'], [])

    def test_dst_and_cancellation(self):
        tracker = self.tracker()
        tracker.add(self.event(1, 0, 'area.enter', {'area': 'A'}, timestamp = '2026-10-25T02:59:59+02:00'))
        tracker.add(self.event(2, 0, 'graph.deadlock', timestamp = '2026-10-25T02:00:00+01:00'))

        self.assertEqual(tracker.rows[0]['area']['name'], 'A')

        source = self.source(self.fixture())
        request = ReportRequest((source,), self.root / 'report', replace_report = True)

        ReportGenerator().generate(request)
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}

        with patch.object(StabilityStatisticsBuilder, 'build', side_effect = GenerationCancelled('Синтетическая отмена')):
            with self.assertRaises(GenerationCancelled):
                ReportGenerator().generate(request)

        self.assertEqual(before, {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()})

        with patch.object(ExecutionContext, 'check', side_effect = GenerationCancelled):
            with self.assertRaises(GenerationCancelled):
                self.tracker().add(self.event(1, 0, 'graph.deadlock'))

    def test_all_boundaries_transitions_and_unknown_critical_time(self):
        for kind in (*MapActivityBuilder.BOUNDARIES, 'area.generate', 'network.instance_connect'):
            tracker = self.tracker()
            tracker.add(self.event(1, 0, 'area.enter', {'area': 'A'}))
            tracker.add(self.event(2, 1, 'graph.deadlock'))
            tracker.add(self.event(3, 2, kind))
            tracker.add(self.event(4, 3, 'graph.deadlock'))

            self.assertIsNone(tracker.rows[-1]['previous_line'])
            self.assertIsNone(tracker.rows[-1]['area'])

        tracker = self.tracker()
        tracker.add(self.event(1, 0, 'area.enter', {'area': 'A'}))
        tracker.add(self.event(2, None, 'area.enter', {'area': 'B'}))
        tracker.add(self.event(3, 2, 'graph.deadlock'))

        self.assertIsNone(tracker.rows[-1]['area'])

    def test_series_respects_continuations_dates_spacing_and_nonmatching_branch(self):
        events = [{'line': line, 'timestamp': self.event(line, second, 'unknown')['timestamp'],
                   'text': text, 'level': 'ERROR', 'details': details}
                  for line, second, text, details in ((1, 0, 'A', []), (2, 0, 'A', []),
                      (3, 1, 'A', ['detail']), (4, 2, 'A', ['detail']), (5, 63, 'A', ['detail']),
                      (6, 86400, 'A', ['detail']), (7, None, 'A', ['detail']),
                      (8, 86401, 'B', []), (9, 86402, 'B', []), (10, 86402, 'C', []))]
        issues = {'groups': [{'code': 'unknown', 'category': 'client', 'events': events}]}
        contexts = [{'line': i, 'previous_line': i - 1} for i in range(2, 11)]
        contexts[-1]['previous_line'] = 8
        selection = ReportPeriodSelection(ReportPeriod(), 'UTC', ExecutionContext())
        sessions = SessionHistoryBuilder([], [], [], selection)
        original = deepcopy(issues)

        model = StabilityStatisticsBuilder.build(issues, contexts, sessions, selection)

        self.assertEqual(issues, original)
        self.assertEqual(sorted(len(group['rows']) for group in model['series'].values()), [1, 1, 1, 1, 1, 1, 2, 2])
        self.assertEqual(sum(day['count'] for day in model['by_date'].values()), 10)
        self.assertEqual(model['summary']['undated'], 1)
        self.assertEqual(sum(bar['count'] for bar in model['chart']['bars']), 9)
