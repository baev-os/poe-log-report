import json
import unittest

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from dataclasses import FrozenInstanceError
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

from poe_log_analyze.stages.composition.CharacterProgressionBuilder import CharacterProgressionBuilder
from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection


class ReportPeriodTests(unittest.TestCase):
    """Shared dates constrain calculations while retaining full evidence and the previous level."""

    @staticmethod
    def selection(start = '2026-09-01', end = '2026-09-01', zone = 'Asia/Almaty', control = None):
        return ReportPeriodSelection(ReportPeriod(date.fromisoformat(start) if start else None,
                                                 date.fromisoformat(end) if end else None),
                                     zone, control or ExecutionContext())

    @staticmethod
    def line(stamp, message):
        return f'{stamp} 1 abcd [INFO Client 1] {message}\n'

    @classmethod
    def source(cls):
        return '\n' * 500 + ''.join(cls.line(stamp, message) for stamp, message in [
            ('2026/08/31 23:59:49', 'Client-Safe Instance ID = 1'),
            ('2026/08/31 23:59:50', 'Generating level 80 area "MapWorldsDunes" with seed 1'),
            ('2026/08/31 23:59:51', ': You have entered Dunes.'),
            ('2026/08/31 23:59:52', 'Sister Cassia: Synthetic first dialogue.'),
            ('2026/08/31 23:59:53', ': SyntheticHero (Duelist) is now level 89'),
            ('2026/08/31 23:59:54', ': 100 Items identified'),
            ('2026/09/01 00:00:01', 'Sister Cassia: Synthetic repeated dialogue.'),
            ('2026/09/01 00:00:02', ': SyntheticHero (Duelist) is now level 90'),
            ('2026/09/01 00:00:03', ': 7 Items identified'),
            ('2026/09/01 00:00:04', '[LOADING SCREEN] (Dunes) Duration = 1.25 seconds'),
            ('2026/09/01 00:00:05', 'Generating level 1 area "HideoutOssuary" with seed 2'),
            ('2026/09/01 00:00:06', ': You have entered Hideout.'),
            ('2026/09/01 00:00:10', 'Client-Safe Instance ID = 1'),
            ('2026/09/01 00:00:11', 'Generating level 80 area "MapWorldsDunes" with seed 1'),
            ('2026/09/01 00:00:12', ': You have entered Dunes.'),
            ('2026/09/01 00:00:13', 'The Maven: Synthetic period dialogue.'),
            ('2026/09/01 00:00:14', ': SyntheticHero (Duelist) is now level 91'),
            ('2026/09/01 00:00:20', 'Generating level 1 area "HideoutOssuary" with seed 2'),
            ('2026/09/01 00:00:20', 'Abnormal disconnect: An unexpected disconnection occurred.'),
            ('2026/09/02 00:00:00', ': SyntheticHero (Duelist) is now level 92'),
            ('2026/09/02 00:00:01', ': 1000 Items identified'),
        ])

    def test_inclusive_dates_open_bounds_validation_and_immutability(self):
        selected = self.selection().period

        self.assertTrue(selected.contains('2026-08-31T19:00:00+00:00', 'Asia/Almaty'))
        self.assertTrue(selected.contains('2026-09-01T18:59:59+00:00', 'Asia/Almaty'))
        self.assertFalse(selected.contains('2026-09-01T19:00:00+00:00', 'Asia/Almaty'))
        self.assertFalse(selected.contains(None, 'Asia/Almaty'))
        self.assertFalse(selected.contains('2026-09-01T01:00:00', 'Asia/Almaty'))
        self.assertTrue(self.selection(None).period.contains('2020-01-01T00:00:00Z', 'UTC'))
        self.assertTrue(self.selection(end = None).period.contains('2030-01-01T00:00:00Z', 'UTC'))
        self.assertTrue(ReportPeriod().contains(None, 'UTC'))

        with self.assertRaises(FrozenInstanceError):
            selected.date_to = None

        for start, end in ((date(2026, 9, 2), date(2026, 9, 1)), ('2026-09-01', None), (None, date.max)):
            with self.assertRaises(ValueError):
                ReportPeriod(start, end)

        with self.assertRaises(ValueError):
            ReportRequest((Path('synthetic.txt'),), Path('build/synthetic'), mode = ReportMode.ANALYSIS, period = selected)

    def test_clipping_midnight_dst_zero_and_missing_boundaries(self):
        selected = self.selection()

        self.assertEqual(selected.clip('2026-08-31T23:59:50+05:00', '2026-09-01T00:00:10+05:00')[2], 10)
        self.assertIsNone(selected.clip('2026-08-31T23:59:50+05:00', '2026-09-01T00:00:00+05:00'))
        self.assertEqual(selected.clip('2026-09-01T00:00:00+05:00', '2026-09-01T00:00:00+05:00')[2], 0)
        self.assertIsNone(selected.clip('2026-09-02T00:00:00+05:00', '2026-09-02T00:00:00+05:00'))

        for day, hours in (('2026-03-29', 23), ('2026-10-25', 25)):
            selection = self.selection(day, day, 'Europe/Berlin')
            bounds = selection.clip(day[:8] + '01T00:00:00Z', day[:8] + '31T00:00:00Z')

            self.assertEqual(bounds[2], hours * 3600)
            self.assertEqual((selection.end - selection.start).total_seconds(), hours * 3600)

        visit = {'entered_at': '2026-09-01T00:00:00+05:00', 'ended_at': None, 'bounded': False, 'seconds': None}

        self.assertIsNone(selected.visit(dict(visit, entered_at = None)))
        self.assertIsNone(selected.visit(dict(visit, entered_at = '2026-08-31T23:59:59+05:00')))
        self.assertIsNone(selected.visit(visit)['seconds'])

        original = deepcopy(visit)
        selected.visit(visit)

        self.assertEqual(visit, original)

        measured = dict(visit, entered_at = '2026-08-31T23:59:55+05:00', ended_at = '2026-09-01T00:00:05+05:00',
                        bounded = True, seconds = 10, afk_seconds = 10)
        original = deepcopy(measured)
        clipped = selected.visit(measured)

        self.assertEqual(clipped['seconds'], 5)
        self.assertEqual(clipped['original_entered_at'], original['entered_at'])
        self.assertIsNone(clipped['afk_seconds'])
        self.assertEqual(measured, original)

    def test_level_delta_keeps_baseline_outside_period(self):
        events = [{'line_number': line, 'timestamp': stamp, 'type': 'screen.level_up',
                   'message': {'fields': {'character': 'Hero', 'class': 'Duelist', 'level': str(level)}}}
                  for line, stamp, level in [
                      (1, '2026-08-31T23:59:50+05:00', 90), (2, '2026-09-01T00:00:01+05:00', 90),
                      (3, '2026-09-01T00:00:10+05:00', 91), (4, '2026-09-02T00:00:00+05:00', 92)]]
        timeline = {'timezone': 'Asia/Almaty', 'days': [{'date': 'synthetic'}], 'by_date': {'synthetic': {'events': events}}}

        result = CharacterProgressionBuilder.build(timeline, ExecutionContext(), period = self.selection().period)
        events = result['characters'][0]['events']

        self.assertEqual([event['level'] for event in events], [90, 91])
        self.assertEqual(events[1]['delta_seconds'], 20)
        self.assertEqual(events[1]['delta_from_level'], 90)

    def test_report_period_shared_by_html_pdf_and_preserves_source_context(self):
        with TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp') as temporary:
            root = Path(temporary)
            source = root / 'synthetic.txt'
            source.write_text(self.source())
            original = source.read_bytes()

            for language in ('ru', 'en'):
                result = ReportGenerator().generate(ReportRequest((source, source), root / language,
                    report_language = language, generate_pdf = True, period = self.selection().period))
                public = result.report_path.parent
                data = public.parent / 'project/data'
                summary = json.loads((data / 'statistics_summary.json').read_text())

                self.assertEqual((summary['maps']['count'], summary['maps']['visits'], summary['maps']['seconds']), (1, 2, 13))
                self.assertEqual(json.loads((data / 'activity.json').read_text())['seconds'], 20)
                self.assertEqual(summary['zone_totals']['seconds'], 18)

                daily = json.loads((data / 'daily_playtime.json').read_text())

                self.assertEqual([(d['date'], d['seconds']) for d in daily['days']], [('2026-09-01', 20)])

                observations = json.loads((data / 'map_observations.json').read_text())

                self.assertEqual(observations['map_count'], 1)
                self.assertEqual({row['code']: row['count'] for row in observations['rows'] if row['count']}, {'blight': 1, 'maven': 1})

                evidence = next(group for group in observations['groups'] if group['code'] == 'blight')['months'][0]['days'][0]['rows'][0]

                self.assertEqual(evidence['date'], '2026-09-01')
                self.assertEqual(evidence['evidence'][0]['href'], 'events/page-2.html#line-507')
                self.assertIn('technical/maps/2026-08-31/', evidence['map_href'])
                self.assertEqual(json.loads((data / 'period_log_observations.json').read_text())['items_identified'], 7)
                self.assertEqual(json.loads((data / 'log_observations.json').read_text())['items_identified'], 1107)

                characters = json.loads((data / 'characters.json').read_text())['characters'][0]['events']

                self.assertEqual([e['level'] for e in characters], [90, 91])
                self.assertEqual([e['delta_seconds'] for e in characters], [9, 12])
                self.assertIn('2026-09-02', json.loads((data / 'timeline.json').read_text())['by_date'])
                self.assertIn('Synthetic first dialogue.', (public / 'events/page-2.html').read_text())
                self.assertIn('2026-09-01 — 2026-09-01', (public / 'statistics/index.html').read_text())

                pdf = PdfReader(public / 'report.pdf')
                text = '\n'.join(page.extract_text() for page in pdf.pages)

                self.assertIn('2026-09-01 — 2026-09-01', text)
                self.assertIn('00:00:20', text)
                self.assertIn('00:00:09', text)
                self.assertNotIn('1107', text)

                manifest = json.loads((public.parent / 'report-manifest.json').read_text())

                self.assertEqual(manifest['report_period']['end_exclusive'], '2026-09-01T19:00:00+00:00')
                self.assertIn('report_period', manifest['views_sha256'])
                self.assertEqual(source.read_bytes(), original)

    def test_export_empty_period_invalid_cli_and_cancellation(self):
        with TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp') as temporary:
            root = Path(temporary)
            source = root / 'synthetic.txt'
            source.write_text(self.source())

            ReportGenerator().generate(ReportRequest((source,), root / 'analysis', mode = ReportMode.ANALYSIS))
            source.unlink()
            args = ['--result', str(root / 'analysis'), '--output', str(root / 'report'), '--pdf']

            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertEqual(ReportCli.main([*args, '--date-from', '2026-09-02', '--date-to', '2026-09-01']), 1)
                self.assertFalse((root / 'report').exists())
                self.assertEqual(ReportCli.main([*args, '--date-from', 'invalid']), 1)
                self.assertEqual(ReportCli.main([*args, '--date-from', '2030-01-01']), 0)

            data = root / 'report/project/data'

            self.assertEqual(json.loads((data / 'statistics_summary.json').read_text())['maps']['count'], 0)
            self.assertEqual(json.loads((data / 'daily_playtime.json').read_text())['days'], [])
            self.assertTrue((root / 'report/public/report.pdf').is_file())

        with self.assertRaises(GenerationCancelled):
            self.selection(control = ExecutionContext(cancelled = lambda: True)).runs([{'visits': []}])

    def test_diverging_prefixes_keep_period_evidence_with_its_source(self):
        with TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp') as temporary:
            root = Path(temporary)
            first, second = root / 'one.txt', root / 'two.txt'
            prefix = ''.join(self.source().splitlines(keepends = True)[:507])
            ending = self.line('2026/09/01 00:00:05', 'Generating level 1 area "HideoutOssuary" with seed 2')
            first.write_text(prefix + self.line('2026/09/01 00:00:03', 'The Maven: Synthetic first branch.') + ending)
            second.write_text(prefix + self.line('2026/09/01 00:00:04', 'Oshabi: Synthetic second branch.') + ending)

            result = ReportGenerator().generate(ReportRequest((first, second), root / 'report', period = self.selection().period))
            data = result.report_path.parent.parent / 'project/data'
            summary = json.loads((data / 'map_observations.json').read_text())

            self.assertEqual(summary['map_count'], 1)
            self.assertEqual({row['code']: row['count'] for row in summary['rows'] if row['count']},
                             {'blight': 1, 'maven': 1, 'harvest': 1})

            maps = json.loads((data / 'maps.json').read_text())['by_date']['2026-08-31']['runs']

            self.assertEqual(len(maps), 1)

            branches = maps[0]['visits'][0]['branches']

            self.assertEqual(sorted([item['code'] for item in branch['period_observations']['mechanics']]
                                    for branch in branches), [['blight', 'harvest'], ['blight', 'maven']])

            harvest = next(group for group in summary['groups'] if group['code'] == 'harvest')
            href = harvest['months'][0]['days'][0]['rows'][0]['evidence'][0]['href']

            self.assertEqual(href, 'events/page-2.html#line-510')
