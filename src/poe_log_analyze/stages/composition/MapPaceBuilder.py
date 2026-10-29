from datetime import datetime

from poe_log_analyze.runtime.AreaKind import AreaKind
from poe_log_analyze.runtime.DurationFormatter import DurationFormatter

from poe_log_analyze.stages.composition.MapGapBuilder import MapGapBuilder
from poe_log_analyze.stages.composition.MapRunMetrics import MapRunMetrics
from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection
from poe_log_analyze.stages.composition.VisitMeasurements import VisitMeasurements
from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder
from poe_log_analyze.stages.composition.sessions.SessionHistoryBuilder import SessionHistoryBuilder


class MapPaceBuilder:
    """First-entry pace and the distribution of fully measured map time."""

    @staticmethod
    def duration(seconds: float | None) -> str:
        if seconds is None:
            return '—'

        rounded = round(seconds, 3)
        fraction = f'{rounded - int(rounded):.3f}'[1:].rstrip('0')

        return DurationFormatter.duration_label(rounded) + (fraction if fraction != '.' else '')

    @classmethod
    def statistics(cls, rows: list[dict], play_seconds: float | None = None, map_seconds: float | None = None,
                   *, duration_field: str = 'seconds') -> dict:

        metrics = MapRunMetrics.statistics(rows, play_seconds, map_seconds, duration_field = duration_field)
        rate = metrics['rate']

        return {**metrics, 'play_duration': cls.duration(play_seconds),
                'map_duration': cls.duration(metrics['map_seconds']),
                'rate_label': f'{rate:.2f}' if rate is not None else '—',
                **{key: cls.duration(metrics[key + '_seconds']) for key in ('mean', 'median', 'min', 'max')}}

    @classmethod
    def build(cls, original: list[dict], selected: list[dict], selection: ReportPeriodSelection,
              sessions: SessionHistoryBuilder, daily_playtime: dict, daily_areas: dict, *, afk: dict | None = None) -> dict:

        selection.control.check()
        originals = {(run['area_id'], run['first_line']): run for run in original}
        rows, groups, dates, session_maps = [], {}, {}, {}
        session_seconds = {}

        for run in selected:
            selection.control.check()

            if AreaKind.code(run) != 'map':
                continue

            source = originals[(run['area_id'], run['first_line'])]
            row = cls.record(source, run, selection, sessions, afk = afk)
            rows.append(row)
            groups.setdefault(run['area_id'] or run['name'], []).append(row)
            dates.setdefault(row['date'], []).append(row)
            session_maps.setdefault(row['session_id'], []).append(row)

            for visit in run['visits']:
                first = sessions.session(visit['entry_line'])
                key = str(first) if first is not None else None
                session_seconds[key] = session_seconds.get(key, 0) + VisitMeasurements.seconds(visit)

        rows.sort(key = lambda row: (row['timestamp'] is None,
                  datetime.fromisoformat(row['timestamp']).timestamp() if row['timestamp'] else 0, row['line']))
        types = []

        for group in groups.values():
            selection.control.check()
            types.append({'name': ' / '.join(sorted({row['name'] for row in group})),
                          'icon': group[0]['icon'], 'area_id': group[0]['area_id'], **cls.statistics(group),
                          'without_afk': cls.statistics(group, duration_field = 'remaining_seconds')})

        types.sort(key = lambda row: (-row['count'], row['name'], row['area_id']))
        plays = {day['date']: day for day in daily_playtime['days']}
        days = []

        for day in sorted(set(plays) | set(daily_areas['by_date']) | set(dates)):
            selection.control.check()
            values = dates.get(day, [])
            # Entry date determines the count; measured seconds are split at midnight.
            play = plays.get(day, {}).get('seconds', 0)
            zones = daily_areas['by_date'].get(day, {}).get('zones', [])
            seconds = sum(zone['seconds'] for zone in zones if zone['kind_code'] == 'map')
            days.append({'date': day, **cls.statistics(values, play, seconds)})

        session_rows = []

        for first, session in sorted(sessions.rows.items(), key = lambda item: (datetime.fromisoformat(item[1]['started_at']), item[0])):
            selection.control.check()
            key = str(first)
            session_rows.append({'id': key, 'start': session['start'], 'end': session['end'], 'href': session['path'],
                                 **cls.statistics(session_maps.get(key, []), session['seconds'], session_seconds.get(key, 0))})

        if None in session_maps or None in session_seconds:
            session_rows.append({'id': None, 'start': None, 'end': None, 'href': None,
                                 **cls.statistics(session_maps.get(None, []), None, session_seconds.get(None, 0))})

        complete = [i for i, row in enumerate(rows) if not row['excluded']]
        fast = sorted(complete, key = lambda i: (rows[i]['seconds'], rows[i]['line']))[:10]
        slow = sorted(complete, key = lambda i: (-rows[i]['seconds'], rows[i]['line']))[:10]
        gaps = MapGapBuilder.build(original, sessions, selection, afk = afk)
        summary = cls.statistics(rows, daily_playtime['seconds'])
        remaining = [i for i in complete if rows[i]['remaining_seconds'] is not None]
        without_afk = {'summary': cls.statistics(rows, duration_field = 'remaining_seconds'),
                       'fastest': sorted(remaining, key = lambda i: (rows[i]['remaining_seconds'], rows[i]['line']))[:10],
                       'slowest': sorted(remaining, key = lambda i: (-rows[i]['remaining_seconds'], rows[i]['line']))[:10]}
        cls.afk_rate(summary, afk['summary'] if afk else None)

        for day in days:
            cls.afk_rate(day, afk['by_date'].get(day['date']) if afk else None)

        for session in session_rows:
            cls.afk_rate(session, afk['by_session'].get(session['id']) if afk else None)

        return {'version': '3', 'timezone': selection.zone_name, 'without_afk': without_afk,
                'summary': summary, 'rows': rows, 'types': types,
                'days': days, 'sessions': session_rows, 'fastest': fast, 'slowest': slow,
                'gaps': gaps, 'chart': cls.chart(days)}

    @classmethod
    def afk_rate(cls, row: dict, measurement: dict | None) -> None:
        seconds = measurement['remaining_seconds'] if measurement else None
        rate = row['new'] * 3600 / seconds if seconds else None
        row.update(afk_seconds = measurement['afk_seconds'] if measurement else None,
                   afk_duration = measurement['afk_duration'] if measurement else '—',
                   remaining_seconds = seconds, remaining_duration = cls.duration(seconds),
                   rate_without_afk = rate, rate_without_afk_label = f'{rate:.2f}' if rate is not None else '—')

    @classmethod
    def record(cls, source: dict, run: dict, selection: ReportPeriodSelection, sessions: SessionHistoryBuilder,
               *, afk: dict | None = None) -> dict:

        metrics = MapRunMetrics.record(source, run, selection, sessions, afk = afk)
        stamp = source.get('started_at')
        moment = datetime.fromisoformat(stamp).astimezone(selection.zone) if stamp else None
        first = sessions.session(source['first_line'])

        return {'line': source['first_line'], 'href': LogHistoryBuilder.line_href(source['first_line']),
                'name': run['name'], 'area_id': run['area_id'], 'icon': run.get('icon', ''),
                'timestamp': moment.isoformat() if moment else None,
                'entry': moment.strftime('%d.%m.%Y %H:%M:%S %z') if moment else None,
                'date': moment.date().isoformat() if moment and metrics['new'] else 'outside' if moment else 'undated',
                **metrics, 'duration': cls.duration(metrics['seconds']), 'session_id': str(first) if first is not None else None,
                'session_href': sessions.rows[first]['path'] if first is not None else None}

    @staticmethod
    def chart(days: list[dict]) -> dict:
        dated = [day for day in days if day['date'] not in ('undated', 'outside')]
        maximum = max(1, max((day['rate'] or 0 for day in dated), default = 0))
        bars = []

        for i, day in enumerate(dated):
            height = 220 * (day['rate'] or 0) / maximum
            bars.append({'date': day['date'], 'rate': day['rate'], 'rate_label': day['rate_label'],
                         'new': day['new'], 'play_duration': day['play_duration'],
                         'x': 70 + 860 * i / len(dated), 'width': 720 / len(dated), 'y': 260 - height,
                         'height': height, 'tick': i % max(1, len(dated) // 8) == 0 or i == len(dated) - 1})

        return {'bars': bars, 'ticks': [{'y': 260 - 55 * i, 'rate': f'{maximum * i / 4:.2f}'} for i in range(5)]}
