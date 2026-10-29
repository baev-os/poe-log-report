"""Paged storage, JSON compatibility, and unfinished-report cleanup."""

import json
import tracemalloc
import unittest

from hashlib import sha256

from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from unittest.mock import patch

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder
from poe_log_analyze.stages.rendering.LogHistoryReader import LogHistoryReader
from poe_log_analyze.stages.rendering.LogHistoryJsonWriter import LogHistoryJsonWriter


class PagedHistoryTests(unittest.TestCase):
    """Synthetic history needs neither a complete text copy nor a complete object copy."""

    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.pages_path = self.root / 'event-pages.jsonl'
        self.output = self.root / 'events.json'
        self.stop = Event()
        self.control = ExecutionContext(cancelled = self.stop.is_set)

    @staticmethod
    def row(line):
        return {'line_number': line, 'record_id': line, 'type': 'synthetic.record',
                'status': 'recognized', 'timestamp': '2026-09-01T12:00:00+05:00',
                'text': f'Синтетическая запись 🗺️ {line} <tag>\n"\\' * 8,
                'fields': {'z': 'Последнее', 'a': 'Первое'}}

    def build(self, count):
        with self.pages_path.open('w', encoding = 'utf-8', newline = '\n') as stream:
            builder = LogHistoryBuilder(stream, self.control)

            for line in range(1, count + 1):
                builder.add(self.row(line))

            model = builder.result()

        self.assertTrue(all('rows' not in page for page in model['pages']))

        return model

    def test_json_matches_v2_bytes_and_field_order_survives_spooling(self):
        for count in (0, 1, 500, 501, 1000, 1001):
            with self.subTest(count = count):
                model = self.build(count)
                pages = list(LogHistoryReader.pages(self.pages_path, model, self.control))
                expected = {**model, 'pages': pages}
                LogHistoryJsonWriter.write(self.output, model, self.pages_path, self.control)

                self.assertEqual(self.output.read_bytes(),
                    (json.dumps(expected, ensure_ascii = False, sort_keys = True, indent = 2) + '\n').encode('utf-8'))
                self.assertEqual([row['line'] for page in pages for row in page['rows']], list(range(1, count + 1)))

                if count:
                    self.assertEqual(list(pages[0]['rows'][0]['fields']), ['z', 'a'])

                self.assertEqual([page['rows'] for page in pages],
                                 [page['rows'] for page in LogHistoryReader.pages(self.pages_path, model, self.control)])

    def test_page_buffers_bound_memory_during_composition_and_export(self):
        tracemalloc.start()

        try:
            model = self.build(12000)
            LogHistoryJsonWriter.write(self.output, model, self.pages_path, self.control)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        self.assertGreater(self.output.stat().st_size, 8 * 1024 * 1024)
        self.assertLess(peak, 8 * 1024 * 1024)
        self.assertEqual(model['count'], 12000)

    def test_missing_extra_and_reordered_pages_are_rejected(self):
        model = self.build(501)
        original = self.pages_path.read_bytes().splitlines(keepends = True)
        wrong_line = json.loads(original[1])
        wrong_line[0]['line'] = 1
        cases = (b''.join(original[:1]), b''.join(original + [b'[]\n']),
                 original[0] + b'[]\n', original[0] + json.dumps(wrong_line).encode() + b'\n')

        for raw in cases:
            with self.subTest(size = len(raw)):
                self.pages_path.write_bytes(raw)

                with self.assertRaises(ValueError):
                    list(LogHistoryReader.pages(self.pages_path, model, self.control))

    def test_reader_observes_cancellation_between_pages(self):
        model = self.build(501)

        with self.assertRaises(GenerationCancelled):
            pages = LogHistoryReader.pages(self.pages_path, model, self.control)

            self.assertEqual(next(pages)['last'], 500)

            self.stop.set()
            next(pages)

    def test_cancellation_and_write_failure_preserve_current_report_and_clean_spool(self):
        source = self.root / 'source.txt'
        source.write_text('\n' * 1001, encoding = 'utf-8')
        request = ReportRequest((source,), self.root / 'report', replace_report = True)
        generator = ReportGenerator()

        result = generator.generate(request)
        before = self.report_hashes()

        self.assertTrue(result.report_path.is_file())

        self.original_flush = LogHistoryBuilder._flush
        self.original_pages = LogHistoryReader.pages

        cases = ((LogHistoryBuilder, '_flush', self.cancel_flush, GenerationCancelled),
                 (LogHistoryBuilder, '_flush', self.fail_flush, OSError),
                 (LogHistoryReader, 'pages', self.cancel_pages, GenerationCancelled))

        for owner, method, action, error in cases:
            self.stop.clear()

            with self.subTest(action = action.__name__):
                with patch.object(owner, method, autospec = True, side_effect = action):
                    with self.assertRaises(error):
                        generator.generate(request, self.control)

                self.assertEqual(self.report_hashes(), before)
                self.assertFalse((self.root / 'build').exists())
                self.assertFalse(list(self.root.rglob('event-pages.jsonl')))
                self.assertEqual(source.read_text(), '\n' * 1001)

    def cancel_flush(self, builder):
        self.original_flush(builder)
        self.stop.set()

    def fail_flush(self, builder):
        self.original_flush(builder)
        raise OSError('Синтетическая ошибка записи страницы')

    def cancel_pages(self, path, model, control):
        for page in self.original_pages(path, model, control):
            yield page
            self.stop.set()

    def report_hashes(self):
        files = [self.root / 'index.html', *sorted((self.root / 'report').rglob('*'))]
        return {path.relative_to(self.root).as_posix(): sha256(path.read_bytes()).hexdigest()
                for path in files if path.is_file()}
