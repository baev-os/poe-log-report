from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.stages.composition.AllTimeStatisticsBuilder import AllTimeStatisticsBuilder
from poe_log_analyze.stages.composition.VisitMeasurements import VisitMeasurements


class DailyAreaStatisticsBuilder:
    """Time in all areas by local day without reconstructing unknown boundaries."""

    @classmethod
    def build(cls, runs: list[dict], timezone_name: str, dates: set[str], control: ExecutionContext) -> dict:
        zone = ZoneInfo(timezone_name)
        days = {date: [] for date in dates}

        for run in runs:
            control.check()
            fragments = {}

            for visit in run['visits']:
                control.check()

                for date, part in cls.split_visit(visit, zone, control):
                    fragments.setdefault(date, []).append(part)

            for date, visits in fragments.items():
                days.setdefault(date, []).append({**run, 'visits': visits})

        keys = sorted(days, key = lambda date: (date != 'undated', date), reverse = True)
        summaries = {}

        for index, date in enumerate(keys):
            control.check()
            summary = AllTimeStatisticsBuilder.build(days[date], control)
            summaries[date] = {
                'date': date,
                'label': datetime.fromisoformat(date).strftime('%d.%m.%Y') if date != 'undated' else 'Дата входа неизвестна',
                'newer': keys[index - 1] if index else None,
                'older': keys[index + 1] if index + 1 < len(keys) else None,
                'zones': summary['zones'], 'zone_totals': summary['zone_totals'], 'kinds': summary['kinds'],
            }

        return {'version': '1', 'timezone': timezone_name, 'by_date': summaries}

    @classmethod
    def split_visit(cls, visit: dict, zone: ZoneInfo, control: ExecutionContext) -> list[tuple[str, dict]]:
        if 'segments' not in visit:
            return cls.split_part(visit, zone, control)

        dates = {}

        for segment in VisitMeasurements.drawable(visit):
            for date, part in cls.split_part(segment, zone, control):
                dates.setdefault(date, []).append(part)

        return [(date, {'bounded': all(p['bounded'] for p in parts),
                        'seconds': sum(p['seconds'] or 0 for p in parts) if all(p['bounded'] for p in parts) else None,
                        'segments': [p for p in parts if p['bounded']]}) for date, parts in sorted(dates.items())]

    @staticmethod
    def split_part(visit: dict, zone: ZoneInfo, control: ExecutionContext) -> list[tuple[str, dict]]:
        entered = visit.get('entered_at')

        if not entered:
            return [('undated', {'bounded': False, 'seconds': None})]

        start = datetime.fromisoformat(entered).astimezone(timezone.utc)
        date = start.astimezone(zone).date()

        if not visit['bounded'] or not visit.get('ended_at'):
            return [(date.isoformat(), {'bounded': False, 'seconds': None})]

        end = datetime.fromisoformat(visit['ended_at']).astimezone(timezone.utc)

        if start == end:
            return [(date.isoformat(), {'bounded': True, 'seconds': 0})]

        parts = []

        while start < end:
            control.check()
            date = start.astimezone(zone).date()
            midnight = datetime.combine(date + timedelta(days = 1), time(), zone).astimezone(timezone.utc)
            stop = min(end, midnight)
            parts.append((date.isoformat(), {'bounded': True, 'seconds': (stop - start).total_seconds()}))
            start = stop

        return parts
