import json
import unittest

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from datetime import date
from io import StringIO

from pathlib import Path
from tempfile import TemporaryDirectory

from pypdf import PdfReader

from poe_log_analyze.cli.ReportCli import ReportCli

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.stages.composition.PeriodComparisonBuilder import PeriodComparisonBuilder
from poe_log_analyze.stages.composition.MapPaceBuilder import MapPaceBuilder
from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection
from poe_log_analyze.stages.composition.sessions.SessionHistoryBuilder import SessionHistoryBuilder
from poe_log_analyze.stages.composition.localization.ComparisonPresenter import ComparisonPresenter
from poe_log_analyze.stages.composition.localization.TranslationCatalogue import TranslationCatalogue


class PeriodComparisonTests(unittest.TestCase):
    """Independent slices, normalization, and equal HTML/PDF values."""

    ROOT = Path(__file__).resolve().parents[1]
    A = ReportPeriod(date(2026, 8, 30), date(2026, 8, 31))
    B = ReportPeriod(date(2026, 9, 1), date(2026, 9, 1))

    @staticmethod
    def source():
        # Shared synthetic scenario: midnight, returns, duplicates, and pagination.
        from ReportPeriodTests import ReportPeriodTests
        return ReportPeriodTests.source()

    @staticmethod
    def load(public, name):
        return json.loads((public.parent / 'project/data' / (name + '.json')).read_text())

    @staticmethod
    def row(model, code):
        return next(row for section in model['sections'] for row in section['rows'] if row['code'] == code)

    def assert_pace_matches(self, snapshot, pace):
        for comparison_key, pace_key in (('map_count', 'count'), ('new_maps', 'new'), ('map_returns', 'returns'),
                                        ('map_seconds', 'map_seconds'), ('play_seconds', 'play_seconds'),
                                        ('maps_per_hour', 'rate'), ('mean_map_seconds', 'mean_seconds'),
                                        ('measured_maps', 'complete'), ('excluded_maps', 'excluded')):
            self.assertEqual(snapshot[comparison_key], pace[pace_key], comparison_key)

        self.assertEqual(snapshot['maps_per_day'], pace['new'] / snapshot['days'])

    def test_each_period_matches_pace_after_midnight_and_returns(self):
        from MapPaceTests import MapPaceTests

        with TemporaryDirectory(dir = self.ROOT / 'build/tmp') as temporary:
            root = Path(temporary)
            source = root / 'synthetic.txt'
            source.write_text(MapPaceTests.fixture())
            a = ReportPeriod(date(2026, 9, 1), date(2026, 9, 1))
            b = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2))

            result = ReportGenerator().generate(ReportRequest((source, source), root / 'both', period = b, comparison_period = a))
            model = self.load(result.report_path.parent, 'period_comparison')

            self.assertEqual(model['version'], '4')
            self.assertEqual((model['b']['map_count'], model['b']['new_maps'], model['b']['map_returns']), (2, 1, 1))
            self.assertEqual((model['b']['maps_per_hour'], model['b']['mean_map_seconds']), (20, 60))
            self.assertEqual((model['b']['measured_maps'], model['b']['excluded_maps']), (1, 1))
            self.assert_pace_matches(model['b'], self.load(result.report_path.parent, 'map_pace')['summary'])

            source.unlink()

            baseline = ReportGenerator().generate(ReportRequest((root / 'both/analysis',), root / 'baseline',
                                                                mode = ReportMode.EXPORT, period = a))

            self.assert_pace_matches(model['a'], self.load(baseline.report_path.parent, 'map_pace')['summary'])

    def test_duration_exclusions_and_zero_agree_with_pace(self):
        start, end = '2026-09-01T00:00:00+05:00', '2026-09-01T00:00:10+05:00'
        visit = {'entry_line': 1, 'entered_at': start, 'ended_at': end, 'seconds': 10, 'bounded': True}
        base = {'id': 'one', 'area_id': 'MapWorldsDunes', 'kind_code': 'map', 'name': 'Dunes',
                'first_line': 1, 'date': '2026-09-01', 'started_at': start, 'identity_complete': True, 'visits': [visit]}
        cases = ((base, 10, None), (dict(base, branched = True), None, 'branched'),
                 (dict(base, identity_complete = False), None, 'identity'),
                 (dict(base, visits = [dict(visit, ended_at = None, seconds = None, bounded = False)]), None, 'incomplete'),
                 (dict(base, visits = [dict(visit, ended_at = start, seconds = 0)]), 0, None),
                 (dict(base, visits = [visit, dict(visit, entry_line = 20)]), None, 'multiple_sessions'))
        definitions = [{'first_line': first, 'line_ranges': [[first, first + 9]], 'branches': []} for first in (1, 20)]
        intervals = [{'first_line': first, 'started_at': start, 'ended_at': end, 'seconds': 10, 'incomplete': False}
                     for first in (1, 20)]
        selection = ReportPeriodSelection(self.B, 'Asia/Almaty', ExecutionContext())

        for run, expected, reason in cases:
            with self.subTest(reason = reason, expected = expected):
                before = deepcopy(run)
                selected = selection.runs([run])
                sessions = SessionHistoryBuilder(definitions, intervals, selected, selection)
                row = MapPaceBuilder.record(run, selected[0], selection, sessions)
                pace = MapPaceBuilder.statistics([row], 20)
                snapshot = PeriodComparisonBuilder.snapshot([run], intervals, 'Asia/Almaty', self.B,
                    {'loading_seconds': '0', 'loading_count': 0}, 'period_observations', ExecutionContext(), definitions)

                self.assert_pace_matches(snapshot, pace)
                self.assertEqual(snapshot['mean_map_seconds'], expected)
                self.assertEqual(row['excluded'], [reason] if reason else [])
                self.assertEqual(run, before)

    def test_request_requires_four_dates_and_allows_overlap(self):
        args = ((Path('synthetic.txt'),), Path('build/synthetic'))

        self.assertIsNone(ReportRequest(*args).comparison_period)
        self.assertEqual(ReportRequest(*args, period = self.B, comparison_period = self.B).comparison_period, self.B)

        for period, baseline in ((ReportPeriod(), self.A), (self.B, ReportPeriod()),
                                 (ReportPeriod(self.B.date_from), self.A),
                                 (self.B, ReportPeriod(None, self.A.date_to)), (self.B, 'invalid')):
            with self.assertRaises(ValueError):
                ReportRequest(*args, period = period, comparison_period = baseline)

        with self.assertRaises(ValueError):
            ReportRequest(*args, mode = ReportMode.ANALYSIS, comparison_period = self.A)

    def test_zero_baseline_missing_values_signed_deltas_and_rounding(self):
        row = PeriodComparisonBuilder.row('test', 'test', 'number', 0, 10)

        self.assertEqual(row['delta'], 10)
        self.assertIsNone(row['change_percent'])
        self.assertIsNone(PeriodComparisonBuilder.row('test', 'test', 'number', None, 10)['delta'])

        row = PeriodComparisonBuilder.row('test', 'test', 'share', 50, 75)

        self.assertEqual((row['delta'], row['change_percent']), (25, 50))

        row = PeriodComparisonBuilder.row('test', 'test', 'number', 10, 0)

        self.assertEqual((row['delta'], row['change_percent']), (-10, -100))

        for language in ('ru', 'en'):
            presenter = ComparisonPresenter(TranslationCatalogue(language, self.ROOT))

            self.assertEqual(presenter.format(None, 'duration'), '—')
            self.assertEqual(presenter.format(-.001, 'number', signed = True), '0')
            self.assertEqual(presenter.format(1.005, 'number'), '1,01' if language == 'ru' else '1.01')
            self.assertEqual(presenter.format(-90061.25, 'duration', signed = True),
                             '−25:01:01,25' if language == 'ru' else '−25:01:01.25')
            self.assertEqual(presenter.format(25, 'share', signed = True), '+25 п.п.' if language == 'ru' else '+25 pp')
            self.assertEqual(presenter.format(50, 'percent', signed = True), '+50 %')

    def test_calendar_days_and_utc_duration_for_dst(self):
        counters = {'loading_seconds': '0', 'loading_count': 0}

        for day, hours in ((date(2026, 3, 29), 23), (date(2026, 10, 25), 25)):
            interval = {'first_line': 1, 'started_at': f'{day:%Y-%m}-01T00:00:00Z',
                        'ended_at': f'{day:%Y-%m}-31T23:59:59Z', 'seconds': 0, 'incomplete': False}
            result = PeriodComparisonBuilder.snapshot([], [interval], 'Europe/Berlin', ReportPeriod(day, day),
                                                       counters, 'period_observations', ExecutionContext(), [])

            self.assertEqual(result['days'], 1)
            self.assertEqual(result['play_per_day'], hours * 3600)
            self.assertIsNone(result['mean_map_seconds'])
            self.assertEqual(result['maps_per_hour'], 0)

    def test_mean_uses_measured_runs_and_preserves_input(self):
        start = '2026-09-01T00:00:00+05:00'
        measured = {'entry_line': 1, 'entered_at': start, 'ended_at': '2026-09-01T00:00:10+05:00',
                    'seconds': 10, 'bounded': True}
        missing = dict(measured, entry_line = 3, ended_at = None, seconds = None, bounded = False)
        run = {'id': 'one', 'area_id': 'MapWorldsDunes', 'kind_code': 'map', 'name': 'Dunes',
               'first_line': 1, 'date': '2026-09-01', 'started_at': start, 'identity_complete': True,
               'visits': [measured]}
        runs = [run, dict(run, id = 'two', first_line = 2, visits = [dict(measured, entry_line = 2), missing])]
        original = deepcopy(runs)
        result = PeriodComparisonBuilder.snapshot(runs, [], 'Asia/Almaty', self.B,
            {'loading_seconds': '0', 'loading_count': 0}, 'period_observations', ExecutionContext(), [])

        self.assertEqual((result['map_count'], result['map_seconds']), (2, 20))
        self.assertEqual((result['measured_maps'], result['excluded_maps'], result['mean_map_seconds']), (1, 1, 10))
        self.assertIsNone(result['maps_per_hour'])
        self.assertEqual(runs, original)

    def test_ru_en_html_pdf_compare_independent_periods_after_deduplication(self):
        with TemporaryDirectory(dir = self.ROOT / 'build/tmp') as temporary:
            root = Path(temporary)
            source = root / 'synthetic.txt'
            source.write_text(self.source())
            original = source.read_bytes()

            for language in ('ru', 'en'):
                result = ReportGenerator().generate(ReportRequest((source, source), root / language,
                    period = self.B, comparison_period = self.A, report_language = language, generate_pdf = True))
                public = result.report_path.parent
                model = self.load(public, 'period_comparison')
                a, b = model['a'], model['b']

                self.assert_pace_matches(b, self.load(public, 'map_pace')['summary'])
                self.assertEqual((a['new_maps'], b['new_maps']), (1, 0))
                self.assertFalse(model['overlap'])
                self.assertEqual((a['days'], b['days']), (2, 1))
                self.assertEqual((a['play_seconds'], b['play_seconds']), (9, 20))
                self.assertEqual((a['play_per_day'], b['play_per_day']), (4.5, 20))
                self.assertEqual((a['map_count'], b['map_count']), (1, 1))
                self.assertEqual((a['maps_per_hour'], b['maps_per_hour']), (400, 0))
                self.assertEqual((a['maps_per_day'], b['maps_per_day']), (.5, 0))
                self.assertEqual((a['mean_map_seconds'], b['mean_map_seconds']), (None, None))
                self.assertEqual((a['loading_seconds'], b['loading_seconds']), (0, 1.25))
                self.assertEqual((a['loading_count'], b['loading_count']), (0, 1))
                self.assertEqual((a['observation_maps'], b['observation_maps']), (1, 1))
                self.assertEqual((a['mechanics']['blight'], b['mechanics']['blight']), (1, 1))
                self.assertEqual((a['mechanics']['maven'], b['mechanics']['maven']), (0, 1))
                self.assertEqual((sum(a['zones'].values()), sum(b['zones'].values())), (9, 18))
                self.assertAlmostEqual(self.row(model, 'play_seconds')['change_percent'], 11 / 9 * 100)
                self.assertIsNone(self.row(model, 'maven')['change_percent'])
                self.assertEqual(self.row(model, 'maven')['delta'], 100)
                self.assertEqual(self.load(public, 'activity')['seconds'], b['play_seconds'])
                self.assertEqual(self.load(public, 'statistics_summary')['maps']['seconds'], b['map_seconds'])
                self.assertEqual(self.load(public, 'comparison_log_observations')['items_identified'], 100)
                self.assertEqual(self.load(public, 'period_log_observations')['items_identified'], 7)
                self.assertEqual(self.load(public, 'log_observations')['items_identified'], 1107)

                html = (public / 'comparison/index.html').read_text()
                pdf = '\n'.join(page.extract_text() for page in PdfReader(public / 'report.pdf').pages)

                for text in ('2026-08-30 — 2026-08-31', '2026-09-01 — 2026-09-01', '+00:00:11', '−400'):
                    self.assertIn(text, html)
                    self.assertIn(text, pdf)

                manifest = json.loads((public.parent / 'report-manifest.json').read_text())

                self.assertEqual(manifest['comparison_period']['date_from'], '2026-08-30')
                self.assertIn('period_comparison', manifest['views_sha256'])
                self.assertEqual(manifest['pdf']['content_version'], '12')
                self.assertEqual(source.read_bytes(), original)

    def test_export_without_source_overlap_empty_period_and_invalid_cli(self):
        with TemporaryDirectory(dir = self.ROOT / 'build/tmp') as temporary:
            root = Path(temporary)
            source = root / 'synthetic.txt'
            source.write_text(self.source())

            ReportGenerator().generate(ReportRequest((source,), root / 'analysis', mode = ReportMode.ANALYSIS))
            source.unlink()
            args = ['--result', str(root / 'analysis'), '--output', str(root / 'report')]

            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertEqual(ReportCli.main([*args, '--compare-from', '2026-09-01']), 1)
                self.assertEqual(ReportCli.main([*args, '--compare-from', 'invalid']), 1)
                self.assertFalse((root / 'report').exists())
                self.assertEqual(ReportCli.main([*args, '--date-from', '2026-09-01', '--date-to', '2026-09-01',
                    '--compare-from', '2026-09-01', '--compare-to', '2026-09-01', '--pdf']), 0)

            public = root / 'report/public'
            model = self.load(public, 'period_comparison')

            self.assertTrue(model['overlap'])
            self.assertEqual(model['a'], model['b'])
            self.assert_pace_matches(model['b'], self.load(public, 'map_pace')['summary'])
            self.assertEqual(self.row(model, 'blight')['delta'], 0)

            empty = ReportPeriod(date(2030, 1, 1), date(2030, 1, 2))

            result = ReportGenerator().generate(ReportRequest((root / 'analysis',), root / 'empty',
                mode = ReportMode.EXPORT, period = empty, comparison_period = self.B, generate_pdf = True))
            model = self.load(result.report_path.parent, 'period_comparison')

            self.assertEqual(model['b']['map_count'], 0)
            self.assert_pace_matches(model['b'], self.load(result.report_path.parent, 'map_pace')['summary'])
            self.assertIsNone(model['b']['mean_map_seconds'])
            self.assertIsNone(self.row(model, 'blight')['delta'])
            self.assertEqual(self.row(model, 'play_seconds')['change_percent'], -100)

            result = ReportGenerator().generate(ReportRequest((root / 'analysis',), root / 'plain', mode = ReportMode.EXPORT))

            self.assertFalse(self.load(result.report_path.parent, 'period_comparison')['enabled'])
            self.assertFalse((result.report_path.parent / 'comparison').exists())
            self.assertNotIn('comparison/index.html', result.report_path.read_text())

    def test_diverging_copies_keep_each_periods_evidence(self):
        from ReportPeriodTests import ReportPeriodTests

        with TemporaryDirectory(dir = self.ROOT / 'build/tmp') as temporary:
            root = Path(temporary)
            first, second = root / 'one.txt', root / 'two.txt'
            prefix = ''.join(self.source().splitlines(keepends = True)[:507])
            ending = ReportPeriodTests.line('2026/09/01 00:00:05', 'Generating level 1 area "HideoutOssuary" with seed 2')
            first.write_text(prefix + ReportPeriodTests.line('2026/09/01 00:00:03', 'The Maven: Synthetic branch.') + ending)
            second.write_text(prefix + ReportPeriodTests.line('2026/09/01 00:00:04', 'Oshabi: Synthetic branch.') + ending)

            result = ReportGenerator().generate(ReportRequest((first, second), root / 'report',
                                                              period = self.B, comparison_period = self.A))
            model = self.load(result.report_path.parent, 'period_comparison')

            self.assert_pace_matches(model['b'], self.load(result.report_path.parent, 'map_pace')['summary'])
            self.assertEqual(model['b']['measured_maps'], 0)
            self.assertEqual((model['a']['observation_maps'], model['b']['observation_maps']), (1, 1))
            self.assertEqual((model['a']['mechanics']['maven'], model['b']['mechanics']['maven']), (0, 1))
            self.assertEqual((model['a']['mechanics']['harvest'], model['b']['mechanics']['harvest']), (0, 1))
            self.assertEqual((model['a']['mechanics']['blight'], model['b']['mechanics']['blight']), (1, 1))

    def test_cancellation_before_build(self):
        with self.assertRaises(GenerationCancelled):
            PeriodComparisonBuilder.build([], [], 'UTC', self.A, self.B, {}, {}, ExecutionContext(cancelled = lambda: True), [])
