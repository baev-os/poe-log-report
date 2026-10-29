from typing import Any

from poe_log_analyze.runtime.AreaKind import AreaKind

from collections import Counter


class MapProjection:
    """Selected-run summary preserving the existing map contract."""

    @staticmethod
    def build(runs: list[dict[str, Any]], models: list[dict[str, Any]], coverage: dict[str, Any]) -> dict[str, Any]:
        result = dict(models[0])
        days = {}

        for number, run in enumerate(runs, 1):
            run['id'] = number
            day = days.setdefault(run['date'], {'date': run['date'], 'runs': [], 'seconds': 0})
            day['runs'].append(run)
            day['seconds'] += run['seconds']

        result.update(by_date = days, days = [{'date': key, 'count': len(day['runs']), 'seconds': day['seconds']}
                                        for key,day in sorted(days.items())],
                      total_lines = coverage['total_lines'], run_count = len(runs),
                      map_count = sum(AreaKind.code(r)=='map' for r in runs), arena_count = sum(AreaKind.code(r)=='arena' for r in runs),
                      statuses = {s:coverage[s+'_lines'] for s in ('recognized','unknown','error') if coverage[s+'_lines']})

        for key in ('seconds', 'afk_seconds', 'unbounded_visits', 'entrances'):
            result[key] = sum(run[key] for run in runs)

        for field, key, attribute in (('diagnostic_events', 'diagnostics', 'kind'),
                                      ('outside_entries', 'outside_areas', 'area_id')):
            unique = {(item[attribute], item['line']) for model in models for item in model.get(field, [])}
            result[field] = [{attribute: label, 'line': line} for label,line in sorted(unique, key = lambda p: (p[1], p[0]))]
            result[key] = dict(sorted(Counter(label for label,_ in unique).items()))

        return result
