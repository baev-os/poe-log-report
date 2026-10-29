import hashlib
import json

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext


class SearchIndexWriter:
    """Write file:// search chunks while retaining only the current page."""

    PREFIX = 'window.PoeSearchChunk = '
    SUFFIX = ';\n'

    def __init__(self, public: Path, timezone: str, issues: set[int], control: ExecutionContext):
        self.public, self.zone, self.issues, self.control = public, ZoneInfo(timezone), issues, control
        self.parts, self.types = [], set()
        self.count = 0
        (public / 'search/parts').mkdir(parents = True, exist_ok = True)

    def add(self, page: dict) -> None:
        self.control.check()
        rows = []
        dates = []

        for row in page['rows']:
            self.control.check()
            stamp = datetime.fromisoformat(row['timestamp']).astimezone(self.zone).isoformat() if row['timestamp'] else ''
            message = row['message']
            values = [str(value) for value in row['fields'].values() if str(value) not in (message or '')]
            rows.append([row['line'], stamp, row['type'], row['status'], message,
                         '\n'.join(values), row['line'] in self.issues])
            self.types.add(row['type'])

            if stamp:
                dates.append(stamp[:10])

        number = page['number']
        payload = {'version': 1, 'number': number, 'rows': rows}
        raw = self.encode(payload)
        path = f'parts/{number}.js'
        (self.public / 'search' / path).write_bytes(raw)
        self.parts.append({'number': number, 'path': path, 'history': '../events/' + page['path'],
                           'first': page['first'], 'last': page['last'], 'count': len(rows),
                           'date_from': min(dates) if dates else None, 'date_to': max(dates) if dates else None,
                           'sha256': hashlib.sha256(raw).hexdigest()})
        self.count += len(rows)
        self.control.check()

    @classmethod
    def encode(cls, payload: dict) -> bytes:
        # Strict JSON data assignment; log text never becomes code or HTML.
        text = json.dumps(payload, ensure_ascii = False, separators = (',', ':'), allow_nan = False)

        for char in ('<', '>', '&', '\u2028', '\u2029'):
            text = text.replace(char, f'\\u{ord(char):04x}')

        return (cls.PREFIX + text + cls.SUFFIX).encode('utf-8')

    def result(self) -> dict:
        return {'version': 1, 'count': self.count, 'page_size': 100, 'timezone': str(self.zone),
                'types': sorted(self.types), 'families': sorted({kind.split('.', 1)[0] for kind in self.types}),
                'parts': self.parts}
