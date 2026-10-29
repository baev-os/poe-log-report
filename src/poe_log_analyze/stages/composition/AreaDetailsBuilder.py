import hashlib
import json

from datetime import datetime

from statistics import mean, median

from poe_log_analyze.runtime.AreaKind import AreaKind

from poe_log_analyze.stages.composition.AfkMeasurements import AfkMeasurements
from poe_log_analyze.stages.composition.MapFlowBuilder import MapFlowBuilder
from poe_log_analyze.stages.composition.MapPaceBuilder import MapPaceBuilder
from poe_log_analyze.stages.composition.MapRunMetrics import MapRunMetrics
from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection
from poe_log_analyze.stages.composition.VisitMeasurements import VisitMeasurements
from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder
from poe_log_analyze.stages.composition.sessions.SessionHistoryBuilder import SessionHistoryBuilder


class AreaDetailsBuilder:
    """History of each area type with original visits and shared map measurements."""

    @staticmethod
    def key(run: dict) -> tuple[str, str]:
        return AreaKind.code(run), run.get('area_id') or run['name']

    @staticmethod
    def path(key: tuple[str, str]) -> str:
        identity = json.dumps(key, ensure_ascii = False).encode('utf-8')
        return 'areas/' + hashlib.sha256(identity).hexdigest() + '/index.html'

    @classmethod
    def build(cls, original: list[dict], selected: list[dict], selection: ReportPeriodSelection,
              sessions: SessionHistoryBuilder, daily_areas: dict, *, afk: dict | None = None) -> dict:

        selection.control.check()
        sources = {(run['area_id'], run['first_line']): run for run in original}
        groups, links = {}, {}

        for run in selected:
            selection.control.check()
            groups.setdefault(cls.key(run), []).append(run)

        pages = []

        for key, runs in sorted(groups.items()):
            selection.control.check()
            rows, records = [], []

            for run in runs:
                selection.control.check()
                source = sources[(run['area_id'], run['first_line'])]
                originals = {visit['entry_line']: visit for visit in source['visits']}

                if key[0] == 'map':
                    records.append(MapRunMetrics.record(source, run, selection, sessions, afk = afk))

                for visit in run['visits']:
                    selection.control.check()
                    rows.append({**AfkMeasurements.visit(visit, afk),
                                 **cls.visit(run, source, visit, originals[visit['entry_line']], selection, sessions, daily_areas)})

            rows.sort(key = cls.order)
            days = {}

            for row in rows:
                day = days.setdefault(row['date'], {'date': row['date'], 'label': row['day_label'],
                    'href': row['calendar_href'], 'rows': [], 'seconds': 0, 'incomplete': 0})
                day['rows'].append(row)
                day['seconds'] += row['seconds'] or 0
                day['incomplete'] += row['incomplete']

            for day in days.values():
                day['duration'] = MapPaceBuilder.duration(day['seconds'] if any(row['seconds'] is not None for row in day['rows']) else None)

            metrics = cls.metrics(records, rows, key[0] == 'map')
            without_afk = cls.metrics(records, rows, key[0] == 'map', duration_field = 'remaining_seconds')
            page = {'path': cls.path(key), 'kind_code': key[0], 'area_id': runs[0].get('area_id', ''),
                    'name': ' / '.join(sorted({run['name'] for run in runs})),
                    'icon': next((run['icon'] for run in runs if run.get('icon')), ''),
                    'count': len(runs), 'visits': len(rows), 'incomplete': sum(row['incomplete'] for row in rows),
                    'seconds': sum(row['seconds'] or 0 for row in rows), 'metrics': metrics,
                    'afk': AfkMeasurements.combine(rows), 'without_afk': without_afk,
                    'days': sorted(days.values(), key = lambda day: (day['date'] == 'undated', day['date'])),
                    'chart': cls.chart(rows, selection),
                    'death_count': len({event['line'] for row in rows for event in row['death_messages']})}
            page['duration'] = MapPaceBuilder.duration(page['seconds'] if any(row['seconds'] is not None for row in rows) else None)
            pages.append(page)
            links.setdefault(key[0], {})[key[1]] = page['path']

        return {'version': '2', 'timezone': selection.zone_name, 'pages': pages, 'links': links}

    @staticmethod
    def order(row: dict) -> tuple:
        stamp = row['entered_at'] or row['exited_at']
        return stamp is None, datetime.fromisoformat(stamp).timestamp() if stamp else 0, row['line']

    @classmethod
    def visit(cls, run: dict, source: dict, visit: dict, original: dict, selection: ReportPeriodSelection,
              sessions: SessionHistoryBuilder, daily_areas: dict) -> dict:

        start = datetime.fromisoformat(visit['entered_at']).astimezone(selection.zone) if visit.get('entered_at') else None
        end = datetime.fromisoformat(visit['ended_at']).astimezone(selection.zone) if visit.get('ended_at') else None
        moment = start or end
        day = moment.date().isoformat() if moment else 'undated'
        parts = VisitMeasurements.parts(visit)
        seconds = VisitMeasurements.seconds(visit) if parts else None
        clipped = VisitMeasurements.seconds(visit) != VisitMeasurements.seconds(original)
        incomplete = not original['bounded'] or original['seconds'] is None
        branched = bool(original.get('branches'))
        first = sessions.session(visit['entry_line'])
        return_visit = (AreaKind.code(run) == 'map' and visit['entry_line'] != source['first_line']
                        and bool(original.get('entered_at'))
                        and selection.period.contains(original['entered_at'], selection.zone_name))

        return {'line': visit['entry_line'], 'anchor': 'visit-' + str(visit['entry_line']),
                'href': LogHistoryBuilder.line_href(visit['entry_line']),
                'entered_at': start.isoformat() if start else None, 'exited_at': end.isoformat() if end else None,
                'entry': start.strftime('%H:%M:%S %z') if start else None,
                'exit': end.strftime('%d.%m.%Y %H:%M:%S %z') if end else None,
                'original_entry': original.get('entered_at'), 'original_exit': original.get('ended_at'),
                'date': day, 'day_label': moment.strftime('%d.%m.%Y') if moment else None,
                'calendar_href': f'maps/{day}/index.html' if day in daily_areas['by_date'] else None,
                'seconds': seconds, 'duration': MapPaceBuilder.duration(seconds),
                'incomplete': incomplete, 'clipped': clipped, 'branched': branched,
                'return': return_visit, 'excluded': incomplete or clipped or branched,
                'session_href': sessions.rows[first]['path'] if first is not None else None,
                'session_label': sessions.rows[first]['start'] if first is not None else None,
                'branches': [MapFlowBuilder.branch(branch, selection.zone) for branch in visit.get('branches', [])],
                **{field: [MapFlowBuilder.event(event, selection.zone) for event in visit.get(field, [])]
                   for field in ('mechanics', 'discoveries', 'mercenaries', 'death_messages')}}

    @staticmethod
    def metrics(records: list[dict], rows: list[dict], maps: bool, *, duration_field: str = 'seconds') -> dict:
        if maps:
            result = MapRunMetrics.statistics(records, duration_field = duration_field)
        else:
            values = [row[duration_field] for row in rows if not row['excluded'] and row.get(duration_field) is not None]
            result = {'complete': len(values), 'excluded': len(rows) - len(values),
                      'mean_seconds': mean(values) if values else None, 'median_seconds': median(values) if values else None}

        return {**result, 'mean': MapPaceBuilder.duration(result['mean_seconds']),
                'median': MapPaceBuilder.duration(result['median_seconds'])}

    @staticmethod
    def chart(rows: list[dict], selection: ReportPeriodSelection) -> dict:
        measured = [row for row in rows if (row['entered_at'] or row['exited_at']) and row['seconds'] is not None]

        if not measured:
            return {'points': [], 'times': [], 'ticks': []}

        stamps = [datetime.fromisoformat(row['entered_at'] or row['exited_at']).timestamp() for row in measured]
        start, end = min(stamps), max(stamps)
        maximum = max(1, max(row['seconds'] for row in measured))
        points = []

        for row, stamp in zip(measured, stamps):
            selection.control.check()
            points.append({'anchor': row['anchor'], 'line': row['line'], 'date': row['day_label'],
                           'time': row['entry'] or row['exit'], 'duration': row['duration'],
                           'partial': row['excluded'],
                           'x': 70 + 860 * (stamp - start) / (end - start) if end != start else 500,
                           'y': 260 - 220 * row['seconds'] / maximum})

        times = [{'x': 70 + 860 * i / 4, 'label': datetime.fromtimestamp(start + (end - start) * i / 4,
                  selection.zone).strftime('%d.%m.%Y %H:%M:%S')} for i in range(5)] if end != start else [
                      {'x': 500, 'label': datetime.fromtimestamp(start, selection.zone).strftime('%d.%m.%Y %H:%M:%S')}]

        return {'points': points, 'times': times,
                'ticks': [{'y': 260 - 55 * i, 'label': f'{maximum * i / 240:.1f}'} for i in range(5)]}
