"""Multiline-record links when removing a copied prefix."""
import base64
import hashlib
import json
import unittest

from pathlib import Path
from tempfile import TemporaryDirectory

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.stages.merging.UnifiedLedgerWriter import UnifiedLedgerWriter


class UnifiedLedgerTests(unittest.TestCase):
    """The parent number must reference a retained line in the shared history."""

    @staticmethod
    def ledger(path, texts, parents):
        rows = [{'line_number': n, 'record_id': parent, 'type': 'blank', 'status': 'recognized',
                 'raw_base64': base64.b64encode(text.encode()).decode()} for n,(text,parent) in enumerate(zip(texts,parents),1)]
        raw = ''.join(json.dumps(row)+'\n' for row in rows).encode()
        path.write_bytes(raw)

        return hashlib.sha256(raw).hexdigest()

    def test_continuation_references_kept_parent_after_prefix_and_other_history(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            writer = UnifiedLedgerWriter(root/'combined.jsonl', ExecutionContext())
            first = root/'first.jsonl'
            digest = self.ledger(first,['a\n','b\n'],[1,2])

            self.assertEqual(writer.append(first,0,expected_sha256 = digest),[0,1,2])

            other = root/'other.jsonl'
            digest = self.ledger(other,['c\n','d\n'],[1,2])

            self.assertEqual(writer.append(other,0,expected_sha256 = digest),[0,3,4])

            extended = root/'extended.jsonl'
            digest = self.ledger(extended,['a\n','b\n','continuation\n'],[1,2,2])

            self.assertEqual(writer.append(extended,2,0,expected_sha256 = digest),[0,1,2,5])

            rows = [json.loads(raw) for raw in writer.path.read_text().splitlines()]

            self.assertEqual([r['line_number'] for r in rows],[1,2,3,4,5])
            self.assertEqual(rows[-1]['record_id'],2)
            self.assertEqual([r['line_number'] for r in rows if r['history_boundary']], [1,3,5])
            self.assertEqual(b''.join(base64.b64decode(r['raw_base64']) for r in rows),b'a\nb\nc\nd\ncontinuation\n')
            self.assertEqual(writer.coverage('UTC','6')['total_lines'],5)

            with self.assertRaisesRegex(ValueError,'registry changed'):
                writer.append(first,0,expected_sha256 = '0'*64)
