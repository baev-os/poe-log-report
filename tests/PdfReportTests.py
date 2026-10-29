import hashlib
import json
import unittest

from contextlib import redirect_stdout

from io import StringIO

from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from unittest.mock import patch

from pypdf import PdfReader

from CollectionFixture import CollectionFixture

from poe_log_analyze.cli.ReportCli import ReportCli

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.stages.rendering.pdf.PdfDocument import PdfDocument
from poe_log_analyze.stages.rendering.pdf.PdfReportWriter import PdfReportWriter


class PdfReportTests(unittest.TestCase):
    """Read actual PDFs: Unicode, totals, pages, preservation, and cancellation."""

    def setUp(self):
        self.temp = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'synthetic.txt'
        line = CollectionFixture.line
        self.source.write_text(''.join([
            line(0, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
            line(1, ': You have entered Dunes.'),
            line(2, '[LOADING SCREEN] (Dunes) Duration = 1.25 seconds'),
            line(3, ': Герой<&> (Duelist) is now level 89'),
            line(4, ': Герой<&> (Duelist) is now level 90'),
            line(5, ': Герой<&> (Duelist) is now level 91'),
            line(61, 'Generating level 1 area "HideoutOssuary" with seed 2'),
            line(62, ': You have entered Synthetic Hideout.'),
            line(72, ': 7 Items identified'),
            line(122, 'Abnormal disconnect: An unexpected disconnection occurred.'),
        ]), encoding = 'utf-8')

    def generate(self, name, language = 'ru', pdf = True):
        return ReportGenerator().generate(ReportRequest((self.source, self.source), self.root / name,
                                                        report_language = language, generate_pdf = pdf))

    def test_ru_en_pdf_embeds_fonts_matches_projections_and_has_no_active_content(self):
        for language in ('ru', 'en'):
            with self.subTest(language = language):
                result = self.generate(language, language)
                public = result.report_path.parent
                pdf = public / 'report.pdf'
                reader = PdfReader(pdf, strict = True)
                text = '\n'.join(page.extract_text() for page in reader.pages)

                self.assertGreaterEqual(len(reader.pages), 8)
                self.assertEqual(reader.trailer['/Root']['/Lang'], language)
                self.assertIn('Герой<&>', text)
                self.assertIn('Dunes', text)
                self.assertIn('00:00:01.25', text)
                self.assertIn('2026-09-01', text)
                self.assertIn('До 90' if language == 'ru' else 'Up to level 90', text)
                self.assertIn('90–100', text)
                self.assertNotIn('/JavaScript', reader.trailer['/Root'])
                self.assertNotIn('/OpenAction', reader.trailer['/Root'])

                fonts = [font.get_object() for page in reader.pages
                         for font in page['/Resources']['/Font'].get_object().values()]
                embedded = [font for font in fonts if '/FontDescriptor' in font]

                self.assertTrue(embedded)
                self.assertTrue(all('/FontFile2' in font['/FontDescriptor'] for font in embedded))

                manifest = json.loads((public.parent / 'report-manifest.json').read_text())

                self.assertTrue(manifest['pdf']['enabled'])
                self.assertEqual(manifest['public_sha256']['report.pdf'], hashlib.sha256(pdf.read_bytes()).hexdigest())
                self.assertIn('reportlab', manifest['renderer']['versions'])
                self.assertEqual(manifest['pdf']['content_version'], '12')

                landscape = [page for page in reader.pages if page.mediabox.width > page.mediabox.height]

                self.assertEqual(len(landscape), 2)
                self.assertIn('За весь период' if language == 'ru' else 'Entire period', landscape[0].extract_text())
                self.assertNotIn('За весь период' if language == 'ru' else 'Entire period', landscape[1].extract_text())
                self.assertTrue(all(('Когда вы находились' if language == 'ru' else 'When') in page.extract_text()
                                    for page in landscape))
                self.assertTrue(all('Heist' in page.extract_text() and 'Legion' in page.extract_text()
                                    for page in landscape))
                self.assertTrue(any(page.images for page in reader.pages))
                self.assertIn('Δ времени' if language == 'ru' else 'Elapsed time', text)
                self.assertIn('00:00:04', text)
                self.assertIn('class="report-pdf"', (public / 'index.html').read_text())
                self.assertIn('Скачать PDF' if language == 'ru' else 'Download PDF', (public / 'index.html').read_text())

                for page in public.rglob('*.html'):
                    self.assertIn('report.pdf', page.read_text())

                model = json.loads((public.parent / 'project/data/statistics_summary.json').read_text())

                self.assertEqual(model['maps']['count'], 1)
                self.assertIn(model['maps']['duration'], text)

    def test_default_does_not_run_pdf_renderer_and_pdf_is_reproducible(self):
        with patch.object(PdfReportWriter, 'write', side_effect = AssertionError('PDF выключен')):
            plain = self.generate('plain', pdf = False)

        self.assertFalse((plain.report_path.parent / 'report.pdf').exists())
        self.assertNotIn('report.pdf', plain.report_path.read_text())

        one, two = self.generate('one'), self.generate('two')

        self.assertEqual((one.report_path.parent / 'report.pdf').read_bytes(),
                         (two.report_path.parent / 'report.pdf').read_bytes())

    def test_cli_pdf_export_without_source(self):
        saved = ReportGenerator().generate(ReportRequest((self.source,), self.root / 'analysis', mode = ReportMode.ANALYSIS))
        self.source.unlink()

        with redirect_stdout(StringIO()) as output:
            code = ReportCli.main(['--result', str(saved.directory), '--output', str(self.root / 'export'), '--pdf'])

        self.assertEqual(code, 0)
        self.assertTrue((self.root / 'export/public/report.pdf').is_file())
        self.assertIn('PDF:', output.getvalue())

        with self.assertRaisesRegex(ValueError, 'PDF'):
            ReportRequest((self.source,), self.root / 'bad', mode = ReportMode.ANALYSIS, generate_pdf = True)

    def test_pdf_failure_or_cancellation_keeps_previous_report_and_cleans_workspace(self):
        request = ReportRequest((self.source,), self.root / 'report', replace_report = True, generate_pdf = True)

        result = ReportGenerator().generate(request)
        pdf = result.report_path.parent / 'report.pdf'
        before = pdf.read_bytes()
        entry = (self.root / 'index.html').read_bytes()

        for error in (RuntimeError('Сбой PDF'), GenerationCancelled()):
            with self.subTest(error = type(error).__name__):
                with patch.object(PdfDocument, 'afterFlowable', side_effect = error):
                    with self.assertRaises(type(error)):
                        ReportGenerator().generate(request)

                self.assertEqual(pdf.read_bytes(), before)
                self.assertEqual((self.root / 'index.html').read_bytes(), entry)
                self.assertFalse((self.root / 'build').exists())

    def test_corrupted_pdf_is_not_published(self):
        with patch.object(PdfReportWriter, 'write', side_effect = self.corrupt_pdf):
            with self.assertRaisesRegex(ValueError, 'The PDF report is incomplete'):
                self.generate('broken')

        self.assertFalse((self.root / 'broken').exists())

    @staticmethod
    def corrupt_pdf(path, content):
        path.write_bytes(b'%PDF-1.4\npartial')

    def test_empty_report_and_long_untrusted_text_paginate(self):
        self.source.write_text('')

        result = self.generate('empty')
        reader = PdfReader(result.report_path.parent / 'report.pdf')

        self.assertIn('Нет', ''.join(page.extract_text() for page in reader.pages))

        from poe_log_analyze.runtime.RuntimeResources import RuntimeResources

        from poe_log_analyze.stages.composition.localization.TranslationCatalogue import TranslationCatalogue
        writer = PdfReportWriter(TranslationCatalogue('ru', RuntimeResources.resource_root()), ExecutionContext())

        with patch.object(writer, 'compose', side_effect = self.large_table):
            self.writer = writer
            writer.write(self.root / 'long.pdf', None)

        reader = PdfReader(self.root / 'long.pdf', strict = True)
        text = ''.join(page.extract_text() for page in reader.pages)

        self.assertGreater(len(reader.pages), 2)
        self.assertIn('<img src="https://invalid.test/a">', text)
        self.assertIn('Конец', text)

    def large_table(self, content):
        text = '<img src="https://invalid.test/a"> ' + 'ОченьДлинноеИмя ' * 1200 + ' Конец'
        self.writer.table(['activities.zone'], [(text,)], [510])

    def test_cancel_requested_during_pdf_layout_is_observed(self):
        stop = Event()
        self.original_footer = PdfDocument.footer
        self.stop = stop

        with patch.object(PdfDocument, 'footer', self.cancel_on_page):
            with self.assertRaises(GenerationCancelled):
                ReportGenerator().generate(ReportRequest((self.source,), self.root / 'cancel', generate_pdf = True),
                                           ExecutionContext(cancelled = stop.is_set))

        self.assertFalse((self.root / 'cancel').exists())

    def cancel_on_page(self, canvas, document):
        self.stop.set()
        self.original_footer(document, canvas, document)

    def test_icons_fit_text_rows_and_untrusted_paths_are_not_loaded(self):
        from poe_log_analyze.runtime.RuntimeResources import RuntimeResources

        from poe_log_analyze.stages.composition.localization.TranslationCatalogue import TranslationCatalogue

        from poe_log_analyze.runtime.GameAreaCatalogue import GameAreaCatalogue

        # write registers pinned fonts before constructing paragraphs.
        self.generate('font-setup')
        writer = PdfReportWriter(TranslationCatalogue('ru', RuntimeResources.resource_root()), ExecutionContext())
        row = dict(GameAreaCatalogue.lookup('MapWorldsDunes'), name = 'Dunes')
        plain = writer.paragraph(row['name'], 'cell')
        icon = writer.zone_name(row)

        self.assertEqual(icon.wrap(210, 100)[1], plain.wrap(210, 100)[1])
        self.assertIn('<img ', icon.text)

        unsafe = writer.zone_name({'name': '<script>', 'icon': '../../data/private.png'})

        self.assertNotIn('<img ', unsafe.text)
        self.assertIn('&lt;script&gt;', unsafe.text)

    def test_weekly_pdf_axis_clips_at_boundaries_and_handles_dst(self):
        from datetime import datetime

        from poe_log_analyze.stages.rendering.pdf.PdfCharts import PdfCharts
        start = datetime.fromisoformat('2026-10-25T23:30:00+01:00').timestamp()
        end = datetime.fromisoformat('2026-10-26T00:30:00+01:00').timestamp()
        model = {'timezone': 'Europe/Berlin', 'periods': [{'start': start, 'end': end}],
                 'groups': [{'children': [{'visits': [{'start': start, 'end': end}]}]}]}
        chart = PdfCharts(None, ExecutionContext())
        periods = list(chart.activity_periods(model))

        self.assertEqual(len(periods), 2)
        self.assertEqual(periods[0]['end'] - periods[0]['start'], 7 * 86400 + 3600)
        self.assertEqual(periods[0]['end'], periods[1]['start'])
        self.assertEqual(sum(t['major'] for t in periods[0]['ticks']), 8)
        self.assertEqual(len(periods[0]['ticks']), 29)
        self.assertNotEqual(chart.day_color(0), chart.day_color(1))
        self.assertNotEqual(chart.day_color(7200), chart.day_color(28800))

    def test_overview_spans_months_includes_last_point_and_keeps_weekly_detail(self):
        from reportlab.graphics.shapes import Line, Rect

        from poe_log_analyze.runtime.RuntimeResources import RuntimeResources

        from poe_log_analyze.stages.composition.localization.TranslationCatalogue import TranslationCatalogue
        from poe_log_analyze.stages.rendering.pdf.PdfCharts import PdfCharts
        text = self.source.read_text()
        self.source.write_text(text + text.replace('2026/09/01', '2026/10/02'))

        result = self.generate('overview')
        public = result.report_path.parent
        reader = PdfReader(public / 'report.pdf')
        landscape = [page for page in reader.pages if page.mediabox.width > page.mediabox.height]

        self.assertEqual(len(landscape), 3)
        self.assertIn('01.09.2026', landscape[0].extract_text())
        self.assertIn('02.10.2026', landscape[0].extract_text())

        model = json.loads((public.parent / 'project/data/activities.json').read_text())
        chart = PdfCharts(TranslationCatalogue('ru', RuntimeResources.resource_root()), ExecutionContext())
        period = chart.activity_overview(model)

        self.assertEqual((period['start'], period['end']),
                         (model['periods'][0]['start'], model['periods'][0]['end']))

        lane = model['groups'][0]['children'][0]
        lane['visits'] = [{'start': period['end'], 'end': period['end'], 'measured': False}]
        drawing = chart.activities(model, period)

        self.assertLessEqual(drawing.height, 420)

        row_lines = [shape for shape in drawing.contents if isinstance(shape, Line) and shape.y1 == shape.y2]

        self.assertTrue(all(shape.y1 > 32 for shape in row_lines))

        marks = [shape for shape in drawing.contents if isinstance(shape, Rect)]

        self.assertTrue(any(mark.x > 744 and mark.width > 0 for mark in marks))
        self.assertTrue(all(mark.x + mark.width <= 745 for mark in marks))

        # Even a single known entry without measured duration must remain visible.
        model['groups'] = model['groups'][:1]
        model['periods'] = [{'start': period['end'], 'end': period['end'] + 1}]
        single = chart.activities(model, chart.activity_overview(model))

        self.assertEqual(len([shape for shape in single.contents if isinstance(shape, Rect)]), 1)
