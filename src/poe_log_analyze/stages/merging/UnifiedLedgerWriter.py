import hashlib
import json

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from pathlib import Path
from typing import Any

from base64 import b64decode
from collections import Counter

from poe_log_analyze.stages.parsing.DiagnosticSummary import DiagnosticSummary


class UnifiedLedgerWriter:
    """Logical registry of one history; originals and their numbering remain in analyses."""

    def __init__(self, path: Path, control: ExecutionContext) -> None:
        self.path, self.control = path, control
        self.total = self.size = 0
        self.mappings = []
        self.statuses, self.types = Counter(), Counter()
        self.input_hash, self.ledger_hash = hashlib.sha256(), hashlib.sha256()
        self.diagnostics = DiagnosticSummary()

    def append(self, ledger: Path, skip: int, copy_source: int | None = None, *, expected_sha256: str) -> list[int]:
        digest = hashlib.sha256()
        mapping = [0] if copy_source is None else self.mappings[copy_source][:skip+1]

        with ledger.open('rb') as source, self.path.open('ab') as target:
            for raw in source:
                self.control.check()
                digest.update(raw)
                row = json.loads(raw)

                if row['line_number'] <= skip:
                    continue

                row['history_boundary'] = row['line_number'] == skip + 1
                self.total += 1
                mapping.append(self.total)
                row['line_number'] = self.total
                parent = row.get('record_id')
                row['record_id'] = mapping[parent] if parent else None
                original = b64decode(row['raw_base64'], validate = True)
                row['byte_start'] = self.size
                self.size += len(original)
                row['byte_end'] = self.size
                self.input_hash.update(original)
                self.statuses[row['status']] += 1
                self.types[row['type']] += 1
                self.diagnostics.add(row)
                encoded = (json.dumps(row, ensure_ascii = False, sort_keys = True) + '\n').encode()
                target.write(encoded)
                self.ledger_hash.update(encoded)

        if digest.hexdigest() != expected_sha256:
            raise ValueError('The registry changed while merging history')

        self.mappings.append(mapping)

        return mapping

    def coverage(self, timezone: str, rules_version: str) -> dict[str, Any]:
        complete = not (self.statuses['unknown'] or self.statuses['error'])
        return {'source_label': 'История игрока', 'timezone': timezone,
                'total_lines': self.total, 'input_bytes': self.size,
                'recognized_lines': self.statuses['recognized'], 'unknown_lines': self.statuses['unknown'],
                'error_lines': self.statuses['error'], 'input_sha256': self.input_hash.hexdigest(),
                'rules_version': rules_version, 'schema_version': '1', 'recognition_complete': complete,
                'state': 'Распознавание завершено' if complete else 'Распознавание не завершено',
                'percentage': f"{self.statuses['recognized']/self.total:.2%}" if self.total else 'Не применимо: пустой файл; 0',
                'types': [{'type': key, 'count': count} for key,count in sorted(self.types.items())],
                'diagnostic_categories': [{'category': DiagnosticSummary.CATEGORIES[key], 'count': count}
                                          for key,count in sorted(self.diagnostics.categories.items())]}
