from datetime import datetime

from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection
from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder
from poe_log_analyze.stages.composition.sessions.SessionHistoryBuilder import SessionHistoryBuilder


class CharacterDeathBuilder:
    """Named death messages; the area belongs to the observing client."""

    TYPES = ('screen.slain', 'screen.suicide')

    def __init__(self, runs: list[dict], selection: ReportPeriodSelection,
                 sessions: SessionHistoryBuilder | None = None):

        self.selection, self.sessions = selection, sessions
        self.rows, self.contexts = [], {}
        selection.control.check()

        for run in runs:
            selection.control.check()
            entries = {}

            for visit in run['visits']:
                for event in visit.get('death_messages', []):
                    entries.setdefault(event['line'], set()).add(visit['entry_line'])

            for event in run.get('death_messages', []):
                entries.setdefault(event['line'], {run['first_line']})

            for line, visits in entries.items():
                selection.control.check()

                for entry in visits:
                    key = (run['area_id'], run['first_line'], entry)
                    self.contexts.setdefault(line, {})[key] = {
                        'area_id': run['area_id'], 'name': run['name'], 'icon': run.get('icon', ''),
                        'href': LogHistoryBuilder.line_href(entry),
                    }

    def add(self, row: dict) -> None:
        if (row['type'] not in self.TYPES or row['status'] != 'recognized'
                or row.get('record_id') != row['line_number']
                or not self.selection.period.contains(row.get('timestamp'), self.selection.zone_name)):
            return

        self.selection.control.check()
        stamp = row.get('timestamp')
        moment = datetime.fromisoformat(stamp).astimezone(self.selection.zone) if stamp else None
        contexts = list(self.contexts.get(row['line_number'], {}).values())
        first = self.sessions.session(row['line_number']) if self.sessions is not None else None
        session = self.sessions.rows[first] if first is not None else None
        self.rows.append({
            'line': row['line_number'], 'href': LogHistoryBuilder.line_href(row['line_number']),
            'character': row['fields']['character'], 'code': row['type'],
            'timestamp': moment.isoformat() if moment else None,
            'time': moment.strftime('%d.%m.%Y %H:%M:%S %z') if moment else None,
            'date': moment.date().isoformat() if moment else 'undated',
            'area': contexts[0] if len(contexts) == 1 else None,
            'area_status': 'known' if len(contexts) == 1 else 'ambiguous' if contexts else 'unknown',
            'session_href': session['path'] if session else None,
            'session_start': session['start'] if session else None,
        })

    def result(self) -> dict:
        self.selection.control.check()
        grouped = {}

        for row in sorted(self.rows, key = lambda row: (row['timestamp'] is None,
                          datetime.fromisoformat(row['timestamp']).timestamp() if row['timestamp'] else 0, row['line'])):
            self.selection.control.check()
            grouped.setdefault(row['character'], []).append(row)

        return {name: self.summary(rows) for name, rows in grouped.items()}

    @staticmethod
    def summary(rows: list[dict]) -> dict:
        days, areas = {}, {}

        for row in rows:
            day = days.setdefault(row['date'], {'date': row['date'], 'count': 0, 'self_inflicted': 0,
                                               'line': row['line']})
            day['count'] += 1
            day['self_inflicted'] += row['code'] == 'screen.suicide'
            area = row['area']
            key = (area['area_id'], area['name']) if area else (None, row['area_status'])
            group = areas.setdefault(key, {'area': area, 'status': row['area_status'], 'count': 0})
            group['count'] += 1

        return {'rows': rows, 'count': len(rows),
                'self_inflicted': sum(row['code'] == 'screen.suicide' for row in rows),
                'days': [days[day] for day in sorted(days)],
                'areas': sorted(areas.values(), key = lambda area: (-area['count'],
                                area['area']['name'] if area['area'] else area['status']))}

    @staticmethod
    def markers(chart: dict, rows: list[dict]) -> list[dict]:
        if not chart['events']:
            return []

        grouped = {}
        start, end = chart['start'], chart['end']

        for row in rows:
            if not row['timestamp']:
                continue

            instant = datetime.fromisoformat(row['timestamp']).timestamp()

            if start <= instant <= end:
                marker = grouped.setdefault(instant, {'line': row['line'], 'time': row['time'], 'count': 0,
                    'x': round(60 + 880 * (instant - start) / (end - start), 2) if end != start else 500})
                marker['count'] += 1

        return list(grouped.values())
