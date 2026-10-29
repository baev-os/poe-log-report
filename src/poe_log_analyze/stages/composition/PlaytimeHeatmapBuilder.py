from collections import Counter
from datetime import datetime, timedelta, timezone
from math import ceil, floor
from zoneinfo import ZoneInfo

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.runtime.AreaKind import AreaKind
from poe_log_analyze.runtime.DurationFormatter import DurationFormatter

from poe_log_analyze.stages.composition.ActivityAreaGroups import ActivityAreaGroups
from poe_log_analyze.stages.composition.VisitMeasurements import VisitMeasurements


class PlaytimeHeatmapBuilder:
    """Measured hours by weekday with individual dates linking to the calendar."""

    FILTERS = ('all', 'maps', 'hideout', 'special')

    @staticmethod
    def filters(run: dict) -> list[str]:
        if run.get('category') == 'unallocated':
            return []

        kind = AreaKind.code(run)
        group = ActivityAreaGroups.classify(run.get('area_id', ''))

        return [code for code, matches in (('maps', kind == 'map'), ('hideout', kind == 'hideout'),
                ('special', group is not None and group not in ('maps', 'hideout', 'acts'))) if matches]

    @classmethod
    def build(cls, intervals: list[dict], runs: list[dict], timezone_name: str,
              daily_areas: dict, control: ExecutionContext, *, afk_rows: list[dict] | None = None) -> dict:

        control.check()
        zone = ZoneInfo(timezone_name)
        buckets = {code: {} for code in cls.FILTERS}

        for interval in intervals:
            cls.add(buckets['all'], interval.get('started_at'), interval.get('ended_at'), zone, control)

        for run in runs:
            control.check()
            codes = cls.filters(run)

            for visit in run['visits']:
                control.check()

                for part in VisitMeasurements.parts(visit):
                    for code in codes:
                        cls.add(buckets[code], part.get('entered_at'), part.get('ended_at'), zone, control)

        maximum = max((sum(days.values()) for cells in buckets.values() for days in cells.values()), default = 0)
        panels = [cls.panel(code, buckets[code], maximum, daily_areas, control) for code in cls.FILTERS]
        marked = {code: {} for code in cls.FILTERS}

        for row in afk_rows or []:
            control.check()

            for code in ['all', *cls.filters(row)]:
                cls.add(marked[code], row['entered_at'], row['ended_at'], zone, control)

        reduced = []

        for code in cls.FILTERS:
            control.check()
            cells = {}

            for cell, days in buckets[code].items():
                values = {}

                for day, seconds in days.items():
                    remaining = seconds - marked[code].get(cell, {}).get(day, 0)

                    if remaining < -0.000001:
                        raise ValueError("AFK time exceeds the cell's measured time")

                    if remaining > 0:
                        values[day] = remaining

                cells[cell] = values

            reduced.append(cls.panel(code, cells, maximum, daily_areas, control, mode = 'without_afk'))

        return {'version': '2', 'timezone': timezone_name, 'panels': panels, 'without_afk': reduced,
                'maximum_seconds': maximum, 'maximum_duration': DurationFormatter.duration_label(maximum)}

    @classmethod
    def add(cls, cells: dict, entered: str | None, ended: str | None, zone: ZoneInfo,
            control: ExecutionContext) -> None:

        control.check()

        if not entered or not ended:
            return

        start = datetime.fromisoformat(entered).astimezone(timezone.utc)
        end = datetime.fromisoformat(ended).astimezone(timezone.utc)

        while start < end:
            control.check()
            local = start.astimezone(zone)
            wall = local.replace(tzinfo = None, minute = 0, second = 0, microsecond = 0) + timedelta(hours = 1)
            candidates = [wall.replace(tzinfo = zone, fold = fold).astimezone(timezone.utc) for fold in (0, 1)]
            stop = min(end, start + timedelta(hours = 1), *(stamp for stamp in candidates if stamp > start))

            # Offset changes may occur within an hour, including 30-minute changes.
            if stop.astimezone(zone).utcoffset() != local.utcoffset():
                stop = cls.transition(start, stop, zone)

            days = cells.setdefault((local.weekday(), local.hour), Counter())
            days[local.date().isoformat()] += (stop - start).total_seconds()
            start = stop

    @staticmethod
    def transition(start: datetime, end: datetime, zone: ZoneInfo) -> datetime:
        """Locate UTC offset transitions while preserving repeated local hours."""

        offset = start.astimezone(zone).utcoffset()
        left, right = floor(start.timestamp()), ceil(end.timestamp())

        while right - left > 1:
            middle = (left + right) // 2

            if datetime.fromtimestamp(middle, zone).utcoffset() == offset:
                left = middle
            else:
                right = middle

        return min(end, datetime.fromtimestamp(right, timezone.utc))

    @staticmethod
    def panel(code: str, buckets: dict, maximum: float, daily_areas: dict, control: ExecutionContext,
              *, mode: str = 'all') -> dict:

        rows, total_days = [], set()
        total = 0
        identifier = code if mode == 'all' else code + '-without-afk'

        for weekday in range(7):
            cells = []

            for hour in range(24):
                control.check()
                values = buckets.get((weekday, hour), {})
                seconds = sum(values.values())
                total += seconds
                total_days.update(values)
                days = [{'date': date, 'seconds': value, 'duration': DurationFormatter.duration_label(value),
                         'href': f'maps/{date}/index.html' if date in daily_areas['by_date'] else None}
                        for date, value in sorted(values.items(), reverse = True)]
                cells.append({'id': f'heatmap-{identifier}-{weekday}-{hour}', 'hour': hour,
                              'range': f'{hour:02}:00–{hour + 1:02}:00', 'seconds': seconds,
                              'duration': DurationFormatter.duration_label(seconds),
                              'active_days': len(days), 'days': days,
                              'level': min(5, ceil(5 * seconds / maximum)) if seconds and maximum else 0})

            rows.append({'weekday': weekday, 'cells': cells})

        return {'code': identifier, 'filter': code, 'mode': mode,
                'rows': rows, 'seconds': total, 'duration': DurationFormatter.duration_label(total),
                'active_days': len(total_days)}
