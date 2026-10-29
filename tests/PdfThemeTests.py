import json
import unittest
import ReportVariantsTests

from contextlib import redirect_stdout
from io import StringIO

from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image
from pypdf import PdfReader
from pypdf.generic import ContentStream

from poe_log_analyze.Bootstrap import Bootstrap
from poe_log_analyze.cli.ReportCli import ReportCli
from poe_log_analyze.core.request.ReportOutputs import ReportOutputs
from poe_log_analyze.core.request.ReportRequest import ReportRequest
from poe_log_analyze.stages.rendering.ReportPalette import ReportPalette


class PdfThemeTests(unittest.TestCase):
    """One theme for both PDFs and PNG in both languages and without original logs."""

    def setUp(self):
        self.temp = TemporaryDirectory(dir = Path('build').resolve(), prefix = 'pdf-theme-')
        self.root = Path(self.temp.name)
        self.source = self.root / 'synthetic.log'
        self.source.write_text(ReportVariantsTests.ReportVariantsTests.source_text(), encoding = 'utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def test_both_pdf_and_images_use_shared_theme_and_contain_weekly_profile(self):
        for language in ('ru', 'en'):
            for dark in (False, True):
                with self.subTest(language = language, dark = dark):
                    result = Bootstrap.report_generator().generate(ReportRequest((self.source,), self.root / f'{language}-{dark}',
                        report_language = language, outputs = ReportOutputs(True, True, True, True), pdf_dark = dark))
                    root = result.report_path.parent.parent
                    manifest = json.loads((root / 'report-manifest.json').read_text())
                    palette = ReportPalette(dark)
                    expected_rgb = tuple(int(palette.background[i:i + 2], 16) for i in (1, 3, 5))

                    self.assertEqual(manifest['image_theme'], 'dark' if dark else 'light')

                    for profile in ('basic', 'extended'):
                        self.assertEqual(manifest['pdfs'][profile]['theme'], 'dark' if dark else 'light')

                        reader = PdfReader(root / 'pdf' / profile / 'report.pdf', strict = True)
                        text = '\n'.join(page.extract_text() for page in reader.pages)

                        self.assertIn('Когда вы играете' if language == 'ru' else 'When you play', text)
                        self.assertTrue(any('/Shading' in page['/Resources'] for page in reader.pages))

                        for page in reader.pages:
                            if '/Shading' in page['/Resources']:
                                self.assertIn('Когда вы играете' if language == 'ru' else 'When you play', page.extract_text())

                            operations = ContentStream(page.get_contents(), reader).operations
                            colors = [tuple(float(channel) for channel in args) for args, op in operations if op == b'rg']

                            self.assertTrue(any(all(abs(channel - expected / 255) < .00001
                                for channel, expected in zip(color, expected_rgb)) for color in colors))

                    for path in ('basic/public/images/activity-overview.png', 'extended/public/basic/images/activity-overview.png'):
                        with Image.open(root / path) as image:
                            self.assertEqual(image.getpixel((0, 0)), expected_rgb if dark else (247, 250, 252))

                    for path in ('basic/public/index.html', 'extended/public/playtime/index.html', 'extended/public/basic/index.html'):
                        html = (root / path).read_text()

                        self.assertEqual(html.count('data-intensity-row'), 7)
                        self.assertEqual(html.count('data-intensity-hit'), 2016)

    def test_pdf_only_uses_dark_theme_without_creating_sites(self):
        result = Bootstrap.report_generator().generate(ReportRequest((self.source,), self.root / 'pdf-only',
            outputs = ReportOutputs(False, True, False, True), pdf_dark = True))
        root = result.report_path.parent.parent
        manifest = json.loads((root / 'report-manifest.json').read_text())

        self.assertFalse((root / 'basic').exists())
        self.assertTrue(all(pdf['theme'] == 'dark' for pdf in manifest['pdfs'].values()))

    def test_theme_flag_is_validated_and_export_cli_accepts_it(self):
        with self.assertRaises(ValueError):
            ReportRequest((self.source,), self.root / 'invalid', pdf_dark = 'dark')

        from poe_log_analyze.core.request.ReportMode import ReportMode
        analysis = self.root / 'analysis'

        Bootstrap.report_generator().generate(ReportRequest((self.source,), analysis, mode = ReportMode.ANALYSIS))

        with redirect_stdout(StringIO()):
            code = ReportCli(Bootstrap.report_generator()).run(['--result', str(analysis), '--output', str(self.root / 'cli'),
                '--dark-pdf', '--no-basic', '--no-basic-pdf', '--extended-pdf'])

        self.assertEqual(code, 0)

        manifest = json.loads((self.root / 'cli/report-manifest.json').read_text())

        self.assertEqual(manifest['pdfs']['extended']['theme'], 'dark')
