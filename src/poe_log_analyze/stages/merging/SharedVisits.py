from copy import deepcopy

from poe_log_analyze.runtime.AreaKind import AreaKind

from poe_log_analyze.stages.merging.SharedIntervals import SharedIntervals


class SharedVisits:
    """One confirmed entry means one visit with separate continuations and measurements."""

    EVENTS = ('mechanics', 'discoveries', 'mercenaries', 'death_messages')
    SCOPES = ('period_observations', 'comparison_observations')

    def __init__(self, intervals: SharedIntervals):
        self.intervals = intervals
        self.history = intervals.history
        self.control = self.history.control

    def merge(self, runs: list[dict]) -> list[dict]:
        groups = {}

        for run in runs:
            groups.setdefault((run['area_id'], run['first_line']), []).append(run)

        result = [self.run(records) for records in groups.values()]
        summary = self.history.summary
        summary['removed_runs'] = len(runs) - len(result)
        summary['removed_maps'] = sum(AreaKind.code(r) == 'map' for r in runs) - sum(AreaKind.code(r) == 'map' for r in result)
        summary['removed_visits'] = sum(len(r['visits']) for r in runs) - sum(len(r['visits']) for r in result)
        summary['removed_map_seconds'] = (sum(r['seconds'] for r in runs if AreaKind.code(r) == 'map')
                                          - sum(r['seconds'] for r in result if AreaKind.code(r) == 'map'))
        summary['branched_runs'] = sum(run['branched'] for run in result)
        summary['branched_visits'] = sum(bool(visit.get('branches')) for run in result for visit in run['visits'])

        return result

    def run(self, records: list[dict]) -> dict:
        self.control.check()
        paths = self.intervals.maximal(records)
        self.intervals.exclusions(records, paths, 'map_run')
        result = deepcopy(paths[0])
        groups = {}

        for record in records:
            for visit in record['visits']:
                groups.setdefault(visit['entry_line'], []).append(visit)

        result['visits'] = sorted((self.visit(copies) for copies in groups.values()),
            key = lambda v: (v['entered_at'] is None, v['entered_at'] or '', self.history.order(v)))
        result['origins'] = [{'source': r['origin']['source'], 'run_id': r['origin']['run_id']} for r in records]
        result['branched'] = len(paths) > 1
        result['seconds'] = sum(v['measured_seconds'] for v in result['visits'])
        result['afk_seconds'] = sum(sum(p.get('afk_seconds') or 0 for p in v.get('segments', [v])) for v in result['visits'])
        result['entrances'] = len(result['visits'])
        result['returns'] = result['entrances'] - 1
        result['unbounded_visits'] = sum(not v['bounded'] for v in result['visits'])
        result['uncertain_line_numbers'] = sorted({n for r in records for n in r.get('uncertain_line_numbers', [])})
        result['uncertain_lines'] = len(result['uncertain_line_numbers'])
        result['death_messages'] = self.events(records, 'death_messages')

        if result['branched']:
            result['between_visits_seconds'] = None
            result['end_reason_code'] = 'branches'

        return result

    def visit(self, records: list[dict]) -> dict:
        self.control.check()
        branches = self.intervals.maximal(records)
        result = deepcopy(branches[0])
        result['origins'] = [deepcopy(record['origin']) for record in records]

        if len(branches) == 1:
            result['measured_seconds'] = result['seconds'] if result['bounded'] else 0
            return result

        measured = [record for record in records if record['bounded'] and record['seconds'] is not None]
        result['segments'] = self.intervals.segments(measured, 'entered_at', 'ended_at')
        result['branches'] = deepcopy(branches)
        result['bounded'] = all(record['bounded'] for record in branches)
        result['measured_seconds'] = sum(part['seconds'] for part in result['segments'])
        result['seconds'] = result['measured_seconds'] if result['bounded'] else None
        result['afk_seconds'] = sum(part['afk_seconds'] for part in result['segments']) if result['bounded'] else None
        endings = {record['ended_at'] for record in branches}
        result['ended_at'] = next(iter(endings)) if len(endings) == 1 else None

        if len(branches) > 1:
            result['end_reason_code'] = 'branches'

        for field in self.EVENTS:
            result[field] = self.events(records, field)

        for scope in self.SCOPES:
            if any(scope in record for record in records):
                result[scope] = {field: self.events([r.get(scope, {}) for r in records], field) for field in self.EVENTS}

        return result

    @staticmethod
    def events(records: list[dict], field: str) -> list[dict]:
        events = {event['line']: event for record in records for event in record.get(field, [])}
        return [deepcopy(events[line]) for line in sorted(events)]
