import json

from datetime import datetime

from typing import TextIO

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue


class LogHistoryBuilder:
    """Complete line-by-line view of the merged registry without event-type filtering."""

    PAGE_SIZE = 500

    def __init__(self, stream: TextIO, control: ExecutionContext):
        self.stream = stream
        self.control = control
        self.pages = []
        self.rows = []
        self.dates = {}
        self.count = 0
        self.types = set()

    @classmethod
    def page_path(cls, number):
        return 'index.html' if number == 1 else f'page-{number}.html'

    @classmethod
    def line_href(cls, line):
        page = (line - 1) // cls.PAGE_SIZE + 1
        return f'events/{cls.page_path(page)}#line-{line}'

    def add(self, row):
        number = self.count // self.PAGE_SIZE + 1
        stamp = row.get('timestamp')
        moment = datetime.fromisoformat(stamp) if stamp else None
        original = row.get('text')
        header = RuleCatalogue.HEADER.fullmatch(original) if original is not None else None
        family = row['type'].split('.', 1)[0]
        parent = row.get('record_id')
        line = row['line_number']
        self.rows.append({
            'line': line, 'timestamp': stamp,
            'time': moment.strftime('%Y-%m-%d %H:%M:%S') if moment else None,
            'timestamp_raw': row.get('timestamp_raw'),
            'type': row['type'], 'family': family, 'status': row['status'],
            'message': header['message'] if header else original, 'original': original,
            'fields': row['fields'], 'reason': row.get('reason'),
            'raw_base64': row.get('raw_base64') if original is None else None,
            'parent': (f"{self.page_path((parent - 1) // self.PAGE_SIZE + 1)}#line-{parent}"
                       if parent and parent != line else None),
            'history_boundary': bool(row.get('history_boundary')),
        })
        self.count += 1
        self.types.add(family)

        if moment:
            date = moment.date().isoformat()
            self.dates.setdefault(date, {'date': date, 'label': moment.strftime('%d.%m.%Y'),
                                         'href': f'{self.page_path(number)}#line-{line}'})

        if len(self.rows) == self.PAGE_SIZE:
            self._flush()

    def _flush(self):
        """One temporary JSONL record per page; preserve field order."""

        self.control.check()
        number = len(self.pages) + 1
        self.stream.write(json.dumps(self.rows, ensure_ascii = False, separators = (',', ':')) + '\n')
        self.pages.append({'number': number, 'path': self.page_path(number),
                           'first': self.rows[0]['line'] if self.rows else 0,
                           'last': self.rows[-1]['line'] if self.rows else 0})
        self.rows = []
        self.control.check()

    def result(self):
        if self.rows or not self.pages:
            self._flush()

        for index, page in enumerate(self.pages):
            page['previous'] = self.pages[index - 1]['path'] if index else None
            page['next'] = self.pages[index + 1]['path'] if index + 1 < len(self.pages) else None

        return {'version': '2', 'count': self.count, 'page_size': self.PAGE_SIZE,
                'types': sorted(self.types), 'dates': [self.dates[key] for key in sorted(self.dates)],
                'pages': self.pages}
