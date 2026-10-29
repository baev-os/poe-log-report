from datetime import datetime
from zoneinfo import ZoneInfo

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.runtime.DurationFormatter import DurationFormatter

from poe_log_analyze.stages.composition.ActivityAreaGroups import ActivityAreaGroups
from poe_log_analyze.stages.composition.AllTimeStatisticsBuilder import AllTimeStatisticsBuilder
from poe_log_analyze.stages.composition.VisitMeasurements import VisitMeasurements


class ActivityTimelineBuilder:
    """Special-area time and a shared timeline of confirmed visits."""

    @classmethod
    def build(cls, runs: list[dict], timezone_name: str, control: ExecutionContext) -> dict:
        zone = ZoneInfo(timezone_name)
        grouped = {child: [] for children in ActivityAreaGroups.SUBGROUPS.values() for child in children}
        control.check()

        for run in runs:
            control.check()
            code = ActivityAreaGroups.subgroup(run.get('area_id', ''))

            if code:
                grouped[code].append(run)

        groups, moments = [], []
        cursor_y = 30

        for code, color in zip(ActivityAreaGroups.CODES, ActivityAreaGroups.COLORS):
            control.check()
            children = []
            split = len(ActivityAreaGroups.SUBGROUPS[code]) > 1
            heading_y = cursor_y + 14

            if split:
                cursor_y += 28

            for child in ActivityAreaGroups.SUBGROUPS[code]:
                summary = AllTimeStatisticsBuilder.build(grouped[child], control)
                visits = []

                for run in grouped[child]:
                    for visit in [part for original in run['visits'] for part in VisitMeasurements.drawable(original)]:
                        control.check()
                        start = datetime.fromisoformat(visit['entered_at']).astimezone(zone) if visit.get('entered_at') else None
                        end = datetime.fromisoformat(visit['ended_at']).astimezone(zone) if visit.get('ended_at') else None
                        measured = bool(visit['bounded'] and visit['seconds'] is not None)
                        original = visit.get('original_entered_at', visit.get('entered_at'))
                        source_date = datetime.fromisoformat(original).astimezone(zone).date().isoformat() if original else None
                        row = {'name': run['name'], 'line': visit['entry_line'],
                               'is_segment': visit.get('is_segment', False),
                               'entered_at': start.isoformat() if start else None,
                               'ended_at': end.isoformat() if end else None,
                               'entry': start.strftime('%d.%m.%Y %H:%M:%S') if start else '—',
                               'exit': end.strftime('%d.%m.%Y %H:%M:%S') if end else '—',
                               'date': source_date,
                               'start': start.timestamp() if start else None,
                               'end': end.timestamp() if measured and end and start else (start.timestamp() if start else None),
                               'measured': measured,
                               'duration': DurationFormatter.duration_label(visit['seconds']) if measured else '—'}
                        visits.append(row)

                        if row['start'] is not None:
                            moments.extend([row['start'], row['end']])

                visits.sort(key = lambda row: (row['start'] is None, row['start'] or 0, row['line']))
                children.append({'code': child, 'y': cursor_y + 20,
                                 'totals': summary['zone_totals'], 'zones': summary['zones'], 'visits': visits})
                cursor_y += 42

            groups.append({'code': code, 'color': color, 'heading_y': heading_y,
                           'top': heading_y - 20, 'bottom': cursor_y,
                           'totals': AllTimeStatisticsBuilder.total([child['totals'] for child in children]),
                           'children': children})
            cursor_y += 12

        periods = []

        if moments:
            first, last = min(moments), max(moments)
            # A single instant also needs a visible scale without adding time to totals.
            periods.append(cls.period('all', first, max(last, first + 1), zone))
            cursor = datetime.fromtimestamp(first, zone).replace(day = 1, hour = 0, minute = 0, second = 0, microsecond = 0)

            while cursor.timestamp() <= last:
                control.check()
                end = cursor.replace(year = cursor.year + cursor.month // 12, month = cursor.month % 12 + 1)
                periods.append(cls.period(cursor.strftime('%Y-%m'), cursor.timestamp(), end.timestamp(), zone))
                cursor = end

            for group in groups:
                for child in group['children']:
                    for visit in child['visits']:
                        control.check()

                        if visit['start'] is not None:
                            visit['x'] = 220 + 960 * (visit['start'] - first) / (max(last, first + 1) - first)
                            visit['width'] = max(1.5, 960 * (visit['end'] - visit['start']) / (max(last, first + 1) - first))

        return {'version': '4', 'timezone': timezone_name, 'groups': groups, 'periods': periods,
                'height': cursor_y + 60}

    @staticmethod
    def period(key: str, start: float, end: float, zone: ZoneInfo) -> dict:
        ticks = [{'x': 220 + 960 * index / 4,
                  'label': datetime.fromtimestamp(start + (end - start) * index / 4, zone).strftime('%d.%m.%Y %H:%M')}
                 for index in range(5)]
        return {'id': key, 'start': start, 'end': end, 'ticks': ticks}
