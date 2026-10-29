from datetime import datetime, timezone

from poe_log_analyze.runtime.AreaKind import AreaKind

from poe_log_analyze.stages.composition.AfkMeasurements import AfkMeasurements
from poe_log_analyze.stages.composition.MapPaceBuilder import MapPaceBuilder
from poe_log_analyze.stages.composition.VisitMeasurements import VisitMeasurements


class MeasuredSpanIndex:
    """Intersections with proven measurements; unknown values must not become zero."""

    def __init__(self, intervals, runs, sessions, selection) -> None:
        selection.control.check()
        self.sessions, self.selection = sessions, selection
        self.intervals, self.areas = {}, {}

        for interval in intervals:
            selection.control.check()
            self.intervals.setdefault(interval['first_line'], []).append(interval)

        for run in runs:
            for visit in run['visits']:
                selection.control.check()
                first = sessions.session(visit['entry_line'])

                for part in VisitMeasurements.parts(visit):
                    self.areas.setdefault(first, []).append((AreaKind.code(run), part, visit['entry_line'],
                                                             run.get('area_id'), run.get('name', '')))

    @staticmethod
    def moment(stamp: str) -> datetime:
        return datetime.fromisoformat(stamp).astimezone(timezone.utc)

    @classmethod
    def overlap(cls, left, right, start, end) -> float:
        return max(0, (min(right, cls.moment(end)) - max(left, cls.moment(start))).total_seconds())

    def measure(self, first, start, end) -> dict | None:
        self.selection.control.check()
        bounds = self.selection.clip(start, end)

        if bounds is None:
            return None

        a, b, elapsed = bounds
        left, right = self.moment(a), self.moment(b)
        seconds, marked, known, observed = 0, 0, True, False

        for interval in self.intervals.get(first, []):
            self.selection.control.check()
            amount = self.overlap(left, right, interval['started_at'], interval['ended_at'])
            zero = left == right and self.moment(interval['started_at']) <= left <= self.moment(interval['ended_at'])

            if not amount and not zero:
                continue

            observed = True
            seconds += amount
            known = known and 'afk_intervals' in interval

            for part in interval.get('afk_intervals', []):
                marked += self.overlap(left, right, part['entered_at'], part['ended_at'])

        kinds, zones = {}, {}

        for kind, part, line, area_id, name in self.areas.get(first, []):
            self.selection.control.check()
            amount = self.overlap(left, right, part['entered_at'], part['ended_at'])
            kinds[kind] = kinds.get(kind, 0) + amount
            key = kind, area_id, name
            zones.setdefault(key, {'kind': kind, 'area_id': area_id, 'name': name, 'seconds': 0})['seconds'] += amount

        measured = seconds if observed else None
        balance = AfkMeasurements.balance(measured, marked if known and observed else None)
        by_area = sum(kinds.values())
        values = {'map_seconds': kinds.get('map', 0),
                  'outside_seconds': sum(value for kind, value in kinds.items() if kind != 'map'),
                  'unallocated_seconds': max(0, seconds - by_area) if observed else None,
                  'elapsed_seconds': elapsed}

        return {**balance, **values, 'started_at': a, 'ended_at': b,
                'covered': observed and abs(seconds - elapsed) < .000001,
                'overlapping': seconds > elapsed + .000001 or by_area > seconds + .000001,
                'clipped': left != self.moment(start) or right != self.moment(end),
                'zones': [{**zone, 'duration': MapPaceBuilder.duration(zone['seconds'])}
                          for zone in sorted(zones.values(), key = lambda item: (item['kind'], item['name'], item['area_id'] or ''))
                          if zone['seconds'] > 0],
                **{key.removesuffix('_seconds') + '_duration': MapPaceBuilder.duration(value)
                   for key, value in values.items()}}

    @staticmethod
    def statistics(rows, field = 'seconds') -> dict:
        values = [{'new': 0, 'returns': 0, 'excluded': row.get('excluded', []), field: row.get(field)} for row in rows]
        return MapPaceBuilder.statistics(values, duration_field = field)
