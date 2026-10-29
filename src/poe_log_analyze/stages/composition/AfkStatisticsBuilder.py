from datetime import datetime, time, timedelta, timezone

from poe_log_analyze.runtime.AreaKind import AreaKind
from poe_log_analyze.runtime.DurationFormatter import DurationFormatter

from poe_log_analyze.stages.composition.AfkMeasurements import AfkMeasurements
from poe_log_analyze.stages.composition.VisitMeasurements import VisitMeasurements
from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder


class AfkStatisticsBuilder:
    """Split observed time by AFK and area while respecting branch provenance."""

    CATEGORIES = ('map', 'hideout', 'other', 'unallocated')

    @staticmethod
    def moment(stamp: str) -> float:
        return datetime.fromisoformat(stamp).timestamp()

    @staticmethod
    def sources(record: dict) -> set[str]:
        return {origin['source'] for origin in record.get('origins', [record['origin']])}

    @classmethod
    def empty(cls) -> dict:
        return {code: {'seconds': 0, 'afk_seconds': 0} for code in cls.CATEGORIES}

    @classmethod
    def summary(cls, categories: dict) -> dict:
        seconds = sum(row['seconds'] for row in categories.values())
        afk = sum(row['afk_seconds'] for row in categories.values())
        rows = []

        for code, row in categories.items():
            rows.append({'code': code, **cls.values(row['seconds'], row['afk_seconds']),
                         'share': row['seconds'] * 100 / seconds if seconds else 0})

        return {**cls.values(seconds, afk), 'categories': rows}

    @staticmethod
    def values(seconds: float, afk: float) -> dict:
        remaining = max(0, seconds - afk)
        return {'seconds': seconds, 'afk_seconds': afk, 'remaining_seconds': remaining,
                'duration': DurationFormatter.duration_label(seconds),
                'afk_duration': DurationFormatter.duration_label(afk),
                'remaining_duration': DurationFormatter.duration_label(remaining),
                'afk_share': afk * 100 / seconds if seconds else 0}

    @classmethod
    def build(cls, intervals: list[dict], runs: list[dict], sessions, daily_playtime: dict, selection,
              *, extended: bool = True) -> dict:

        zones, visits = {}, {}

        for run in runs:
            selection.control.check()
            kind = AreaKind.code(run)
            category = kind if kind in ('map', 'hideout') else 'other'

            for visit in run['visits']:
                first = str(sessions.session(visit['entry_line']))
                parts = VisitMeasurements.parts(visit)

                if extended:
                    visits[str(visit['entry_line'])] = {'seconds': VisitMeasurements.seconds(visit) if parts else None,
                                                      'covered': 0, 'afk_seconds': 0}

                for part in parts:
                    item = {'start': cls.moment(part['entered_at']), 'end': cls.moment(part['ended_at']),
                            'name': run['name'], 'category': category, 'line': visit['entry_line'],
                            'area_id': run.get('area_id', ''), 'kind_code': kind}

                    for source in cls.sources(part):
                        zones.setdefault((first, source), []).append(item)

        total = cls.empty()
        days = {day['date']: cls.empty() for day in daily_playtime['days']} if extended else {}
        session_totals = {str(first): cls.empty() for first in sessions.rows} if extended else {}
        session_days, rows = {}, []

        for index, interval in enumerate(intervals):
            selection.control.check()
            session = str(interval['first_line'])
            candidates = {}

            for source in cls.sources(interval):
                for zone in zones.get((session, source), []):
                    candidates[(zone['line'], zone['start'], zone['end'])] = zone

            spans = cls.spans(interval, list(candidates.values()), selection)

            for left, right, zone, afk in spans:
                category = zone['category'] if zone else 'unallocated'
                seconds = right - left
                amount = seconds if afk else 0
                cls.add(total, category, seconds, amount)

                if not extended:
                    continue

                cls.add(session_totals.setdefault(session, cls.empty()), category, seconds, amount)

                if zone:
                    visit = visits[str(zone['line'])]
                    visit['covered'] += seconds
                    visit['afk_seconds'] += amount

                for date, duration in cls.days(left, right, selection):
                    cls.add(days.setdefault(date, cls.empty()), category, duration, duration if afk else 0)
                    daily = session_days.setdefault(session, {}).setdefault(date, cls.empty())
                    cls.add(daily, category, duration, duration if afk else 0)

                if afk:
                    cls.append(rows, left, right, zone, afk, session, index, selection)

        if not extended:
            return {'summary': cls.summary(total)}

        by_visit = {}

        for line, visit in visits.items():
            selection.control.check()
            known = visit['seconds'] is not None and abs(visit['covered'] - visit['seconds']) < .000001
            by_visit[line] = AfkMeasurements.balance(visit['seconds'], visit['afk_seconds'] if known else None)

        return {'version': '3', 'timezone': selection.zone_name, 'summary': cls.summary(total), 'by_visit': by_visit,
                'by_date': {key: cls.summary(value) for key, value in sorted(days.items())},
                'by_session': {key: {**cls.summary(value), 'by_date': {
                    day: cls.summary(amount) for day, amount in session_days.get(key, {}).items()}}
                    for key, value in session_totals.items()}, 'rows': rows}

    @staticmethod
    def add(target: dict, category: str, seconds: float, afk: float) -> None:
        target[category]['seconds'] += seconds
        target[category]['afk_seconds'] += afk

    @classmethod
    def spans(cls, interval: dict, zones: list[dict], selection) -> list[tuple]:
        start, end = cls.moment(interval['started_at']), cls.moment(interval['ended_at'])
        changes = {start: [], end: []}
        entries = {'zone': zones, 'afk': interval.get('afk_intervals', [])}

        for kind, items in entries.items():
            for index, item in enumerate(items):
                selection.control.check()
                left = max(start, item['start'] if kind == 'zone' else cls.moment(item['entered_at']))
                right = min(end, item['end'] if kind == 'zone' else cls.moment(item['ended_at']))

                if left < right:
                    changes.setdefault(left, []).append((kind, index, True))
                    changes.setdefault(right, []).append((kind, index, False))

        active = {'zone': set(), 'afk': set()}
        points = sorted(changes)
        result = []

        for left, right in zip(points, points[1:]):
            selection.control.check()

            for kind, index, added in changes[left]:
                if added:
                    active[kind].add(index)
                else:
                    active[kind].discard(index)

            zone = entries['zone'][next(iter(active['zone']))] if len(active['zone']) == 1 else None
            afk = entries['afk'][min(active['afk'])] if active['afk'] else None
            result.append((left, right, zone, afk))

        return result

    @staticmethod
    def days(left: float, right: float, selection) -> list[tuple[str, float]]:
        start, end = datetime.fromtimestamp(left, timezone.utc), datetime.fromtimestamp(right, timezone.utc)
        result = []

        while start < end:
            selection.control.check()
            date = start.astimezone(selection.zone).date()
            midnight = datetime.combine(date + timedelta(days = 1), time(), selection.zone).astimezone(timezone.utc)
            stop = min(end, midnight)
            result.append((date.isoformat(), (stop - start).total_seconds()))
            start = stop

        return result

    @classmethod
    def append(cls, rows: list[dict], left: float, right: float, zone: dict | None, afk: dict,
               session: str, part: int, selection) -> None:

        name = zone['name'] if zone else ''
        category = zone['category'] if zone else 'unallocated'
        start = datetime.fromtimestamp(left, selection.zone)
        end = datetime.fromtimestamp(right, selection.zone)
        rows.append({'session_id': session, 'part': part, 'category': category, 'name': name,
                     'visit_line': zone['line'] if zone else None,
                     'area_id': zone['area_id'] if zone else '', 'kind_code': zone['kind_code'] if zone else 'unknown',
                     'entered_at': start.isoformat(), 'ended_at': end.isoformat(),
                     'start': start.strftime('%d.%m.%Y %H:%M:%S %z'), 'end': end.strftime('%d.%m.%Y %H:%M:%S %z'),
                     'seconds': right - left, 'duration': DurationFormatter.duration_label(right - left),
                     'line': afk['first_line'], 'href': LogHistoryBuilder.line_href(afk['first_line']),
                     'end_href': LogHistoryBuilder.line_href(afk['last_line']),
                     'open_at_end': afk['open_at_end'], 'end_reason': afk['end_reason']})
