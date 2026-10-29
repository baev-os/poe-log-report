from datetime import datetime
from decimal import Decimal

from poe_log_analyze.runtime.DurationFormatter import DurationFormatter

from poe_log_analyze.stages.composition.DailyPlaytimeBuilder import DailyPlaytimeBuilder
from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder


class DayOverviewBuilder:
    """Day summary from measured sessions and dated merged-history events."""

    @staticmethod
    def events(timeline: dict, selection) -> list[dict]:
        rows = []

        for day in timeline['by_date'].values():
            for event in day['events']:
                selection.control.check()

                if (event['type'] not in ('area.enter', 'log.open')
                        and selection.period.contains(event['timestamp'], selection.zone_name)):
                    rows.append(event)

        return rows

    @staticmethod
    def date(stamp: str | None, selection) -> str:
        return datetime.fromisoformat(stamp).astimezone(selection.zone).date().isoformat() if stamp else 'undated'

    @classmethod
    def dates(cls, timeline: dict, loading: dict, selection) -> set[str]:
        return {cls.date(event['timestamp'], selection) for event in cls.events(timeline, selection)} | {
            row['date'] for row in loading['rows']}

    @classmethod
    def build(cls, timeline: dict, loading: dict, sessions: dict, intervals: list[dict],
              daily_playtime: dict, daily_areas: dict, selection) -> dict:

        play = {day['date']: day for day in daily_playtime['days']}
        days = {key: {'date': key, 'seconds': play.get(key, {}).get('seconds', 0),
                      'duration': DurationFormatter.duration_label(play.get(key, {}).get('seconds', 0)),
                      'sessions': [], 'events': [], 'loading': [], 'loading_seconds': '0'}
                for key in daily_areas['by_date']}
        grouped = {}

        for part in intervals:
            selection.control.check()
            grouped.setdefault(str(part['first_line']), []).append(part)

        for session in sessions['rows']:
            selection.control.check()
            parts = grouped.get(session['id'], [])
            measured = DailyPlaytimeBuilder.build({'intervals': parts}, selection.zone_name)
            amounts = {day['date']: day['seconds'] for day in measured['days'] if day['seconds'] > 0}

            for part in parts:
                if part['seconds'] == 0:
                    amounts.setdefault(cls.date(part['started_at'], selection), 0)

            for key, seconds in amounts.items():
                if key in days:
                    days[key]['sessions'].append({'id': session['id'], 'href': session['path'],
                        'start': session['start'], 'end': session['end'], 'seconds': seconds,
                        'duration': DurationFormatter.duration_label(seconds), 'ending_reasons': session['ending_reasons']})

        for event in cls.events(timeline, selection):
            days[cls.date(event['timestamp'], selection)]['events'].append({
                'event': event, 'href': LogHistoryBuilder.line_href(event['line_number'])})

        for row in loading['rows']:
            selection.control.check()
            days[row['date']]['loading'].append(row)

        for day in days.values():
            selection.control.check()
            day['events'].sort(key = lambda item: (not bool(item['event']['timestamp']),
                datetime.fromisoformat(item['event']['timestamp']).timestamp() if item['event']['timestamp'] else 0,
                item['event']['line_number']))
            day['loading_seconds'] = str(sum((Decimal(row['seconds']) for row in day['loading']), Decimal(0)))

        return {'version': '1', 'by_date': days}
