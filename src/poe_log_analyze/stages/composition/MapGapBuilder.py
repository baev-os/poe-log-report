from datetime import datetime, timezone

from poe_log_analyze.runtime.AreaKind import AreaKind
from poe_log_analyze.runtime.DurationFormatter import DurationFormatter

from poe_log_analyze.stages.composition.AfkMeasurements import AfkMeasurements
from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection
from poe_log_analyze.stages.composition.VisitMeasurements import VisitMeasurements
from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder
from poe_log_analyze.stages.composition.sessions.SessionHistoryBuilder import SessionHistoryBuilder


class MapGapBuilder:
    """Measured gaps between adjacent map visits in one linear session."""

    @staticmethod
    def moment(stamp: str) -> datetime:
        return datetime.fromisoformat(stamp).astimezone(timezone.utc)

    @classmethod
    def build(cls, runs: list[dict], sessions: SessionHistoryBuilder, selection: ReportPeriodSelection,
              *, afk: dict | None = None) -> dict:

        grouped = {}
        unassigned = 0
        marked = {}

        for row in afk['rows'] if afk else []:
            selection.control.check()
            marked.setdefault(row['session_id'], []).append(row)

        for run in runs:
            for visit in run['visits']:
                selection.control.check()
                session = sessions.session(visit['entry_line'])

                if session is not None:
                    grouped.setdefault(session, []).append((run, visit))
                elif AreaKind.code(run) == 'map' and selection.visit(visit) is not None:
                    unassigned += 1

        rows, excluded, branched = [], 0, 0

        for first, visits in grouped.items():
            selection.control.check()
            visits.sort(key = lambda item: item[1]['entry_line'])
            positions = [i for i, (run, _) in enumerate(visits) if AreaKind.code(run) == 'map']
            session = sessions.rows[first]

            if session['branched']:
                selected = sum(selection.visit(visits[i][1]) is not None for i in positions)
                branched += bool(selected > 1)
                excluded += max(0, selected - 1)
                continue

            for left, right in zip(positions, positions[1:]):
                selection.control.check()
                previous, end = visits[left]
                following, begin = visits[right]
                start, stop = end.get('ended_at'), begin.get('entered_at')

                if (not end['bounded'] or not start or not stop or end.get('branches') or begin.get('branches')
                        or cls.moment(stop) < cls.moment(start)):
                    excluded += bool(selection.visit(end) is not None or selection.visit(begin) is not None)
                    continue

                bounds = selection.clip(start, stop)

                if bounds is None:
                    continue

                a, b, seconds = bounds
                zones = cls.zones(visits[left + 1:right], a, b, selection)
                measured = sum(row['seconds'] for row in zones)

                if measured > seconds + .000001:
                    # Overlapping measurements do not establish a linear gap.
                    excluded += 1
                    continue

                evidence = cls.afk_parts(marked.get(str(first), []), a, b, selection)
                balance = AfkMeasurements.balance(seconds, sum(row['seconds'] for row in evidence) if afk else None)
                rows.append({**balance, 'afk_evidence': evidence,
                             'from_name': previous['name'], 'to_name': following['name'],
                             'from_href': LogHistoryBuilder.line_href(end['end_line']),
                             'to_href': LogHistoryBuilder.line_href(begin['entry_line']),
                             'line': begin['entry_line'], 'session_id': str(first), 'session_href': session['path'],
                             'from_run': previous['first_line'], 'to_run': following['first_line'],
                             'from_visit': end['entry_line'],
                             'from_line': end['end_line'],
                             'started_at': a, 'ended_at': b, 'start': sessions.label(a), 'end': sessions.label(b),
                             'seconds': seconds, 'duration': DurationFormatter.duration_label(seconds),
                             'return': previous['first_line'] == following['first_line'],
                             'clipped': seconds != (cls.moment(stop) - cls.moment(start)).total_seconds(),
                             'zones': zones, 'unallocated_seconds': max(0, seconds - measured),
                             'unallocated': DurationFormatter.duration_label(max(0, seconds - measured))})

        rows.sort(key = lambda row: (cls.moment(row['started_at']), row['line']))
        seconds = sum(row['seconds'] for row in rows)
        zones = {}

        for row in rows:
            for zone in row['zones']:
                key = (zone['kind'], zone['name'])
                zones.setdefault(key, {'kind': zone['kind'], 'name': zone['name'], 'seconds': 0})['seconds'] += zone['seconds']

        zone_rows = sorted(zones.values(), key = lambda row: (-row['seconds'], row['name'], row['kind']))

        for row in zone_rows:
            row['duration'] = DurationFormatter.duration_label(row['seconds'])

        return {**AfkMeasurements.combine(rows), 'rows': rows, 'count': len(rows),
                'seconds': seconds, 'duration': DurationFormatter.duration_label(seconds),
                'longest': sorted(range(len(rows)), key = lambda i: (-rows[i]['seconds'], rows[i]['line']))[:10],
                'zones': zone_rows, 'unallocated_seconds': sum(row['unallocated_seconds'] for row in rows),
                'unallocated': DurationFormatter.duration_label(sum(row['unallocated_seconds'] for row in rows)),
                'excluded_pairs': excluded, 'branched_sessions': branched, 'unassigned_visits': unassigned}

    @classmethod
    def afk_parts(cls, rows: list[dict], start: str, end: str, selection: ReportPeriodSelection) -> list[dict]:
        left, right = cls.moment(start), cls.moment(end)
        parts = {}

        for row in rows:
            selection.control.check()
            a, b = max(left, cls.moment(row['entered_at'])), min(right, cls.moment(row['ended_at']))

            if b > a:
                seconds = (b - a).total_seconds()
                key = (row['href'], row['end_href'])
                parts.setdefault(key, {'seconds': 0, 'href': row['href'], 'end_href': row['end_href']})['seconds'] += seconds

        return [{**part, 'duration': DurationFormatter.duration_label(part['seconds'])} for part in parts.values()]

    @classmethod
    def zones(cls, visits: list[tuple[dict, dict]], start: str, end: str, selection: ReportPeriodSelection) -> list[dict]:
        left, right = cls.moment(start), cls.moment(end)
        zones = {}

        for run, visit in visits:
            for part in VisitMeasurements.parts(visit):
                selection.control.check()
                a, b = max(left, cls.moment(part['entered_at'])), min(right, cls.moment(part['ended_at']))

                if b <= a:
                    continue

                key = (AreaKind.code(run), run['name'])
                zones.setdefault(key, {'kind': key[0], 'name': key[1], 'seconds': 0})['seconds'] += (b - a).total_seconds()

        rows = sorted(zones.values(), key = lambda row: (-row['seconds'], row['name'], row['kind']))

        for row in rows:
            row['duration'] = DurationFormatter.duration_label(row['seconds'])

        return rows
