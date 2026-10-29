from poe_log_analyze.runtime.AreaKind import AreaKind

from poe_log_analyze.stages.composition.AfkMeasurements import AfkMeasurements
from poe_log_analyze.stages.composition.analytics.MeasuredSpanIndex import MeasuredSpanIndex
from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder


class ReturnProfileBuilder:
    """First and repeated visits without assuming a reason for returning."""

    @classmethod
    def build(cls, original, selected, explorer, spans, afk, details) -> dict:
        spans.selection.control.check()
        sources = {run['first_line']: run for run in original if AreaKind.code(run) == 'map'}
        chosen = {run['first_line']: run for run in selected if AreaKind.code(run) == 'map'}
        measurements = {row['line']: row for row in explorer['rows']}
        routes = {}

        for run in original:
            for visit in run['visits']:
                first = spans.sessions.session(visit['entry_line'])
                routes.setdefault(first, []).append({'line': visit['entry_line'], 'name': run['name'],
                                                     'kind': AreaKind.code(run), 'href': LogHistoryBuilder.line_href(visit['entry_line'])})

        rows, episodes = [], []

        for line, run in chosen.items():
            spans.selection.control.check()
            source, record = sources[line], measurements[line]
            initial, returned = [], []
            ordered = sorted(source['visits'], key = lambda visit: visit['entry_line'])
            positions = {visit['entry_line']: index for index, visit in enumerate(ordered)}

            for visit in run['visits']:
                spans.selection.control.check()
                balance = AfkMeasurements.visit(visit, afk)

                if visit['entry_line'] == line:
                    initial.append(balance)
                    continue

                returned.append(balance)
                position = positions[visit['entry_line']]
                original_visit = ordered[position]

                if not spans.selection.period.contains(original_visit.get('entered_at'), spans.selection.zone_name):
                    continue

                previous = ordered[position - 1] if position else None
                first = spans.sessions.session(visit['entry_line'])
                span, via = None, []

                if (previous is not None and first is not None and not spans.sessions.rows[first]['branched']
                        and spans.sessions.session(previous['entry_line']) == first and previous['bounded']
                        and previous.get('ended_at') and original_visit.get('entered_at')
                        and spans.moment(previous['ended_at']) <= spans.moment(original_visit['entered_at'])):
                    span = spans.measure(first, previous['ended_at'], original_visit['entered_at'])
                    via = sorted((dict(item) for item in routes.get(first, [])
                                  if previous['entry_line'] < item['line'] < visit['entry_line']), key = lambda item: item['line'])

                episodes.append({'line': visit['entry_line'], 'name': run['name'],
                                 'href': details['links'].get(str(visit['entry_line'])) or LogHistoryBuilder.line_href(visit['entry_line']),
                                 'previous_href': LogHistoryBuilder.line_href(previous['entry_line']) if previous else None,
                                 'span': span, 'via': via})

            a, b = AfkMeasurements.combine(initial), AfkMeasurements.combine(returned)
            rows.append({'line': line, 'name': run['name'], 'href': details['links'][str(line)],
                         'returns': record['returns'], 'first': a, 'returned': b, 'excluded': list(record['excluded']),
                         'first_seconds': a['seconds'], 'returned_seconds': b['seconds'],
                         'first_remaining_seconds': a['remaining_seconds'], 'returned_remaining_seconds': b['remaining_seconds']})

        returned_rows = [row for row in rows if row['returns']]
        buckets = [{'returns': count, 'count': sum(row['returns'] == count for row in rows),
                    'share': sum(row['returns'] == count for row in rows) * 100 / len(rows) if rows else None}
                   for count in sorted({row['returns'] for row in rows})]

        return {'version': '1', 'rows': rows, 'episodes': episodes, 'map_count': len(rows),
                'returned_count': len(returned_rows), 'buckets': buckets,
                'share': len(returned_rows) * 100 / len(rows) if rows else None,
                'first': AfkMeasurements.combine([row['first'] for row in rows]),
                'returned': AfkMeasurements.combine([row['returned'] for row in rows]),
                'modes': {mode: {'first': MeasuredSpanIndex.statistics(rows, 'first_' + field),
                                 'returned': MeasuredSpanIndex.statistics(returned_rows, 'returned_' + field)}
                          for mode, field in (('all', 'seconds'), ('without_afk', 'remaining_seconds'))}}
