from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod

from poe_log_analyze.runtime.AreaKind import AreaKind

from poe_log_analyze.stages.composition.ActivityAreaGroups import ActivityAreaGroups
from poe_log_analyze.stages.composition.AfkMeasurements import AfkMeasurements
from poe_log_analyze.stages.composition.AllTimeStatisticsBuilder import AllTimeStatisticsBuilder
from poe_log_analyze.stages.composition.MapObservationStatisticsBuilder import MapObservationStatisticsBuilder
from poe_log_analyze.stages.composition.MapRunMetrics import MapRunMetrics
from poe_log_analyze.stages.composition.MapGapBuilder import MapGapBuilder
from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection
from poe_log_analyze.stages.composition.VisitMeasurements import VisitMeasurements
from poe_log_analyze.stages.composition.sessions.SessionHistoryBuilder import SessionHistoryBuilder


class PeriodComparisonBuilder:
    """Compare independent slices of the shared history: A is baseline, B is report period."""

    METRICS = (('days', 'number'), ('play_seconds', 'duration'), ('play_per_day', 'duration'),
               ('afk_seconds', 'duration'), ('afk_share', 'share'), ('remaining_seconds', 'duration'),
               ('map_count', 'number'), ('new_maps', 'number'), ('map_returns', 'number'),
               ('maps_per_day', 'number'), ('maps_per_hour', 'number'),
               ('maps_per_hour_without_afk', 'number'),
               ('map_seconds', 'duration'), ('mean_map_seconds', 'duration'),
               ('measured_maps', 'number'), ('excluded_maps', 'number'),
               ('loading_seconds', 'duration'), ('loading_per_day', 'duration'), ('loading_count', 'number'))

    @classmethod
    def build(cls, runs: list[dict], intervals: list[dict], zone: str, baseline: ReportPeriod,
              current: ReportPeriod, baseline_counters: dict, current_counters: dict,
              control: ExecutionContext, session_definitions: list[dict]) -> dict:

        control.check()
        a = cls.snapshot(runs, intervals, zone, baseline, baseline_counters, 'comparison_observations', control, session_definitions)
        b = cls.snapshot(runs, intervals, zone, current, current_counters, 'period_observations', control, session_definitions)
        sections = [{'code': 'metrics', 'rows': [cls.row(key, 'comparison.' + key, kind, a[key], b[key])
                                               for key, kind in cls.METRICS]}]
        zone_rows = []

        for code in a['zones']:
            control.check()
            label = 'comparison.other_zones' if code == 'other' else 'activities.' + code
            zone_rows.append(cls.row(code + '_seconds', label, 'duration', a['zones'][code], b['zones'][code]))
            zone_rows.append(cls.row(code + '_share', label, 'share',
                cls.ratio(a['zones'][code] * 100, a['zone_seconds']), cls.ratio(b['zones'][code] * 100, b['zone_seconds'])))

        sections.append({'code': 'zones', 'rows': zone_rows})
        mechanics = []

        for code, label in sorted(MapObservationStatisticsBuilder.LABELS.items()):
            control.check()
            mechanics.append({**cls.row(code, label, 'share',
                cls.ratio(a['mechanics'][code] * 100, a['observation_maps']),
                cls.ratio(b['mechanics'][code] * 100, b['observation_maps'])),
                'a_count': a['mechanics'][code], 'b_count': b['mechanics'][code]})

        sections.append({'code': 'mechanics', 'rows': mechanics})

        return {'version': '4', 'enabled': True, 'timezone': zone, 'a': a, 'b': b,
                'overlap': baseline.date_from <= current.date_to and current.date_from <= baseline.date_to,
                'sections': sections}

    @classmethod
    def snapshot(cls, runs: list[dict], intervals: list[dict], zone: str, period: ReportPeriod,
                 counters: dict, observations_key: str, control: ExecutionContext, session_definitions: list[dict]) -> dict:

        if period.date_from is None or period.date_to is None:
            raise ValueError('Comparison requires both dates of each period')

        selection = ReportPeriodSelection(period, zone, control, observations_key)
        selected = selection.runs(runs)
        activity = selection.intervals(intervals)
        maps = [run for run in selected if AreaKind.code(run) == 'map']
        sessions = SessionHistoryBuilder(session_definitions, intervals, selected, selection)
        originals = {(run['area_id'], run['first_line']): run for run in runs}
        records = [MapRunMetrics.record(originals[(run['area_id'], run['first_line'])], run, selection, sessions)
                   for run in maps]
        summary = AllTimeStatisticsBuilder.build(selected, control)
        observations = MapObservationStatisticsBuilder.build(selection.model(maps, zone), control)
        days = (period.date_to - period.date_from).days + 1
        play_seconds = sum(item['seconds'] for item in activity)
        metrics = MapRunMetrics.statistics(records, play_seconds)
        afk = AfkMeasurements.summary(activity, control)
        loading = float(counters['loading_seconds'])
        gaps = MapGapBuilder.build(runs, sessions, selection)
        zones = {code: 0 for code in (*ActivityAreaGroups.CODES, 'other')}

        for run in selected:
            control.check()
            code = ActivityAreaGroups.classify(run.get('area_id', '')) or 'other'
            zones[code] += sum(VisitMeasurements.seconds(v) for v in run['visits'])

        return {'period': selection.metadata(), 'days': days, 'play_seconds': play_seconds,
                'gaps': {key: gaps[key] for key in ('count', 'seconds', 'excluded_pairs', 'branched_sessions', 'unassigned_visits')},
                **afk, 'maps_per_hour_without_afk': cls.ratio(metrics['new'] * 3600, afk['remaining_seconds']),
                'play_per_day': play_seconds / days, 'map_count': metrics['count'],
                'new_maps': metrics['new'], 'map_returns': metrics['returns'],
                'maps_per_day': metrics['new'] / days, 'maps_per_hour': metrics['rate'],
                'map_seconds': metrics['map_seconds'], 'mean_map_seconds': metrics['mean_seconds'],
                'measured_maps': metrics['complete'], 'excluded_maps': metrics['excluded'],
                'incomplete_play_intervals': sum(item['incomplete'] for item in activity),
                'incomplete_zone_visits': summary['zone_totals']['incomplete_visits'],
                'zone_seconds': summary['zone_totals']['seconds'], 'zones': zones,
                'loading_seconds': loading, 'loading_per_day': loading / days, 'loading_count': counters['loading_count'],
                'observation_maps': observations['map_count'],
                'mechanics': {row['code']: row['count'] for row in observations['rows']}}

    @staticmethod
    def ratio(numerator: float, denominator: float) -> float | None:
        return numerator / denominator if denominator else None

    @classmethod
    def row(cls, code: str, label: str, kind: str, a: float | None, b: float | None) -> dict:
        delta = b - a if a is not None and b is not None else None
        change = cls.ratio(delta * 100, a) if delta is not None and a is not None else None

        return {'code': code, 'label_key': label, 'kind': kind, 'a': a, 'b': b,
                'delta': delta, 'change_percent': change}
