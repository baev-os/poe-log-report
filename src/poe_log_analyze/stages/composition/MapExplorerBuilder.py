from datetime import datetime

from poe_log_analyze.runtime.AreaKind import AreaKind

from poe_log_analyze.stages.composition.AfkMeasurements import AfkMeasurements
from poe_log_analyze.stages.composition.AreaDetailsBuilder import AreaDetailsBuilder
from poe_log_analyze.stages.composition.MapPaceBuilder import MapPaceBuilder
from poe_log_analyze.stages.composition.MapRunMetrics import MapRunMetrics
from poe_log_analyze.stages.composition.VisitMeasurements import VisitMeasurements
from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder


class MapExplorerBuilder:
    """Selection records preserve the shared instance, measurement, and evidence methodology."""

    @classmethod
    def build(cls, pace: dict, runs: list[dict], selection, *, afk: dict | None = None) -> dict:
        sources = {run['first_line']: run for run in runs if AreaKind.code(run) == 'map'}
        rows, types, levels, mechanics = [], {}, set(), set()

        for record in pace['rows']:
            selection.control.check()
            run = sources[record['line']]
            key = AreaDetailsBuilder.key(run)
            path = AreaDetailsBuilder.path(key)
            types.setdefault(path, {'area_id': run['area_id'], 'names': set()})['names'].add(run['name'])
            visits, evidence = [], {}
            observed = False

            for visit in run['visits']:
                selection.control.check()
                observed = observed or bool(VisitMeasurements.parts(visit))
                visits.append({**AfkMeasurements.visit(visit, afk), 'href': path + '#visit-' + str(visit['entry_line']),
                               'line': visit['entry_line'], 'level': int(visit['level']) if visit.get('level') is not None else None,
                               'seconds': VisitMeasurements.seconds(visit) if VisitMeasurements.parts(visit) else None})

                for event in visit.get('mechanics', []):
                    evidence[event['line']] = {'code': event['code'], 'line': event['line'],
                                               'href': LogHistoryBuilder.line_href(event['line'])}

            row_levels = sorted({visit['level'] for visit in visits if visit['level'] is not None})
            codes = cls.mechanics(run)
            levels.update(row_levels)
            mechanics.update(codes)
            moment = datetime.fromisoformat(record['timestamp']) if record['timestamp'] else None
            rows.append({**record, 'type': path, 'levels': row_levels, 'mechanics': codes,
                         'date': moment.date().isoformat() if moment else None,
                         'observed': observed, 'visits': visits, 'evidence': list(evidence.values())})

        type_rows = [{'path': path, 'name': ' / '.join(sorted(item['names'])), 'area_id': item['area_id']}
                     for path, item in types.items()]
        names = [item['name'] for item in type_rows]

        for item in type_rows:
            item['label'] = item['name'] + (' · ' + item['area_id'] if names.count(item['name']) > 1 else '')

        type_rows.sort(key = lambda item: (item['name'], item['path']))

        return {'version': '2', 'rows': rows, 'summary': MapPaceBuilder.statistics(rows),
                'without_afk': MapPaceBuilder.statistics(rows, duration_field = 'remaining_seconds'),
                'types': type_rows,
                'levels': sorted(levels), 'mechanics': sorted(mechanics)}

    @staticmethod
    def mechanics(run: dict) -> list[str]:
        return sorted({event['code'] for visit in run['visits'] for event in visit.get('mechanics', [])})

    @classmethod
    def memberships(cls, original: list[dict], runs: list[dict], selection) -> list[dict]:
        """Instance membership for simple shares without durations or contexts."""

        sources = {(run['area_id'], run['first_line']): run for run in original}
        rows = []

        for run in runs:
            selection.control.check()

            if AreaKind.code(run) != 'map':
                continue

            source = sources[(run['area_id'], run['first_line'])]
            rows.append({'line': run['first_line'], 'area_id': run['area_id'], 'name': run['name'],
                         'timestamp': source.get('started_at'), 'new': int(MapRunMetrics.is_new(source, selection)),
                         'mechanics': cls.mechanics(run)})

        rows.sort(key = lambda row: (row['timestamp'] is None,
                  datetime.fromisoformat(row['timestamp']).timestamp() if row['timestamp'] else 0, row['line']))

        return rows
