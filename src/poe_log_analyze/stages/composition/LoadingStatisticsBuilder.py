from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod

from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder
from poe_log_analyze.stages.composition.sessions.SessionHistoryBuilder import SessionHistoryBuilder


class LoadingStatisticsBuilder:
    """LOADING SCREEN durations from the merged registry within the selected period."""

    def __init__(self, period: ReportPeriod, zone_name: str, control: ExecutionContext,
                 sessions: SessionHistoryBuilder | None = None):

        self.period, self.zone_name, self.control, self.sessions = period, zone_name, control, sessions
        self.zone = ZoneInfo(zone_name)
        self.rows = []

    def add(self, row: dict) -> None:
        self.control.check()

        if (row['type'] != 'loading.duration' or row['status'] != 'recognized'
                or row.get('record_id') != row['line_number']
                or not self.period.contains(row.get('timestamp'), self.zone_name)):
            return

        stamp = row.get('timestamp')
        moment = datetime.fromisoformat(stamp).astimezone(self.zone) if stamp else None
        first = self.sessions.session(row['line_number']) if self.sessions is not None else None
        session = self.sessions.rows[first] if self.sessions is not None and first is not None else None
        self.rows.append({
            'line': row['line_number'], 'href': LogHistoryBuilder.line_href(row['line_number']),
            'timestamp': moment.isoformat() if moment else None,
            'time': moment.strftime('%d.%m.%Y %H:%M:%S %z') if moment else None,
            'date': moment.date().isoformat() if moment else 'undated',
            'area': row['fields']['area'], 'seconds': row['fields']['seconds'],
            'session_id': str(first) if session else None,
            'session_href': session['path'] if session else None,
            'session_start': session['start'] if session else None,
            'session_end': session['end'] if session else None,
        })

    @staticmethod
    def label(value: Decimal | None) -> str:
        if value is None:
            return '—'

        rounded = round(value, 3) if value >= Decimal('.001') else value

        return format(rounded, 'f').rstrip('0').rstrip('.') if '.' in format(rounded, 'f') else format(rounded, 'f')

    def statistics(self, rows: list[dict]) -> dict:
        values = []

        for row in rows:
            self.control.check()
            values.append(Decimal(row['seconds']))

        values.sort()
        count = len(values)
        total = sum(values, Decimal(0))
        median = ((values[(count - 1) // 2] + values[count // 2]) / 2) if count else None
        measures = {'total': total, 'mean': total / count if count else None,
                    'median': median, 'max': values[-1] if count else None}

        return {'count': count, **{key + '_seconds': str(value) if value is not None else None
                                  for key, value in measures.items()},
                **{key: self.label(value) if key in ('mean', 'median') or value is None else format(value, 'f')
                   for key, value in measures.items()}}

    def result(self) -> dict:
        self.control.check()
        rows = sorted(self.rows, key = lambda row: (row['timestamp'] is None,
                      datetime.fromisoformat(row['timestamp']).timestamp() if row['timestamp'] else 0, row['line']))
        areas, days, sessions = {}, {}, {}

        for row in rows:
            self.control.check()
            areas.setdefault(row['area'], []).append(row)
            days.setdefault(row['date'], []).append(row)
            sessions.setdefault(row['session_id'], []).append(row)

        area_rows = [{'area': name, **self.statistics(items)} for name, items in areas.items()]
        area_rows.sort(key = lambda row: (-Decimal(row['total_seconds']), row['area']))
        day_rows = [{'date': date, **self.statistics(items)} for date, items in sorted(days.items())]
        session_rows = []

        for key, items in sessions.items():
            self.control.check()
            sample = items[0]
            session_rows.append({'id': key, 'href': sample['session_href'], 'start': sample['session_start'],
                                 'end': sample['session_end'], **self.statistics(items)})

        session_rows.sort(key = lambda row: row['id'] is None)
        top = sorted(range(len(rows)), key = lambda i: (-Decimal(rows[i]['seconds']), rows[i]['line']))[:20]

        return {'version': '1', 'timezone': self.zone_name, 'summary': self.statistics(rows),
                'rows': rows, 'areas': area_rows, 'days': day_rows, 'sessions': session_rows,
                'slowest': top, 'chart': self.chart(rows), 'undated': len(days.get('undated', []))}

    def chart(self, rows: list[dict]) -> dict:
        dated = [(i, row) for i, row in enumerate(rows) if row['timestamp']]

        if not dated:
            return {'points': [], 'ticks': [], 'time_ticks': []}

        start = datetime.fromisoformat(dated[0][1]['timestamp']).timestamp()
        end = datetime.fromisoformat(dated[-1][1]['timestamp']).timestamp()
        maximum = max(Decimal(row['seconds']) for _, row in dated) or Decimal(1)
        points = []

        for index, row in dated:
            self.control.check()
            instant = datetime.fromisoformat(row['timestamp']).timestamp()
            points.append({'index': index, 'x': round(70 + 860 * (instant - start) / (end - start), 2) if end > start else 500,
                           'y': round(260 - 220 * float(Decimal(row['seconds']) / maximum), 2)})

        ticks = [{'y': 260 - 55 * i, 'seconds': self.label(maximum * i / 4)} for i in range(5)]
        time_ticks = []

        for i in range(1 if start == end else 6):
            fraction = i / 5 if start != end else .5
            moment = datetime.fromtimestamp(start + (end - start) * fraction, self.zone)
            time_ticks.append({'x': 70 + 860 * fraction, 'date': moment.strftime('%d.%m.%Y'),
                               'time': moment.strftime('%H:%M:%S %z')})

        return {'points': points, 'ticks': ticks, 'time_ticks': time_ticks}
