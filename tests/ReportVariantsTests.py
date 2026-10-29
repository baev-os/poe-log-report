import hashlib
import json
import re
import unittest

from dataclasses import replace
from datetime import date
from contextlib import redirect_stderr, redirect_stdout

from io import StringIO

from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import patch

from PIL import Image
from pypdf import PdfReader

from poe_log_analyze.Bootstrap import Bootstrap
from poe_log_analyze.cli.ReportCli import ReportCli
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.request.ReportOutputs import ReportOutputs
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod
from poe_log_analyze.core.request.ReportRequest import ReportRequest
from poe_log_analyze.stages.rendering.BasicReportWriter import BasicReportWriter


class ReportVariantsTests(unittest.TestCase):
    """Independent outputs, simple HTML/PDF, and preservation of the complete set."""

    @classmethod
    def setUpClass(cls):
        cls.temp = TemporaryDirectory(dir = Path('build').resolve(), prefix = 'report-variants-')
        cls.root = Path(cls.temp.name)
        cls.source = cls.root / 'synthetic.log'
        cls.source.write_text(cls.source_text(), encoding = 'utf-8')
        cls.original = cls.source.read_bytes()
        cls.generator = Bootstrap.report_generator()
        cls.analysis = cls.generator.generate(ReportRequest((cls.source,), cls.root / 'analysis', mode = ReportMode.ANALYSIS)).directory

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @staticmethod
    def source_text():
        records = []

        for stamp, message in (
                ('2026/08/31 23:50:00', 'Client-Safe Instance ID = 1'),
                ('2026/08/31 23:50:01', 'Generating level 83 area "MapWorldsBeach" with seed 1'),
                ('2026/08/31 23:50:02', ': You have entered Synthetic Beach.'),
                ('2026/08/31 23:51:00', ': Hero (Witch) is now level 89'),
                ('2026/08/31 23:52:00', '@From PlayerOne: Before period'),
                ('2026/09/01 00:00:00', 'Sister Cassia: Synthetic observation.'),
                ('2026/09/01 00:01:00', ': Hero (Witch) is now level 90'),
                ('2026/09/01 00:02:00', 'Generating level 83 area "MapWorldsDunes" with seed 2'),
                ('2026/09/01 00:02:02', ': You have entered Synthetic Dunes.'),
                ('2026/09/01 00:03:00', '@From PlayerTwo: <script>danger & text</script>'),
                ('2026/09/01 00:04:00', 'Generating level 83 area "MapWorldsBeach" with seed 3'),
                ('2026/09/01 00:04:02', ': You have entered Synthetic Beach.'),
                ('2026/09/01 00:05:00', 'Generating level 83 area "Delve_Main" with seed 4'),
                ('2026/09/01 00:05:02', ': You have entered Synthetic Mine.'),
                ('2026/09/01 00:06:00', ': Hero (Witch) is now level 91'),
                ('2026/09/01 00:07:00', '@To PlayerOne: Reply'),
                ('2026/09/01 00:08:00', '#PlayerThree: Channel message'),
                ('2026/09/01 00:09:00', 'Abnormal disconnect: Synthetic end')):
            records.append(f'{stamp} 1 abcd [INFO Client 1] {message}\n')

        return ''.join(records)

    def export(self, name, outputs, language = 'ru', period = ReportPeriod()):
        return self.generator.generate(ReportRequest((self.analysis,), self.root / name,
            mode = ReportMode.EXPORT, outputs = outputs, report_language = language, period = period))

    def test_all_fifteen_nonempty_output_selections(self):
        for mask in range(1, 16):
            with self.subTest(mask = mask):
                outputs = ReportOutputs(*(bool(mask & (1 << index)) for index in range(4)))
                result = self.export('selection-' + str(mask), outputs)
                root = result.report_path.parent.parent
                manifest = json.loads((root / 'report-manifest.json').read_text(encoding = 'utf-8'))

                self.assertEqual(manifest['report_schema_version'], '40')
                self.assertEqual(manifest['outputs'], {
                    name: getattr(outputs, name) for name in ('basic', 'basic_pdf', 'extended', 'extended_pdf')})

                for profile in ('basic', 'extended'):
                    self.assertEqual((root / profile / 'public/index.html').is_file(), getattr(outputs, profile))
                    self.assertEqual((root / 'pdf' / profile / 'report.pdf').is_file(), getattr(outputs, profile + '_pdf'))

                    if not getattr(outputs, profile):
                        continue

                    for page in (root / profile / 'public').rglob('*.html'):
                        links = re.findall(r'<a class="report-pdf" href="([^"]+)" download="report.pdf"',
                                           page.read_text(encoding = 'utf-8'))

                        self.assertEqual(len(links), int(getattr(outputs, profile + '_pdf')), str(page))

                        if links:
                            self.assertEqual((page.parent / links[0]).resolve(),
                                             (root / 'pdf' / profile / 'report.pdf').resolve())

                self.assertEqual(self.source.read_bytes(), self.original)

    def test_basic_pages_localization_no_evidence_and_extended_first_block(self):
        for language in ('ru', 'en'):
            with self.subTest(language = language):
                result = self.export('language-' + language, ReportOutputs(True, True, True, True), language)
                root = result.report_path.parent.parent

                for prefix in ('basic/public', 'extended/public/basic'):
                    for page in BasicReportWriter.PAGES:
                        html = (root / prefix / page).read_text(encoding = 'utf-8')

                        self.assertIn(f'lang="{language}"', html)

                        for forbidden in ('#line-', 'technical/', 'input_sha256', 'Seed', 'coverage', '[i18n]'):
                            self.assertNotIn(forbidden, html)

                graphs = (root / 'basic/public/index.html').read_text(encoding = 'utf-8')

                self.assertLess(graphs.index('class="activity-overview"'), graphs.index('data-activity-chart'))
                self.assertIn('66,7 %' if language == 'ru' else '66.7 %',
                              (root / 'basic/public/maps/index.html').read_text(encoding = 'utf-8'))

                chat = (root / 'basic/public/conversations/index.html').read_text(encoding = 'utf-8')

                self.assertIn('&lt;script&gt;danger &amp; text&lt;/script&gt;', chat)
                self.assertIn('data-chat-sort', chat)
                self.assertIn('value="character"', chat)
                self.assertIn('value="channel"', chat)

                menu = (root / 'extended/public/index.html').read_text(encoding = 'utf-8')

                self.assertLess(menu.index('basic/index.html'), menu.index('playtime/index.html'))

                for asset in BasicReportWriter.STYLE_ASSETS:
                    self.assertEqual((root / 'basic/public' / asset).read_bytes(),
                                     (root / 'extended/public' / asset).read_bytes())

                for page in (root / 'basic/public').rglob('*.html'):
                    html = page.read_text(encoding = 'utf-8')

                    self.assertIn('data-bs-theme="dark"', html)
                    self.assertIn('class="report-shell basic-shell"', html)
                    self.assertIn('style.css', html)
                    self.assertIn('vendor/bootstrap.min.css', html)

                with Image.open(root / 'basic/public/images/activity-overview.png') as image:
                    self.assertEqual(image.width, 4800)
                    self.assertGreaterEqual(image.height, 640)

                basic = PdfReader(root / 'pdf/basic/report.pdf')
                extended = PdfReader(root / 'pdf/extended/report.pdf')
                text = '\n'.join(page.extract_text() for page in basic.pages)

                for label in (('Графики', 'Персонажи', 'Карты', 'Календарь', 'Разговоры') if language == 'ru'
                              else ('Charts', 'Characters', 'Maps', 'Calendar', 'Conversations')):
                    self.assertIn(label, text)

                self.assertNotIn('input_sha256', text)
                self.assertNotIn('Seed', text)
                self.assertGreater(len(extended.pages), len(basic.pages))

                landscape = [page for page in basic.pages if page.mediabox.width > page.mediabox.height]

                self.assertTrue(landscape)
                self.assertIn('Весь период' if language == 'ru' else 'Full period', landscape[0].extract_text())
                self.assertIn('danger & text', text)

    def test_period_filters_conversations_and_daily_totals(self):
        result = self.export('period', ReportOutputs(), period = ReportPeriod(date(2026, 9, 1), date(2026, 9, 1)))
        model = json.loads((result.report_path.parent.parent / 'project/data/basic.json').read_text(encoding = 'utf-8'))

        self.assertEqual([day['date'] for day in model['daily']], ['2026-09-01'])
        self.assertEqual(sum(day['seconds'] for day in model['daily']), model['seconds'])
        self.assertEqual(sum(week['seconds'] for week in model['weekly']), model['seconds'])
        self.assertEqual(model['daily'][-1]['cumulative_seconds'], model['seconds'])
        self.assertFalse(any(row['text'] == 'Before period' for row in model['messages']))
        self.assertEqual(len(model['messages']), 3)

    def test_pdf_failure_and_cancellation_preserve_all_previous_outputs(self):
        output = self.root / 'current/report'
        request = ReportRequest((self.source,), output, replace_report = True, outputs = ReportOutputs(True, True, True, True))

        self.generator.generate(request)
        before = self.hashes(output.parent)

        with patch('poe_log_analyze.stages.rendering.pdf.PdfReportWriter.PdfReportWriter.write', side_effect = OSError('Synthetic PDF failure')):
            with self.assertRaises(OSError):
                self.generator.generate(request)

        self.assertEqual(self.hashes(output.parent), before)

        self.cancelled = False
        self.pdf_stages = 0

        with self.assertRaises(GenerationCancelled):
            self.generator.generate(request, ExecutionContext(cancelled = self.is_cancelled, progress = self.cancel_on_pdf))

        self.assertEqual(self.hashes(output.parent), before)

        self.generator.generate(replace(request, outputs = ReportOutputs(False, True, False, False)))

        self.assertTrue((output / 'pdf/basic/report.pdf').is_file())
        self.assertFalse((output / 'basic').exists())
        self.assertFalse((output / 'extended').exists())
        self.assertFalse((output / 'pdf/extended').exists())

    def is_cancelled(self):
        return self.cancelled

    def cancel_on_pdf(self, update):
        if 'PDF' in update.stage:
            self.pdf_stages += 1
            self.cancelled = self.pdf_stages == 2

    @staticmethod
    def hashes(root):
        return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in root.rglob('*') if path.is_file() and not path.name.endswith('.lock')}

    def test_empty_period_and_export_without_source(self):
        self.source.unlink()

        try:
            result = self.export('empty', ReportOutputs(True, True, False, False),
                                 period = ReportPeriod(date(2030, 1, 1), date(2030, 1, 2)))
            root = result.report_path.parent.parent
            model = json.loads((root / 'project/data/basic.json').read_text(encoding = 'utf-8'))

            self.assertEqual(model['daily'], [])
            self.assertEqual(model['messages'], [])
            self.assertEqual(model['maps'], [])
            self.assertEqual(model['seconds'], 0)
            self.assertTrue(PdfReader(root / 'pdf/basic/report.pdf').pages)
        finally:
            self.source.write_bytes(self.original)

    def test_selection_validation(self):
        self.assertEqual(ReportOutputs(), ReportOutputs(True, True, False, False))

        with self.assertRaises(ValueError):
            ReportOutputs(False, False, False, False)

        with self.assertRaises(ValueError):
            ReportOutputs(1, True, False, False)

        with self.assertRaises(ValueError):
            ReportRequest((self.source,), self.root / 'invalid', mode = ReportMode.ANALYSIS, outputs = ReportOutputs())

    def test_cli_defaults_pdf_only_and_invalid_selections(self):
        for name, flags, expected in (
                ('cli-default', [], ReportOutputs()),
                ('cli-pdf-only', ['--no-basic', '--no-basic-pdf', '--extended-pdf'], ReportOutputs(False, False, False, True))):
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                status = ReportCli.main(['--result', str(self.analysis), '--output', str(self.root / name), *flags])

            self.assertEqual(status, 0)

            manifest = json.loads((self.root / name / 'report-manifest.json').read_text(encoding = 'utf-8'))

            self.assertEqual(manifest['outputs'], {key: getattr(expected, key)
                             for key in ('basic', 'basic_pdf', 'extended', 'extended_pdf')})

        for index, flags in enumerate((['--no-basic', '--no-basic-pdf'], ['--pdf', '--basic'])):
            output = self.root / ('cli-invalid-' + str(index))

            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertEqual(ReportCli.main(['--result', str(self.analysis), '--output', str(output), *flags]), 1)

            self.assertFalse(output.exists())

    def test_replacement_migrates_previous_single_report_and_root_pdf(self):
        output = self.root / 'migration/report'
        legacy = ReportRequest((self.source,), output, replace_report = True, generate_pdf = True)

        self.generator.generate(legacy)

        self.assertTrue((output.parent / 'report.pdf').is_file())

        self.generator.generate(replace(legacy, generate_pdf = False, outputs = ReportOutputs(True, False, False, False)))

        self.assertFalse((output.parent / 'report.pdf').exists())
        self.assertFalse((output / 'public/report.pdf').exists())
        self.assertTrue((output / 'basic/public/index.html').is_file())
        self.assertTrue((output.parent / 'index.html').is_file())
        self.assertFalse((output.parent / 'build').exists())
