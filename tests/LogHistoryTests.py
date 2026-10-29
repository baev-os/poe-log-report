import json
import unittest

from base64 import b64decode
from copy import deepcopy

from pathlib import Path
from tempfile import TemporaryDirectory

from CollectionFixture import CollectionFixture

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder
from poe_log_analyze.stages.rendering.LogHistoryReader import LogHistoryReader


class LogHistoryTests(unittest.TestCase):
    """All physical lines, stable ordering, pages, and source values."""

    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.pages_path = Path(temporary.name) / 'event-pages.jsonl'
        self.stream = self.pages_path.open('w', encoding = 'utf-8', newline = '\n')
        self.addCleanup(self.stream.close)
        self.builder = LogHistoryBuilder(self.stream, ExecutionContext())

    def model(self):
        metadata = self.builder.result()
        self.stream.flush()

        return {**metadata, 'pages': list(LogHistoryReader.pages(self.pages_path, metadata, ExecutionContext()))}

    def test_continuation_crosses_page_without_invented_timestamp(self):
        builder = self.builder
        row = {'line_number': 1, 'record_id': 1, 'timestamp': '2026-09-02T12:00:00+05:00',
               'type': 'synthetic.record', 'status': 'recognized', 'fields': {}, 'text': 'Synthetic'}
        before = deepcopy(row)

        for line in range(1, 501):
            builder.add({**row, 'line_number': line, 'record_id': line})

        builder.add({**row, 'line_number': 501, 'record_id': 500, 'timestamp': None,
                     'type': 'synthetic.field', 'text': 'Synthetic continuation'})
        builder.add({**row, 'line_number': 502, 'record_id': 502, 'timestamp': '2026-09-01T10:00:00+05:00'})
        model = self.model()

        self.assertEqual(row, before)
        self.assertEqual(model['count'], 502)
        self.assertEqual([len(page['rows']) for page in model['pages']], [500, 2])
        self.assertEqual([r['line'] for page in model['pages'] for r in page['rows']], list(range(1, 503)))

        continuation = model['pages'][1]['rows'][0]

        self.assertEqual(continuation['parent'], 'index.html#line-500')
        self.assertIsNone(continuation['time'])
        self.assertIsNone(continuation['timestamp'])
        self.assertEqual(model['dates'][0]['href'], 'page-2.html#line-502')
        self.assertEqual(model['dates'][1]['href'], 'index.html#line-1')
        self.assertEqual(model['pages'][0]['next'], 'page-2.html')
        self.assertEqual(model['pages'][1]['previous'], 'index.html')

    def test_empty_history_still_has_one_page(self):
        model = self.model()

        self.assertEqual(model['count'], 0)
        self.assertEqual(len(model['pages']), 1)
        self.assertEqual(model['pages'][0]['rows'], [])
        self.assertEqual(model['dates'], [])

    def test_reliquary_continuation_links_to_previous_html_page(self):
        with TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp') as temporary:
            root = Path(temporary)
            source = root / 'synthetic.txt'
            messages = ('Generating level 75 area "ClassicTreasury_Cosmic" with seed 1',
                        '[SCENE] Set Source [Voidborn Reliquary]',
                        ': You have entered Voidborn Reliquary.',
                        '[LOADING SCREEN] (Voidborn Reliquary) Duration = 1.5 seconds',
                        ': Synthetic gift')
            source.write_text('\n' * 495 + ''.join(CollectionFixture.line(i, text)
                                                   for i, text in enumerate(messages)) + 'Synthetic continuation\n')

            result = ReportGenerator().generate(ReportRequest((source,), root / 'result'))
            model = json.loads((result.report_path.parent.parent / 'project/data/events.json').read_text())

            self.assertEqual(model['pages'][0]['rows'][-1]['type'], 'reliquary.message')

            row = model['pages'][1]['rows'][0]

            self.assertEqual(row['type'], 'reliquary.message.field')
            self.assertEqual(row['parent'], 'index.html#line-500')
            self.assertIsNone(row['timestamp'])

            html = (result.report_path.parent / 'events/page-2.html').read_text()

            self.assertIn('href="index.html#line-500"', html)
            self.assertIn('Synthetic continuation', html)

    def test_full_export_keeps_chat_service_unknown_empty_invalid_and_copied_lines(self):
        with TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp') as temporary:
            root = Path(temporary)
            source = root / 'synthetic.txt'
            line = CollectionFixture.line
            text = (line(60, '[SCENE] Set Source [Synthetic Area]') +
                    line(61, '@From SyntheticPlayer: <script>example</script>') +
                    'Synthetic unsupported <img src=x>\n' + '\n' * 497 +
                    line(30, ': SyntheticHero (Duelist) is now level 13'))
            raw = text.encode() + b'\xff\xfe\n'
            source.write_bytes(raw)
            models = []

            for language in ('ru', 'en'):
                with self.subTest(language = language):
                    result = ReportGenerator().generate(ReportRequest((source, source), root / language,
                                                                     report_language = language))
                    report = result.report_path.parent.parent
                    model = json.loads((report / 'project/data/events.json').read_text())
                    models.append(model)
                    rows = [row for page in model['pages'] for row in page['rows']]
                    analysis = json.loads((report / 'project/data/analysis.json').read_text())

                    self.assertEqual(model['count'], 502)
                    self.assertEqual(model['count'], analysis['total_lines'])
                    self.assertEqual([row['line'] for row in rows], list(range(1, 503)))
                    self.assertEqual(rows[0]['type'], 'scene.source')
                    self.assertEqual(rows[1]['type'], 'chat.whisper')
                    self.assertEqual(rows[2]['status'], 'unknown')
                    self.assertEqual(rows[3]['message'], '')
                    self.assertEqual(rows[-1]['status'], 'error')
                    self.assertIsNone(rows[-1]['original'])
                    self.assertEqual(b64decode(rows[-1]['raw_base64']), b'\xff\xfe\n')

                    first = (report / 'public/events/index.html').read_text()
                    second = (report / 'public/events/page-2.html').read_text()

                    self.assertEqual(first.count('data-item data-kind='), 500)
                    self.assertEqual(second.count('data-item data-kind='), 2)
                    self.assertIn('timeline-rows history-rows', first)
                    self.assertNotIn('card-body', first)
                    self.assertIn('&lt;script&gt;example&lt;/script&gt;', first)
                    self.assertIn('&lt;img src=x&gt;', first)
                    self.assertNotIn('<script>example', first)
                    self.assertIn('page-2.html', first)

                    manifest = json.loads((report / 'report-manifest.json').read_text())

                    self.assertIn('events/page-2.html', manifest['public_sha256'])

            self.assertEqual(models[0], models[1])
            self.assertEqual(source.read_bytes(), raw)
