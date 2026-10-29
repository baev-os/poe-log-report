import hashlib
import json

from datetime import date, datetime, timedelta, timezone

from poe_log_analyze.core.request.ReportPeriod import ReportPeriod

from poe_log_analyze.runtime.AreaKind import AreaKind

from poe_log_analyze.stages.composition.MapPaceBuilder import MapPaceBuilder
from poe_log_analyze.stages.composition.AfkStatisticsBuilder import AfkStatisticsBuilder
from poe_log_analyze.stages.composition.PeriodComparisonBuilder import PeriodComparisonBuilder
from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection
from poe_log_analyze.stages.composition.VisitMeasurements import VisitMeasurements
from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder
from poe_log_analyze.stages.composition.sessions.SessionHistoryBuilder import SessionHistoryBuilder


class WeeklyPaceBuilder:
    """Weekly history slices using shared map-instance measurements."""

    METRICS = (('play_seconds', 'weekly.play', 'duration'), ('new', 'pace.new', 'number'),
               ('returns', 'pace.returns', 'number'), ('rate', 'pace.rate_label', 'number'),
               ('afk_seconds', 'afk.marked', 'duration'), ('afk_share', 'comparison.afk_share', 'share'),
               ('remaining_seconds', 'afk.remaining_duration', 'duration'),
               ('rate_without_afk', 'afk.rate_without', 'number'),
               ('map_seconds', 'pace.measured', 'duration'), ('mean_seconds', 'pace.mean', 'duration'),
               ('median_seconds', 'pace.median', 'duration'))

    @staticmethod
    def monday(day: date) -> date:
        return day - timedelta(days = day.weekday())

    @staticmethod
    def key(run: dict) -> str:
        value = ('id', run['area_id']) if run.get('area_id') else ('name', run['name'])
        return hashlib.sha256(json.dumps(value, ensure_ascii = False).encode('utf-8')).hexdigest()

    @classmethod
    def build(cls, original: list[dict], selected: list[dict], selection: ReportPeriodSelection,
              sessions: SessionHistoryBuilder, daily_playtime: dict, daily_areas: dict, *, afk: dict | None = None) -> dict:

        control = selection.control
        control.check()
        dates = sorted(date.fromisoformat(day) for day in daily_areas['by_date'] if day != 'undated')
        first = selection.period.date_from or (dates[0] if dates else None)
        last = selection.period.date_to or (dates[-1] if dates else None)
        weeks = []
        plays = {row['date']: row['seconds'] for row in daily_playtime['days']}

        if first is not None and last is not None and first <= last:
            day = cls.monday(first)

            while day <= last:
                control.check()
                weeks.append(cls.week(day, max(day, first), min(day + timedelta(days = 6), last), plays, daily_areas,
                                      afk['by_date'] if afk else {}))
                day += timedelta(days = 7)

        candidates = {week['date']: [] for week in weeks}
        sources = {(run['area_id'], run['first_line']): run for run in original}
        maps = [run for run in selected if AreaKind.code(run) == 'map']
        groups, undated = {}, []

        for run in maps:
            control.check()
            key = cls.key(run)
            groups.setdefault(key, []).append(run)
            touched = cls.touched(run, selection)

            if not touched:
                undated.append(key)

            for day in touched:
                if day in candidates:
                    candidates[day].append(run)

        for week in weeks:
            control.check()
            period = ReportPeriod(date.fromisoformat(week['from']), date.fromisoformat(week['to']))
            part = ReportPeriodSelection(period, selection.zone_name, control)
            records = []

            for run in part.runs(candidates[week['date']]):
                source = sources[(run['area_id'], run['first_line'])]
                record = MapPaceBuilder.record(source, run, part, sessions)
                record.update(key = cls.key(run), visits = cls.visits(run, selection))
                records.append(record)

            week['records'] = sorted(records, key = lambda row: row['line'])

        panels = [cls.panel('all', None, weeks, len(undated), control)]

        for key, runs in sorted(groups.items(), key = lambda item: (item[1][0]['name'], item[0])):
            panel = cls.panel(key, runs[0], weeks, undated.count(key), control)
            panel['name'] = ' / '.join(sorted({run['name'] for run in runs}))
            panels.append(panel)

        return {'version': '2', 'timezone': selection.zone_name, 'weeks': weeks, 'panels': panels}

    @classmethod
    def touched(cls, run: dict, selection: ReportPeriodSelection) -> set[str]:
        result = set()

        for visit in run['visits']:
            selection.control.check()
            parts = VisitMeasurements.parts(visit)

            for part in [*parts, visit]:
                stamp = part.get('entered_at') or part.get('ended_at')

                if not stamp:
                    continue

                start = datetime.fromisoformat(stamp).astimezone(timezone.utc)
                end = datetime.fromisoformat(part['ended_at']).astimezone(timezone.utc) if part.get('ended_at') else start
                end = end - timedelta(microseconds = 1) if end > start else start
                day = cls.monday(start.astimezone(selection.zone).date())
                last = cls.monday(end.astimezone(selection.zone).date())

                while day <= last:
                    selection.control.check()
                    result.add(day.isoformat())
                    day += timedelta(days = 7)

        return result

    @staticmethod
    def week(day: date, first: date, last: date, plays: dict, areas: dict, afk_days: dict) -> dict:
        days, zones = [], {'maps': 0, 'hideout': 0, 'other': 0}
        current = first

        while current <= last:
            key = current.isoformat()
            summary = areas['by_date'].get(key, {})
            days.append({'date': key, 'seconds': plays.get(key, 0), 'duration': MapPaceBuilder.duration(plays.get(key, 0)),
                         'afk_seconds': afk_days.get(key, {}).get('afk_seconds', 0),
                         'href': f'maps/{key}/index.html' if summary else None})

            for row in summary.get('zones', []):
                code = 'maps' if row['kind_code'] == 'map' else 'hideout' if row['kind_code'] == 'hideout' else 'other'
                zones[code] += row['seconds']

            current += timedelta(days = 1)

        total = sum(zones.values())

        return {'date': day.isoformat(), 'label': day.strftime('%d.%m.%Y'),
                'from': first.isoformat(), 'to': last.isoformat(), 'days': days,
                'partial': first != day or last != day + timedelta(days = 6),
                'active_days': sum(row['seconds'] > 0 for row in days),
                'play_seconds': sum(row['seconds'] for row in days),
                'afk': AfkStatisticsBuilder.values(sum(row['seconds'] for row in days),
                                                   sum(row['afk_seconds'] for row in days)),
                'zones': [{'code': code, 'seconds': value, 'duration': MapPaceBuilder.duration(value),
                           'share': value * 100 / total if total else None} for code, value in zones.items()]}

    @staticmethod
    def visits(run: dict, selection: ReportPeriodSelection) -> list[dict]:
        rows = []

        for visit in run['visits']:
            selection.control.check()
            stamp = visit.get('entered_at') or visit.get('ended_at')
            rows.append({'line': visit['entry_line'], 'href': LogHistoryBuilder.line_href(visit['entry_line']),
                         'entry': datetime.fromisoformat(stamp).astimezone(selection.zone).strftime('%d.%m.%Y %H:%M:%S') if stamp else None,
                         'duration': MapPaceBuilder.duration(VisitMeasurements.seconds(visit) if VisitMeasurements.parts(visit) else None)})

        return rows

    @classmethod
    def panel(cls, key: str, run: dict | None, weeks: list[dict], undated: int, control) -> dict:
        rows = []

        for index, week in enumerate(weeks):
            control.check()
            indices = [i for i, record in enumerate(week['records']) if key == 'all' or record['key'] == key]
            metrics = MapPaceBuilder.statistics([week['records'][i] for i in indices], week['play_seconds'])
            MapPaceBuilder.afk_rate(metrics, week['afk'])
            metrics['afk_share'] = week['afk']['afk_share'] if week['play_seconds'] else None
            previous = rows[-1] if rows else None
            changes = [PeriodComparisonBuilder.row(code, label, kind, previous[code] if previous else None, metrics[code])
                       for code, label, kind in cls.METRICS]
            rows.append({'week': index, 'date': week['date'], 'label': week['label'], 'indices': indices,
                         'changes': changes, 'comparison_partial': bool(previous and (week['partial'] or weeks[index - 1]['partial'])),
                         **metrics})

        charts = []

        rate_maximum = max(1, max((row[key] or 0 for row in rows for key in ('rate', 'rate_without_afk')), default = 0))

        for code, field in (('rate', 'rate_label'), ('rate_without_afk', 'rate_without_afk_label'), ('median_seconds', 'median')):
            maximum = max(1, max((row[code] or 0 for row in rows), default = 0))

            if code != 'median_seconds':
                maximum = rate_maximum

            bars = [{'date': row['date'], 'label': row['label'], 'value': row[code], 'value_label': row[field],
                     'x': 70 + 860 * i / len(rows), 'y': 260 - 220 * (row[code] or 0) / maximum,
                     'width': min(60, 720 / len(rows)), 'height': 220 * (row[code] or 0) / maximum,
                     'tick': i % max(1, len(rows) // 8) == 0 or i == len(rows) - 1} for i, row in enumerate(rows)]
            charts.append({'code': code, 'bars': bars, 'ticks': [{'y': 260 - 55 * i,
                           'label': f'{maximum * i / 4:.2f}' if code != 'median_seconds' else MapPaceBuilder.duration(maximum * i / 4)} for i in range(5)]})

        return {'key': key, 'name': run['name'] if run else None, 'area_id': run['area_id'] if run else None,
                'icon': run.get('icon', '') if run else '', 'undated': undated, 'rows': rows, 'charts': charts,
                'path': f'pace/weeks/{key}/index.html' if key != 'all' else 'pace/weeks/index.html'}
