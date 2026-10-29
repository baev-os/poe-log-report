from decimal import Decimal
from itertools import combinations

from poe_log_analyze.stages.composition.analytics.ObservationSamples import ObservationSamples
from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder
from poe_log_analyze.stages.merging.SourceObservationEvidence import SourceObservationEvidence


class ClientEnvironmentBuilder:
    """Comparable recorded measurements by client context without causal claims."""

    KEYS = ('engine', 'revision', 'backend', 'driver')

    @classmethod
    def build(cls, index) -> dict:
        index.selection.control.check()
        codes = {row['code'] for row in index.evidence['events'] if row.get('issue')}
        rows = index.selected(codes | set(SourceObservationEvidence.ENVIRONMENT) |
                              {'loading.duration', 'network.connected', 'network.instance_latency'})
        groups, issues, exposure = {}, {}, {}

        for item in index.evidence.get('environment_intervals', []):
            index.selection.control.check()
            bounds = index.selection.clip(item['started_at'], item['ended_at'])

            if bounds is not None:
                key = tuple(item['environment'].get(key, {}).get('value') for key in cls.KEYS)
                exposure[key] = exposure.get(key, 0) + bounds[2]

        for row in rows:
            index.selection.control.check()
            metadata = row.get('environment', {})
            row['environment_values'] = [metadata.get(key, {}).get('value') for key in cls.KEYS]
            row['environment_proofs'] = [LogHistoryBuilder.line_href(metadata[key]['line'])
                                         for key in cls.KEYS if key in metadata]
            environment = tuple(row['environment_values'])
            row['complete_environment'] = all(value is not None for value in environment)
            context = row['context']

            if row['code'] in ('loading.duration', 'network.connected', 'network.instance_latency'):
                unit = 's' if row['code'] == 'loading.duration' else 'ms'
                row['value'] = float(Decimal(row['fields']['seconds' if unit == 's' else 'milliseconds']))
                # A loading-screen name retains its purpose before a confirmed entry.
                target = row['fields'].get('area') if unit == 's' else None
                area = target or (context['area_id'] if context else None)
                key = environment, row['code'], area, context['level'] if context and not target else None
                groups.setdefault(key, []).append(row)

            if row.get('issue'):
                issues.setdefault((environment, row['code']), []).append(row)

        summaries = [
            {'environment': list(environment), 'code': code, 'area': area, 'level': level,
             'unit': 's' if code == 'loading.duration' else 'ms',
             'stats': ObservationSamples.build(row['value'] for row in records),
             'comparable': (area is not None and all(value is not None for value in environment) and
                            (code == 'loading.duration' or level is not None)),
             'evidence': [row['href'] for row in records]}
            for (environment, code, area, level), records in sorted(groups.items(), key = lambda pair: str(pair[0]))]

        return {'version': '1', 'rows': rows, 'groups': summaries,
            'comparisons': cls.comparisons(summaries, index),
            'exposure': [{'environment': list(environment), 'seconds': seconds}
                         for environment, seconds in sorted(exposure.items(), key = lambda pair: str(pair[0]))],
            'issues': [{'environment': list(environment), 'code': code, 'count': len(records),
                        'seconds': exposure.get(environment),
                        'per_hour': len(records) * 3600 / exposure[environment] if exposure.get(environment) else None,
                        'evidence': [row['href'] for row in records]}
                       for (environment, code), records in sorted(issues.items(), key = lambda pair: str(pair[0]))]}

    @staticmethod
    def comparisons(rows, index) -> list[dict]:
        groups, result = {}, []

        for row in rows:
            index.selection.control.check()

            if row['comparable']:
                groups.setdefault((row['code'], row['area'], row['level']), []).append(row)

        for (code, area, level), records in sorted(groups.items(), key = lambda pair: str(pair[0])):
            for a, b in combinations(records, 2):
                index.selection.control.check()
                enough = a['stats']['count'] >= 5 and b['stats']['count'] >= 5
                result.append({'code': code, 'area': area, 'level': level, 'unit': a['unit'],
                               'a': a, 'b': b, 'difference': b['stats']['median'] - a['stats']['median'] if enough else None})

        return result
