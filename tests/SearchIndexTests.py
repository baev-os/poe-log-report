import hashlib
import json
import tracemalloc
import unittest

from copy import deepcopy

from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from unittest.mock import patch

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.stages.rendering.SearchIndexWriter import SearchIndexWriter
from poe_log_analyze.stages.verification.LocalHTML import LocalHTML
from poe_log_analyze.stages.verification.SearchIndexVerifier import SearchIndexVerifier

from datetime import date


class SearchIndexTests(unittest.TestCase):
    """Complete local index: source values, safety, boundaries, and cleanup."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.stop = Event()
        self.control = ExecutionContext(cancelled = self.stop.is_set)

    @staticmethod
    def source_text():
        return ('\n' * 500
                + '2026/09/01 23:59:59 1 abcd [INFO Client 1] : SyntheticHero (Duelist) is now level 90\n'
                + '2026/09/02 00:00:00 2 abcd [INFO Client 1] : You have entered Dunes.\n'
                + '2026/09/02 00:00:01 3 abcd [INFO Client 1] [LOADING SCREEN] (Dunes) Duration = 1.25 seconds\n'
                + '2026/09/02 00:00:02 4 abcd [INFO Client 1] : SyntheticHero has been slain.\n'
                + '2026/09/02 00:00:03 5 abcd [INFO Client 1] Abnormal disconnect: An unexpected disconnection occurred.\n'
                + '2026/09/02 00:00:04 6 abcd [INFO Client 1] #SyntheticHero: Зеркало Mirror <script>window.injected=1</script>\n'
                + '</script>\u2028\u2029\x00 & " \\ ; window.injected=1; //\n')

    @staticmethod
    def payload(path):
        text = path.read_text()
        return json.loads(text[len(SearchIndexWriter.PREFIX):-len(SearchIndexWriter.SUFFIX)])

    def test_full_index_beyond_page_and_period_copies_ru_en_and_export(self):
        source = self.root / 'synthetic.txt'
        source.write_bytes(self.source_text().encode() + b'\xff\n')
        original = source.read_bytes()
        generator = ReportGenerator()

        analysis = generator.generate(ReportRequest((source, source), self.root / 'analysis', mode = ReportMode.ANALYSIS))

        for language in ('ru', 'en'):
            result = generator.generate(ReportRequest((analysis.directory,), self.root / language,
                mode = ReportMode.EXPORT, report_language = language, period = ReportPeriod(date(2026, 10, 1), None)))
            public = result.report_path.parent
            model = json.loads((public.parent / 'project/data/search-index.json').read_text())

            self.assertEqual(model['count'], 508)
            self.assertEqual([part['count'] for part in model['parts']], [500, 8])

            rows = [row for part in model['parts'] for row in self.payload(public / 'search' / part['path'])['rows']]

            self.assertEqual([row[0] for row in rows], list(range(1, 509)))
            self.assertEqual((rows[500][1][:10], rows[500][2]), ('2026-09-01', 'screen.level_up'))
            self.assertTrue(rows[504][6])
            self.assertIn('Зеркало Mirror <script>', rows[505][4])
            self.assertIsNone(rows[-1][4])
            self.assertEqual(rows[-1][3], 'error')
            self.assertIn('window.injected=1', rows[-2][4])
            self.assertEqual(model['parts'][1]['history'], '../events/page-2.html')

            html = (public / 'search/index.html').read_text()

            self.assertIn('data-history-search=', html)
            self.assertNotIn('window.injected', html)
            self.assertIn('search/index.html', (public / 'events/index.html').read_text())

            manifest = json.loads((public.parent / 'report-manifest.json').read_text())

            self.assertEqual(manifest['search']['count'], 508)
            self.assertEqual(manifest['search']['index_sha256'], hashlib.sha256((public.parent / 'project/data/search-index.json').read_bytes()).hexdigest())

            for part in model['parts']:
                raw = (public / 'search' / part['path']).read_bytes()

                self.assertNotIn(b'<', raw)
                self.assertNotIn(b'&', raw)
                self.assertNotIn('\u2028'.encode(), raw)
                self.assertEqual(manifest['public_sha256']['search/' + part['path']], hashlib.sha256(raw).hexdigest())

        self.assertEqual(source.read_bytes(), original)

    def test_timezone_values_long_multiline_and_input_immutability(self):
        row = {'line': 1, 'timestamp': '2026-09-01T23:59:00Z', 'message': 'Synthetic' * 2000 + '\nпродолжение',
               'fields': {'extra': 'Hidden value', 'existing': 'Synthetic'}, 'type': 'synthetic.row', 'status': 'recognized'}
        page = {'number': 1, 'path': 'index.html', 'first': 1, 'last': 1, 'rows': [row]}
        before = deepcopy(page)
        writer = SearchIndexWriter(self.root, 'Asia/Almaty', set(), self.control)
        writer.add(page)
        model = writer.result()
        saved = self.payload(self.root / 'search/parts/1.js')['rows'][0]

        self.assertEqual(saved[1], '2026-09-02T04:59:00+05:00')
        self.assertEqual(saved[4], row['message'])
        self.assertEqual(saved[5], 'Hidden value')
        self.assertEqual(model['parts'][0]['date_from'], '2026-09-02')
        self.assertEqual(page, before)

    def test_verifier_rejects_code_missing_rows_and_wrong_links(self):
        writer = SearchIndexWriter(self.root, 'UTC', set(), self.control)
        page = {'number': 1, 'path': 'index.html', 'first': 1, 'last': 1, 'rows': [
            {'line': 1, 'timestamp': None, 'message': '</script>', 'fields': {}, 'type': 'unknown', 'status': 'unknown'}]}
        writer.add(page)
        model = writer.result()
        history = {'count': 1, 'pages': [page]}
        target = self.root / 'events/index.html'
        target.parent.mkdir()
        target.write_text('<p id="line-1">Synthetic</p>')
        checker = LocalHTML(self.root, target)
        checker.feed(target.read_text())
        checkers = {target.resolve(): checker}
        SearchIndexVerifier.verify(self.root, model, history, checkers, self.control)
        path = self.root / 'search/parts/1.js'
        valid = path.read_bytes()

        for raw in (valid + b'alert(1);', valid.replace(b'\\u003c', b'<'),
                    SearchIndexWriter.encode({'version': 1, 'number': 1, 'rows': []})):
            with self.subTest(raw = raw[:25]):
                path.write_bytes(raw)
                model['parts'][0]['sha256'] = hashlib.sha256(raw).hexdigest()

                with self.assertRaises(ValueError):
                    SearchIndexVerifier.verify(self.root, model, history, checkers, self.control)

        path.write_bytes(valid)
        model['parts'][0]['sha256'] = hashlib.sha256(valid).hexdigest()
        checker.ids.clear()

        with self.assertRaises(ValueError):
            SearchIndexVerifier.verify(self.root, model, history, checkers, self.control)

    def test_empty_report_and_bounded_index_memory(self):
        source = self.root / 'empty.txt'
        source.write_text('')

        result = ReportGenerator().generate(ReportRequest((source,), self.root / 'empty'))

        self.assertEqual(self.payload(result.report_path.parent / 'search/parts/1.js')['rows'], [])

        tracemalloc.start()

        try:
            writer = SearchIndexWriter(self.root, 'UTC', set(), self.control)

            for number in range(1, 25):
                first = (number - 1) * 500 + 1
                page = {'number': number, 'path': f'page-{number}.html', 'first': first, 'last': first + 499,
                        'rows': [{'line': line, 'timestamp': None, 'message': 'Synthetic text ' * 80,
                                  'fields': {}, 'type': 'unknown', 'status': 'unknown'} for line in range(first, first + 500)]}
                writer.add(page)

            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        self.assertEqual(writer.result()['count'], 12000)
        self.assertLess(peak, 6 * 1024 * 1024)
        self.assertGreater(sum(path.stat().st_size for path in (self.root / 'search/parts').glob('*.js')), 8 * 1024 * 1024)

    def test_cancel_and_index_write_failure_preserve_current_report(self):
        source = self.root / 'synthetic.txt'
        source.write_text(self.source_text())
        request = ReportRequest((source,), self.root / 'report', replace_report = True)
        generator = ReportGenerator()

        generator.generate(request)
        before = self.hashes()
        self.original_add = SearchIndexWriter.add

        for effect, error in ((self.cancel_add, GenerationCancelled), (OSError('Синтетическая ошибка'), OSError)):
            self.stop.clear()

            with patch.object(SearchIndexWriter, 'add', autospec = True, side_effect = effect):
                with self.assertRaises(error):
                    generator.generate(request, self.control)

            self.assertEqual(self.hashes(), before)
            self.assertFalse((self.root / 'build').exists())

    def cancel_add(self, writer, page):
        self.original_add(writer, page)
        self.stop.set()

    def hashes(self):
        return {path.relative_to(self.root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (self.root / 'report').rglob('*') if path.is_file()}
