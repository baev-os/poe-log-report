import json
import unittest

from copy import deepcopy
from datetime import date, datetime, timedelta
from decimal import Decimal

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

from poe_log_analyze.stages.composition.LoadingStatisticsBuilder import LoadingStatisticsBuilder


class LoadingStatisticsTests(unittest.TestCase):
    """Loading data preserves precision, provenance, and a shared HTML/PDF period."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @staticmethod
    def record(line, seconds, stamp = '2026-09-01T23:59:59+05:00', area = 'Dunes'):
        return {'line_number': line, 'record_id': line, 'status': 'recognized', 'type': 'loading.duration',
                'timestamp': stamp, 'fields': {'area': area, 'seconds': seconds}}

    @staticmethod
    def line(second, message, start = '2026-09-01T23:59:00'):
        stamp = datetime.fromisoformat(start) + timedelta(seconds = second)
        return f'{stamp:%Y/%m/%d %H:%M:%S} 1 abcd [INFO Client 1] {message}\n'

    @classmethod
    def fixture(cls):
        return '\n' * 500 + ''.join(cls.line(second, message) for second, message in (
            (0, '[LOADING SCREEN] (Unassigned) Duration = 0.25 seconds'),
            (1, ': You have entered Dunes.'),
            (2, '[LOADING SCREEN] (Dunes) Duration = 1.25 seconds'),
            (3, '[LOADING SCREEN] (Dunes) Duration = 3.75 seconds'),
            (4, '[LOADING SCREEN] (Dunes) Duration = 0 seconds'),
            (60, '[LOADING SCREEN] (Dunes) Duration = 2.5 seconds'),
            (61, '[LOADING SCREEN] (Area <script> & "synthetic") Duration = 0.5 seconds'),
            (70, 'Abnormal disconnect: An unexpected disconnection occurred.'),
        ))

    def source(self, name, text):
        path = self.root / name
        path.write_text(text, encoding = 'utf-8')

        return path

    def report(self, name, sources, **options):
        result = ReportGenerator().generate(ReportRequest(tuple(sources), self.root / name, **options))
        return result.report_path.parent

    @staticmethod
    def data(public, name = 'loading'):
        return json.loads((public.parent / 'project/data' / (name + '.json')).read_text())

    def test_decimal_statistics_exact_names_undated_and_no_input_mutation(self):
        builder = LoadingStatisticsBuilder(ReportPeriod(), 'Asia/Almaty', ExecutionContext())
        rows = [self.record(501, '0.1'), self.record(502, '0.2'), self.record(503, '0.3'),
                self.record(504, '4e-5', None, 'Dunes ')]
        original = deepcopy(rows)

        for row in rows:
            builder.add(row)

        builder.add({**rows[0], 'record_id': 400})
        builder.add({**rows[0], 'status': 'unknown'})
        model = builder.result()

        self.assertEqual(rows, original)
        self.assertEqual(model['summary']['count'], 4)
        self.assertEqual(Decimal(model['summary']['total_seconds']), Decimal('.60004'))
        self.assertEqual(Decimal(model['summary']['median_seconds']), Decimal('.15'))
        self.assertEqual(Decimal(model['summary']['mean_seconds']), Decimal('.15001'))
        self.assertEqual([row['area'] for row in model['areas']], ['Dunes', 'Dunes '])
        self.assertEqual(model['areas'][0]['median_seconds'], '0.2')
        self.assertEqual(model['areas'][1]['mean'], '0.00004')
        self.assertEqual(model['undated'], 1)
        self.assertEqual(len(model['chart']['points']), 3)
        self.assertEqual(model['slowest'], [2, 1, 0, 3])
        self.assertEqual(model['sessions'][0]['id'], None)
        self.assertEqual(model['rows'][0]['href'], 'events/page-2.html#line-501')

    def test_local_midnight_open_bounds_and_dst_coordinates(self):
        period = ReportPeriod(date(2026, 9, 1), date(2026, 9, 1))
        builder = LoadingStatisticsBuilder(period, 'Asia/Almaty', ExecutionContext())

        for row in [self.record(1, '1', '2026-08-31T19:00:00+00:00'),
                    self.record(2, '2', '2026-09-01T18:59:59+00:00'),
                    self.record(3, '3', '2026-09-01T19:00:00+00:00'), self.record(4, '4', None)]:
            builder.add(row)

        model = builder.result()

        self.assertEqual([row['line'] for row in model['rows']], [1, 2])
        self.assertEqual(model['days'][0]['date'], '2026-09-01')
        self.assertTrue(model['rows'][0]['timestamp'].endswith('+05:00'))

        dst = LoadingStatisticsBuilder(ReportPeriod(None, date(2026, 11, 1)), 'America/New_York', ExecutionContext())
        dst.add(self.record(2, '2', '2026-11-01T01:30:00-05:00'))
        dst.add(self.record(1, '1', '2026-11-01T01:30:00-04:00'))
        model = dst.result()

        self.assertEqual([row['line'] for row in model['rows']], [1, 2])
        self.assertEqual([point['x'] for point in model['chart']['points']], [70, 930])
        self.assertTrue(model['chart']['time_ticks'][0]['time'].endswith('-0400'))
        self.assertTrue(model['chart']['time_ticks'][-1]['time'].endswith('-0500'))

    def test_empty_single_zero_and_stable_top_twenty(self):
        builder = LoadingStatisticsBuilder(ReportPeriod(), 'UTC', ExecutionContext())
        empty = builder.result()

        self.assertEqual(empty['summary']['count'], 0)
        self.assertIsNone(empty['summary']['mean_seconds'])
        self.assertEqual(empty['chart']['points'], [])

        builder.add(self.record(1, '0'))
        single = builder.result()

        self.assertEqual(single['chart']['points'][0], {'index': 0, 'x': 500, 'y': 260})

        for line in range(2, 24):
            builder.add(self.record(line, '1'))

        model = builder.result()

        self.assertEqual([model['rows'][i]['line'] for i in model['slowest']], list(range(2, 22)))
        self.assertEqual(len(model['chart']['points']), 23)

    def test_full_export_copies_localization_pdf_and_links_after_500(self):
        source = self.source('synthetic.txt', self.fixture())
        original = source.read_bytes()

        for language, title in (('ru', 'Загрузки'), ('en', 'Loading screens')):
            public = self.report(language, (source, source), report_language = language, generate_pdf = True)
            model = self.data(public)

            self.assertEqual(model['summary']['count'], 6)
            self.assertEqual(Decimal(model['summary']['total_seconds']), Decimal('8.25'))
            self.assertEqual(model['summary']['total_seconds'], self.data(public, 'period_log_observations')['loading_seconds'])
            self.assertEqual([(row['date'], Decimal(row['total_seconds'])) for row in model['days']],
                             [('2026-09-01', Decimal('5.25')), ('2026-09-02', Decimal('3'))])
            self.assertEqual([Decimal(row['total_seconds']) for row in model['sessions']], [Decimal('8'), Decimal('.25')])
            self.assertEqual(model['sessions'][0]['total_seconds'], self.data(public, 'sessions')['rows'][0]['observations']['loading_seconds'])

            page = (public / 'loading/index.html').read_text()

            self.assertIn(title, page)
            self.assertIn('Area &lt;script&gt; &amp;', page)
            self.assertNotIn('Area <script>', page)
            self.assertEqual(page.count('<circle '), 6)

            pdf = '\n'.join(page.extract_text() for page in PdfReader(public / 'report.pdf', strict = True).pages)

            self.assertIn(title, pdf)
            self.assertIn('8.25', pdf)
            self.assertIn('Area <script>', pdf)

            for row in model['rows']:
                target, anchor = row['href'].split('#')

                self.assertNotEqual(target, 'events/index.html')
                self.assertIn(f'id="{anchor}"', (public / target).read_text())

                if row['session_href']:
                    self.assertTrue((public / row['session_href']).is_file())

        self.assertEqual(source.read_bytes(), original)

    def test_period_export_without_source_and_empty_period(self):
        source = self.source('synthetic.txt', self.fixture())

        public = self.report('full', (source,))
        analysis = public.parents[1] / 'analysis'
        source.unlink()

        selected = self.report('selected', (analysis,), mode = ReportMode.EXPORT,
                               period = ReportPeriod(date(2026, 9, 2), None))
        model = self.data(selected)

        self.assertEqual(model['summary']['count'], 2)
        self.assertEqual(model['summary']['total_seconds'], '3.0')
        self.assertEqual(model['summary']['total_seconds'], self.data(selected, 'period_log_observations')['loading_seconds'])

        empty = self.report('empty', (analysis,), mode = ReportMode.EXPORT,
                            period = ReportPeriod(date(2027, 1, 1), None), generate_pdf = True)

        self.assertEqual(self.data(empty)['summary']['count'], 0)
        self.assertIn('No loading duration messages in the selected period.', (empty / 'loading/index.html').read_text())

    def test_shared_prefix_and_independent_equal_clocks_keep_session_membership(self):
        prefix = self.line(0, ': You have entered Dunes.') + self.line(1, '[LOADING SCREEN] (Dunes) Duration = 1 seconds')
        first = self.source('one.txt', prefix + self.line(2, '[LOADING SCREEN] (Dunes) Duration = 2 seconds')
                            + self.line(10, 'Abnormal disconnect: An unexpected disconnection occurred.'))
        second = self.source('two.txt', prefix + self.line(3, '[LOADING SCREEN] (Dunes) Duration = 3 seconds')
                             + self.line(12, 'Abnormal disconnect: An unexpected disconnection occurred.'))
        third = self.source('three.txt', self.line(0, ': You have entered Synthetic Other.')
                            + self.line(1, '[LOADING SCREEN] (Synthetic Other) Duration = 4 seconds')
                            + self.line(10, 'Abnormal disconnect: An unexpected disconnection occurred.'))
        model = self.data(self.report('branches', (first, second, third)))

        self.assertEqual(model['summary']['count'], 4)
        self.assertEqual(model['summary']['total_seconds'], '10')
        self.assertEqual(sorted(row['total_seconds'] for row in model['sessions']), ['4', '6'])
        self.assertTrue(all(row['id'] is not None for row in model['sessions']))

    def test_cancelled_projection_preserves_current_report_and_removes_work(self):
        source = self.source('synthetic.txt', self.fixture())
        request = ReportRequest((source,), self.root / 'report', replace_report = True)

        ReportGenerator().generate(request)
        old = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}

        with patch.object(LoadingStatisticsBuilder, 'add', side_effect = GenerationCancelled('Синтетическая отмена')):
            with self.assertRaises(GenerationCancelled):
                ReportGenerator().generate(request)

        self.assertEqual(old, {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()})

        control = ExecutionContext(cancelled = lambda: True)

        with self.assertRaises(GenerationCancelled):
            LoadingStatisticsBuilder(ReportPeriod(), 'UTC', control).result()
