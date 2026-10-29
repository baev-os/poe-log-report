"""Complete review queue, stable groups, and preservation of unknown lines."""

import json
import unittest

from base64 import b64decode
from io import BytesIO

from pathlib import Path
from tempfile import TemporaryDirectory

from zoneinfo import ZoneInfo

from poe_log_analyze.stages.parsing.LogAnalysisService import LogAnalysisService
from poe_log_analyze.stages.parsing.DiagnosticSummary import DiagnosticSummary
from poe_log_analyze.stages.parsing.LogParser import LogParser

from DiagnosticsFixture import DiagnosticsFixture


class DiagnosticTests(unittest.TestCase):
    """Grouping changes no status and loses no problematic byte."""

    def test_groups_ignore_header_but_preserve_exact_payload(self):
        raw = b''.join(DiagnosticsFixture.message('PRIVATE_MESSAGE', i) for i in range(12))
        raw += DiagnosticsFixture.message('PRIVATE_MESSAGE ') + b'PRIVATE_MESSAGE\n\r\r\n\xff\n'
        raw += DiagnosticsFixture.message('PRIVATE_MESSAGE', stamp = '2026/02/30 10:00:00') + b'\n'

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / 'input.txt', root / 'result'
            source.write_bytes(raw)
            coverage = LogAnalysisService.analyze(source, output)
            summary = json.loads((output / 'diagnostic_summary.json').read_text())
            rows = [json.loads(line) for line in (output / 'lines.jsonl').read_text().splitlines()]
            diagnostics = [json.loads(line) for line in (output / 'diagnostics.jsonl').read_text().splitlines()]

            self.assertEqual(summary['total_lines'], 17)
            self.assertEqual(summary['categories'], {'message': 13, 'unframed': 1, 'control': 1, 'encoding': 1, 'timestamp': 1})
            self.assertEqual(sum(g['count'] for g in summary['groups']), 17)
            self.assertEqual(summary['groups'][0]['count'], 12)
            self.assertEqual(summary['groups'][0]['sample_lines'], list(range(1, 11)))
            self.assertEqual((summary['groups'][0]['first_line'], summary['groups'][0]['last_line']), (1, 12))
            self.assertEqual(summary['input_sha256'], coverage['input_sha256'])
            self.assertEqual(summary['total_lines'], coverage['unknown_lines'] + coverage['error_lines'])
            self.assertEqual(diagnostics, [r for r in rows if r['status'] != 'recognized'])
            self.assertEqual(b''.join(b64decode(r['raw_base64']) for r in rows), raw)
            self.assertEqual(source.read_bytes(), raw)
            self.assertFalse(coverage['recognition_complete'])
            self.assertNotIn('PRIVATE_MESSAGE', (output / 'diagnostic_summary.md').read_text())

    def test_key_is_stable_and_uses_untruncated_payload(self):
        text = 'x' * 600
        raw = DiagnosticsFixture.message(text) + DiagnosticsFixture.message(text + 'different')
        summaries = []

        for stream in (raw, raw.replace(b'Client 42', b'Client 99')):
            summary = DiagnosticSummary()

            for row in LogParser.iter_records(BytesIO(stream), ZoneInfo('Asia/Almaty')):
                summary.add(row)

            summaries.append(summary.result('source', '6'))

        self.assertEqual(summaries[0], summaries[1])

        groups = summaries[0]['groups']

        self.assertEqual(len(groups), 2)
        self.assertNotEqual(groups[0]['group_id'], groups[1]['group_id'])
        self.assertTrue(all(g['example_truncated'] and len(g['example_text']) == 512 for g in groups))

    def test_empty_queue_for_recognized_input(self):
        summary = DiagnosticSummary()
        row = next(LogParser.iter_records(BytesIO(b'\n'), ZoneInfo('Asia/Almaty')))
        summary.add(row)
        result = summary.result('source', '6')

        self.assertEqual(result['total_lines'], 0)
        self.assertEqual(result['groups'], [])
        self.assertEqual(result['categories'], {})
