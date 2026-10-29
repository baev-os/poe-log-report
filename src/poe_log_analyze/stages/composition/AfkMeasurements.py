from datetime import datetime, timezone

from poe_log_analyze.runtime.DurationFormatter import DurationFormatter

from poe_log_analyze.stages.composition.VisitMeasurements import VisitMeasurements


class AfkMeasurements:
    """Exact observed remainder after subtracting recorded AFK intervals."""

    @staticmethod
    def moment(stamp: str) -> datetime:
        return datetime.fromisoformat(stamp).astimezone(timezone.utc)

    @classmethod
    def without(cls, intervals: list[dict], control) -> list[dict]:
        result = []

        for interval in intervals:
            control.check()
            cursor, end = cls.moment(interval['started_at']), cls.moment(interval['ended_at'])
            marked = sorted((cls.moment(part['entered_at']), cls.moment(part['ended_at']))
                            for part in interval.get('afk_intervals', []))

            for left, right in marked:
                control.check()
                left, right = max(cursor, left), min(end, right)

                if right <= left:
                    continue

                if cursor < left:
                    result.append(cls.part(cursor, left))

                cursor = right

            if cursor < end:
                result.append(cls.part(cursor, end))

        return result

    @staticmethod
    def part(start: datetime, end: datetime) -> dict:
        return {'started_at': start.isoformat(), 'ended_at': end.isoformat(),
                'seconds': (end - start).total_seconds()}

    @classmethod
    def summary(cls, intervals: list[dict], control) -> dict:
        total = sum(interval['seconds'] for interval in intervals)
        remaining = sum(part['seconds'] for part in cls.without(intervals, control))
        afk = max(0, total - remaining)

        return {'afk_seconds': afk, 'remaining_seconds': remaining,
                'afk_share': afk * 100 / total if total else None}

    @staticmethod
    def balance(seconds: float | None, afk: float | None) -> dict:
        if seconds is None:
            afk = None

        if afk is not None and seconds is not None and not -0.000001 <= afk <= seconds + 0.000001:
            raise ValueError('AFK time lies outside the measured interval')

        remaining = max(0, seconds - afk) if seconds is not None and afk is not None else None

        return {'seconds': seconds, 'afk_seconds': afk, 'remaining_seconds': remaining,
                'duration': DurationFormatter.duration_label(seconds) if seconds is not None else '—',
                'afk_duration': DurationFormatter.duration_label(afk) if afk is not None else '—',
                'remaining_duration': DurationFormatter.duration_label(remaining) if remaining is not None else '—'}

    @classmethod
    def combine(cls, rows: list[dict]) -> dict:
        seconds = sum(row['seconds'] for row in rows if row['seconds'] is not None)
        marked = sum(row['afk_seconds'] for row in rows) if all(row['afk_seconds'] is not None for row in rows) else None

        return cls.balance(seconds if not rows or any(row['seconds'] is not None for row in rows) else None, marked)

    @classmethod
    def visit(cls, visit: dict, afk: dict | None) -> dict:
        if afk is not None and str(visit['entry_line']) in afk.get('by_visit', {}):
            return afk['by_visit'][str(visit['entry_line'])]

        return cls.balance(VisitMeasurements.seconds(visit) if VisitMeasurements.parts(visit) else None, None)
