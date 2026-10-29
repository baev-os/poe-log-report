from statistics import mean, median

from poe_log_analyze.stages.composition.AfkMeasurements import AfkMeasurements
from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection
from poe_log_analyze.stages.composition.VisitMeasurements import VisitMeasurements
from poe_log_analyze.stages.composition.sessions.SessionHistoryBuilder import SessionHistoryBuilder


class MapRunMetrics:
    """Shared map-instance measurements for play pace and period comparison."""

    @staticmethod
    def record(source: dict, run: dict, selection: ReportPeriodSelection, sessions: SessionHistoryBuilder,
               *, afk: dict | None = None) -> dict:

        selection.control.check()
        visits = run['visits']
        original = {visit['entry_line']: visit for visit in source['visits']}
        new = MapRunMetrics.is_new(source, selection)
        changed = len(visits) != len(source['visits']) or any(
            VisitMeasurements.seconds(visit) != VisitMeasurements.seconds(original[visit['entry_line']]) for visit in visits)
        membership = {sessions.session(visit['entry_line']) for visit in source['visits']}
        reasons = []

        if not all(visit['bounded'] and visit['seconds'] is not None for visit in source['visits']):
            reasons.append('incomplete')

        if changed:
            reasons.append('clipped')

        if source.get('branched') or any(visit.get('branches') for visit in source['visits']):
            reasons.append('branched')

        if not source.get('identity_complete'):
            reasons.append('identity')

        if len(membership) > 1:
            reasons.append('multiple_sessions')

        returns = sum(bool(visit.get('entered_at') and visit['entry_line'] != source['first_line']
                      and selection.period.contains(original[visit['entry_line']].get('entered_at'), selection.zone_name))
                      for visit in visits)
        balance = AfkMeasurements.combine([AfkMeasurements.visit(visit, afk) for visit in visits])

        return {**balance, 'new': int(new), 'returns': returns,
                'seconds': sum(VisitMeasurements.seconds(visit) for visit in visits), 'excluded': reasons}

    @staticmethod
    def statistics(rows: list[dict], play_seconds: float | None = None, map_seconds: float | None = None,
                   *, duration_field: str = 'seconds') -> dict:

        values = [row[duration_field] for row in rows if not row['excluded'] and row.get(duration_field) is not None]
        measured = [row[duration_field] for row in rows if row.get(duration_field) is not None]
        count = sum(row['new'] for row in rows)

        return {'count': len(rows), 'new': count, 'complete': len(values), 'excluded': len(rows) - len(values),
                'returns': sum(row['returns'] for row in rows), 'play_seconds': play_seconds,
                'map_seconds': map_seconds if map_seconds is not None else sum(measured) if measured or not rows else None,
                'rate': count * 3600 / play_seconds if play_seconds else None,
                'mean_seconds': mean(values) if values else None, 'median_seconds': median(values) if values else None,
                'min_seconds': min(values) if values else None, 'max_seconds': max(values) if values else None}

    @staticmethod
    def is_new(source: dict, selection: ReportPeriodSelection) -> bool:
        return bool(source.get('started_at') and selection.period.contains(source['started_at'], selection.zone_name))
