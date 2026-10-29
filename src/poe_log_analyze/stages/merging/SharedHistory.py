import hashlib
import json

from base64 import b64decode
from datetime import datetime, timezone

from pathlib import Path
from typing import Any

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext


class SharedHistory:
    """Confirmed shared source paths up to the first differing byte."""

    OVERLAP_POLICY = 'shared_prefix_v2'

    def __init__(self, control: ExecutionContext | None = None) -> None:
        self.control = control or ExecutionContext()
        self.sources: dict[str, Any] = {}
        self.pairs: dict[frozenset[str], Any] = {}
        self.summary: dict[str, Any] = {'policy': self.OVERLAP_POLICY, 'prefixes': [], 'excluded': [],
            'removed_runs': 0, 'removed_maps': 0, 'removed_visits': 0, 'removed_map_seconds': 0,
            'removed_intervals': 0, 'removed_play_seconds': 0}

    def register(self, ledger: Path, ledger_sha256: str, input_sha256: str, label: str) -> dict | None:
        fingerprints = []
        prefixes = {key: {'source': label, 'same_as': key, 'lines': 0, 'bytes': 0, 'timestamp': None}
                    for key in self.sources}
        ledger_hash, input_hash = hashlib.sha256(), hashlib.sha256()
        offset, stamp = 0, None

        with ledger.open('rb') as source:
            for number, raw in enumerate(source, 1):
                self.control.check()
                ledger_hash.update(raw)
                row = json.loads(raw)

                if row['line_number'] != number:
                    raise ValueError('Invalid registry order while comparing shared history')

                original = b64decode(row['raw_base64'], validate = True)
                input_hash.update(original)
                offset += len(original)
                fingerprint = hashlib.sha256(original).digest()
                fingerprints.append(fingerprint)
                stamp = row.get('timestamp') or stamp

                for key, prefix in prefixes.items():
                    previous = self.sources[key]['fingerprints']

                    if prefix['lines'] == number - 1 and number <= len(previous) and previous[number - 1] == fingerprint:
                        prefix.update(lines = number, bytes = offset, timestamp = stamp)

                if number % 1000 == 0:
                    self.control.report('Compare shared file history', lines = number)

        if ledger_hash.hexdigest() != ledger_sha256 or input_hash.hexdigest() != input_sha256:
            raise ValueError('Registry or raw-byte hash mismatch while comparing shared history')

        for key, prefix in prefixes.items():
            self.pairs[frozenset((key, label))] = prefix

            if prefix['lines']:
                self.summary['prefixes'].append(prefix)

        self.sources[label] = {'fingerprints': fingerprints, 'sha256': input_sha256}

        return max(prefixes.values(), key = lambda p: p['lines'], default = None)

    def prefix(self, left: dict, right: dict) -> dict:
        return self.pairs.get(frozenset((left['source'], right['source'])), {'lines': 0, 'timestamp': None})

    def order(self, record: dict) -> tuple:
        origin = record['origin']
        source = self.sources[origin['source']]

        return (-len(source['fingerprints']), source['sha256'], origin['first_line'], origin['last_line'], origin['source'])

    def shared_end(self, left: dict, right: dict, start_key: str, end_key: str) -> datetime | None:
        prefix = self.prefix(left['origin'], right['origin'])

        if prefix['lines'] < max(left['origin']['first_line'], right['origin']['first_line']):
            return None

        end = min(self.moment(left[end_key]), self.moment(right[end_key]))

        if prefix['lines'] < min(left['origin']['last_line'], right['origin']['last_line']):
            if prefix['timestamp'] is None:
                return None

            end = min(end, self.moment(prefix['timestamp']))

        start = max(self.moment(left[start_key]), self.moment(right[start_key]))

        return max(start, end)

    @staticmethod
    def moment(stamp: str) -> datetime:
        return datetime.fromisoformat(stamp).astimezone(timezone.utc)
