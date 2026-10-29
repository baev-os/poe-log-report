from datetime import datetime

from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder


class CounterHistoryBuilder:
    """Independent cumulative-counter readings without guessing characters or deltas."""

    TYPES = {'screen.kill_count': 'kills', 'screen.death_count': 'deaths'}

    def __init__(self):
        self.rows = []

    def add(self, row: dict) -> None:
        if (row['status'] != 'recognized' or row['type'] not in self.TYPES
                or row.get('record_id') != row['line_number']):
            return

        stamp = row.get('timestamp')
        moment = datetime.fromisoformat(stamp) if stamp else None
        self.rows.append({'kind': self.TYPES[row['type']], 'count': row['fields']['count'],
                          'line': row['line_number'], 'timestamp': stamp,
                          'time': moment.strftime('%d.%m.%Y %H:%M:%S') if moment else '—',
                          'href': LogHistoryBuilder.line_href(row['line_number'])})

    def result(self) -> dict:
        return {'version': '1', 'rows': self.rows, 'count': len(self.rows)}
