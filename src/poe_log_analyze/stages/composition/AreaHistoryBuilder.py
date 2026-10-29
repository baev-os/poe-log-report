from typing import Any

from poe_log_analyze.stages.composition.MapRowOrdering import MapRowOrdering

from poe_log_analyze.runtime.DurationFormatter import DurationFormatter
from poe_log_analyze.runtime.AreaKind import AreaKind

from poe_log_analyze.stages.composition.VisitMeasurements import VisitMeasurements


class AreaHistoryBuilder:
    """Readable area, town, and hideout visits on one timeline."""

    @staticmethod
    def build(model: dict[str, Any]) -> dict[str, Any]:
        rows = []

        for day in model['by_date'].values():
            for run in day['runs']:
                for visit in run['visits']:
                    entered, exited = MapRowOrdering.moment(visit['entered_at']), MapRowOrdering.moment(visit['ended_at'])
                    rows.append({'name': run['name'], 'kind': run['kind'], 'kind_code': AreaKind.code(run),
                                 'entered_at': visit['entered_at'], 'exited_at': visit['ended_at'],
                                 'entry': entered.strftime('%d.%m.%Y %H:%M:%S') if entered else '—',
                                 'exit': exited.strftime('%d.%m.%Y %H:%M:%S') if exited else '—',
                                 'duration': DurationFormatter.duration_label(VisitMeasurements.seconds(visit)) if VisitMeasurements.parts(visit) else '—',
                                 'branched': bool(visit.get('branches')),
                                 '_line': visit['entry_line'], '_anchor': visit.get('position_at')})

        return {'rows': MapRowOrdering.ordered_rows(rows), 'count': len(rows), 'kinds': sorted({r['kind'] for r in rows})}
