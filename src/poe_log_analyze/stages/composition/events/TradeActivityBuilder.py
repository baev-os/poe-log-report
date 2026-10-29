import re

from datetime import datetime, timezone

from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder
from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue


class TradeActivityBuilder:
    """Trade events and explicit request templates; transaction contents remain unknown."""

    REQUESTS = (
        re.compile(r'Hi, I would like to buy your .+ (?:listed for .+|for my .+) in .+', re.DOTALL),
        re.compile(r'Здравствуйте, хочу купить у вас .+ (?:за .+|по цене .+) в .+', re.DOTALL),
    )
    KINDS = ('accepted', 'cancelled', 'incoming_request', 'outgoing_request')

    def __init__(self, selection, sessions):
        self.selection, self.sessions = selection, sessions
        self.rows, self.unclassified_whispers = [], 0
        self.segment = 0

    def add(self, row) -> None:
        if row.get('history_boundary'):
            self.segment = row['line_number']

        if row['status'] != 'recognized' or not self.selection.period.contains(row.get('timestamp'), self.selection.zone_name):
            return

        fields, kind = row['fields'], None

        if row['type'] == 'screen.trade':
            kind = fields['state']
        elif row['type'] == 'chat.whisper':
            if any(pattern.fullmatch(fields['message']) for pattern in self.REQUESTS):
                kind = 'outgoing_request' if fields['direction'] == 'To' else 'incoming_request'
            else:
                self.unclassified_whispers += 1

        if kind not in self.KINDS:
            return

        first = self.sessions.session(row['line_number'])
        stamp = row.get('timestamp')
        moment = datetime.fromisoformat(stamp).astimezone(self.selection.zone) if stamp else None
        text = row.get('text') or ''
        header = RuleCatalogue.HEADER.fullmatch(text)
        self.rows.append({'line': row['line_number'], 'href': LogHistoryBuilder.line_href(row['line_number']),
                          'kind': kind, 'segment': self.segment, 'timestamp': stamp,
                          'date': moment.date().isoformat() if moment else 'undated',
                          'time': moment.strftime('%d.%m.%Y %H:%M:%S %z') if moment else None,
                          'session_id': str(first) if first is not None else None,
                          'session_href': self.sessions.rows[first]['path'] if first is not None else None,
                          'message': header['message'] if header else text, 'character': fields.get('character')})

    def result(self) -> dict:
        days, sessions = {}, {}

        for row in self.rows:
            self.selection.control.check()
            days.setdefault(row['date'], []).append(row)
            sessions.setdefault(row['session_id'], []).append(row)

        return {'version': '1', 'rows': self.rows, 'summary': self.counts(self.rows),
                'unclassified_whispers': self.unclassified_whispers,
                'days': [{'date': key, **self.counts(rows)} for key, rows in sorted(days.items())],
                'sessions': [{'id': key, 'href': rows[0]['session_href'], **self.counts(rows)}
                             for key, rows in sorted(sessions.items(), key = lambda item: (item[0] is None, item[0] or ''))]}

    @classmethod
    def counts(cls, rows) -> dict:
        return {kind: sum(row['kind'] == kind for row in rows) for kind in cls.KINDS}

    @classmethod
    def enrich(cls, model, explorer, gaps, selection) -> None:
        previous, pairs = {}, []

        for row in model['rows']:
            selection.control.check()

            if row['kind'] != 'accepted' or row['session_id'] is None or not row['timestamp']:
                continue

            key = row['segment'], row['session_id']
            left = previous.get(key)
            previous[key] = row

            if left is None or not left['timestamp']:
                continue

            a, b = cls.moment(left['timestamp']), cls.moment(row['timestamp'])

            if b < a:
                continue

            maps = [item['line'] for item in explorer['rows'] if item['session_id'] == row['session_id']
                    and item['new'] and left['line'] < item['line'] < row['line']]
            pairs.append({'from_href': left['href'], 'to_href': row['href'], 'from_line': left['line'],
                          'to_line': row['line'], 'session_href': row['session_href'],
                          'seconds': (b - a).total_seconds(), 'maps': maps, 'count': len(maps)})

        marked = []

        for gap in gaps['rows']:
            selection.control.check()
            a, b = cls.moment(gap['started_at']), cls.moment(gap['ended_at'])
            events = [row for row in model['rows'] if row['session_id'] == gap['session_id'] and row['timestamp']
                      and gap['from_line'] <= row['line'] < gap['line'] and a <= cls.moment(row['timestamp']) <= b]

            if events:
                marked.append({'gap': dict(gap), 'events': [dict(row) for row in events], **cls.counts(events)})

        model.update(between_exchanges = pairs, gaps = marked)

    @staticmethod
    def moment(stamp: str) -> datetime:
        return datetime.fromisoformat(stamp).astimezone(timezone.utc)
