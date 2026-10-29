from datetime import datetime, timezone
from statistics import median

from poe_log_analyze.stages.composition.MapPaceBuilder import MapPaceBuilder
from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder


class DisconnectReturnBuilder:
    """Observed interval before entry, not server outage duration."""

    LONG_BREAK_SECONDS = 1800

    @classmethod
    def build(cls, links, sessions, selection) -> dict:
        grouped = {}

        for link in links:
            selection.control.check()

            if selection.period.contains(link['timestamp'], selection.zone_name):
                grouped.setdefault(link['line'], []).append(link)

        rows, measured = [], []

        for line, candidates in sorted(grouped.items()):
            selection.control.check()
            choices = {}

            for item in candidates:
                seconds = ((cls.moment(item['entered_at']) - cls.moment(item['timestamp'])).total_seconds()
                           if item['state'] == 'observed' else None)
                state = 'long_break' if seconds is not None and seconds > cls.LONG_BREAK_SECONDS else item['state']
                choices[(item['entry_line'], state)] = {
                    'state': state, 'entry_line': item['entry_line'], 'area': item['area'],
                    'href': LogHistoryBuilder.line_href(item['entry_line']) if item['entry_line'] else None,
                    'entered_at': item['entered_at'], 'entry': cls.label(item['entered_at'], selection),
                    'seconds': seconds, 'duration': MapPaceBuilder.duration(seconds),
                    'outside_period': not selection.period.contains(item['entered_at'], selection.zone_name),
                }

            options = sorted(choices.values(), key = lambda row: (row['entry_line'] is None, row['entry_line'] or 0, row['state']))
            state = 'ambiguous' if len(options) > 1 else options[0]['state']
            first = sessions.session(line)

            if state == 'observed':
                measured.append(options[0]['seconds'])

            rows.append({'line': line, 'href': LogHistoryBuilder.line_href(line), 'kind': candidates[0]['kind'],
                         'timestamp': candidates[0]['timestamp'], 'time': cls.label(candidates[0]['timestamp'], selection),
                         'state': state, 'choices': options,
                         'session_href': sessions.rows[first]['path'] if first is not None else None})

        return {'version': '1', 'long_break_seconds': cls.LONG_BREAK_SECONDS, 'rows': rows, 'count': len(rows),
                'states': {state: sum(row['state'] == state for row in rows)
                           for state in ('observed', 'long_break', 'ambiguous', 'clock', 'missing_time', 'no_entry')},
                'sample_count': len(measured), 'median_seconds': median(measured) if measured else None,
                'median': MapPaceBuilder.duration(median(measured) if measured else None)}

    @staticmethod
    def moment(stamp: str) -> datetime:
        return datetime.fromisoformat(stamp).astimezone(timezone.utc)

    @staticmethod
    def label(stamp, selection) -> str | None:
        return datetime.fromisoformat(stamp).astimezone(selection.zone).strftime('%d.%m.%Y %H:%M:%S %z') if stamp else None
