from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod

from poe_log_analyze.stages.composition.VisitMeasurements import VisitMeasurements


class ReportPeriodSelection:
    """Slice calculated visits while keeping original boundaries and technical models intact."""

    def __init__(self, period: ReportPeriod, zone_name: str, control: ExecutionContext,
                 observations_key: str = 'period_observations'):

        self.period, self.zone_name, self.control = period, zone_name, control
        self.start, self.end = period.bounds(zone_name)
        self.zone = ZoneInfo(zone_name)
        self.observations_key = observations_key

    def metadata(self) -> dict:
        return {'version': '1', 'active': self.period.active, 'timezone': self.zone_name,
                'date_from': self.period.date_from.isoformat() if self.period.date_from else None,
                'date_to': self.period.date_to.isoformat() if self.period.date_to else None,
                'start_inclusive': self.start.isoformat() if self.start else None,
                'end_exclusive': self.end.isoformat() if self.end else None}

    def clip(self, start: str, end: str) -> tuple[str, str, float] | None:
        left = datetime.fromisoformat(start).astimezone(timezone.utc)
        right = datetime.fromisoformat(end).astimezone(timezone.utc)

        if right < left:
            return None

        if left == right:
            return (start, end, 0) if self.period.contains(start, self.zone_name) else None

        begin = max(left, self.start) if self.start else left
        stop = min(right, self.end) if self.end else right

        if begin >= stop:
            return None

        return begin.astimezone(self.zone).isoformat(), stop.astimezone(self.zone).isoformat(), (stop - begin).total_seconds()

    def intervals(self, intervals: list[dict]) -> list[dict]:
        if not self.period.active:
            return intervals

        result = []

        for interval in intervals:
            self.control.check()
            bounds = self.clip(interval['started_at'], interval['ended_at'])

            if bounds:
                start, end, seconds = bounds
                result.append({**interval, 'started_at': start, 'ended_at': end, 'seconds': seconds,
                               **self.afk(interval)})

        return result

    def afk(self, record: dict) -> dict:
        if 'afk_intervals' not in record:
            return {}

        intervals = []
        seconds = 0

        for part in record['afk_intervals']:
            self.control.check()
            bounds = self.clip(part['entered_at'], part['ended_at'])

            if bounds is not None:
                start, end, amount = bounds
                intervals.append({**part, 'entered_at': start, 'ended_at': end})
                seconds += amount

        return {'afk_intervals': intervals, 'afk_seconds': seconds}

    def visit(self, visit: dict) -> dict | None:
        start, end = visit.get('entered_at'), visit.get('ended_at')
        result = dict(visit)

        if 'segments' in visit:
            selected = self.branched_visit(visit)

            if selected is None:
                return None

            result.update(selected)
        elif visit['bounded'] and start and end:
            bounds = self.clip(start, end)

            if bounds is None:
                return None

            left, right, seconds = bounds
            result.update(entered_at = left, ended_at = right, seconds = seconds,
                          original_entered_at = visit.get('original_entered_at', start), original_ended_at = end)
            # AFK totals without intervals cannot be prorated across a boundary.
            result['afk_seconds'] = visit.get('afk_seconds') if seconds == visit['seconds'] else None
            result.update(self.afk(visit))
        elif not (self.period.contains(start, self.zone_name) or self.period.contains(end, self.zone_name)):
            return None

        evidence = visit.get(self.observations_key, visit)

        for key in ('mechanics', 'discoveries', 'mercenaries', 'death_messages'):
            result[key] = [item for item in evidence.get(key, [])
                           if self.period.contains(item.get('timestamp'), self.zone_name)]

        result.pop('period_observations', None)
        result.pop('comparison_observations', None)

        return result

    def branched_visit(self, visit: dict) -> dict | None:
        segments, branches = [], []

        for source, destination in ((visit['segments'], segments), (visit['branches'], branches)):
            for part in source:
                self.control.check()
                selected = self.visit(part)

                if selected is not None:
                    destination.append(selected)

        if not segments and not branches:
            return None

        bounded = all(branch['bounded'] for branch in branches)
        seconds = sum(part['seconds'] for part in segments)
        starts = [part['entered_at'] for part in (*segments, *branches) if part.get('entered_at')]
        endings = {branch['ended_at'] for branch in branches}

        return {'segments': segments, 'branches': branches, 'bounded': bounded,
                'original_entered_at': visit['entered_at'], 'original_ended_at': visit['ended_at'],
                'entered_at': min(starts, key = datetime.fromisoformat) if starts else None,
                'ended_at': next(iter(endings)) if len(endings) == 1 else None,
                'seconds': seconds if bounded else None, 'measured_seconds': seconds,
                'afk_seconds': None}

    def runs(self, runs: list[dict]) -> list[dict]:
        if not self.period.active:
            return runs

        result = []

        for run in runs:
            self.control.check()
            visits = []

            for visit in run['visits']:
                self.control.check()
                selected = self.visit(visit)

                if selected is not None:
                    visits.append(selected)

            if not visits:
                continue

            start = visits[0]['entered_at']
            result.append({**run, 'visits': visits, 'original_started_at': run['started_at'],
                           'started_at': start, 'entrances': len(visits),
                           'period_date': datetime.fromisoformat(start).astimezone(self.zone).date().isoformat() if start else 'undated',
                           'seconds': sum(VisitMeasurements.seconds(v) for v in visits),
                           'unbounded_visits': sum(not v['bounded'] for v in visits)})

        return result

    @staticmethod
    def model(runs: list[dict], zone_name: str) -> dict:
        days = {}

        for run in runs:
            key = run.get('period_date', run['date'])
            days.setdefault(key, {'runs': []})['runs'].append(run)

        return {'timezone': zone_name, 'by_date': days}
