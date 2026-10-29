from poe_log_analyze.stages.composition.analytics.MeasuredSpanIndex import MeasuredSpanIndex
from poe_log_analyze.stages.composition.MapObservationStatisticsBuilder import MapObservationStatisticsBuilder
from poe_log_analyze.stages.reconstruction.MapEncounterTracker import MapEncounterTracker


class MarkerOrderBuilder:
    """Adjacent original markers retain repeats; branches and breaks get no shared ordering."""

    @classmethod
    def build(cls, index, explorer, spans) -> dict:
        spans.selection.control.check()
        selected = {row['line']: row for row in explorer['rows']}
        recorded, rows, signals, ambiguous = {}, [], [], 0

        for source in index.evidence['events']:
            spans.selection.control.check()

            if 'marker_code' not in source:
                continue

            event = index.record(source)
            context = event['context']
            event.update(source_code = event['code'], code = event['marker_code'])

            if spans.selection.period.contains(event['timestamp'], spans.selection.zone_name):
                signals.append(event)

            if (context and context['kind'] == 'map' and context['run_line'] in selected and
                    context['area_id'] and MapEncounterTracker.mechanic_area(context['area_id'])):
                event.update(visit_line = context['visit_line'], returned = context['visit_line'] != context['run_line'])
                recorded.setdefault(context['run_line'], []).append(event)

        for line, events in sorted(recorded.items()):
            spans.selection.control.check()
            record = selected[line]

            if any(event['context']['branched'] for event in events):
                ambiguous += 1
                continue

            ordered = sorted(events, key = lambda event: event['line'])

            for length in (2, 3):
                for offset in range(len(ordered) - length + 1):
                    path = ordered[offset:offset + length]
                    a, b = path[0], path[-1]

                    if len({event['marker_epoch'] for event in path}) != 1:
                        continue

                    if not spans.selection.period.contains(b['timestamp'], spans.selection.zone_name):
                        continue

                    span = None

                    if a['timestamp'] and b['timestamp'] and spans.moment(b['timestamp']) >= spans.moment(a['timestamp']):
                        span = spans.measure(spans.sessions.session(a['line']), a['timestamp'], b['timestamp'])

                    excluded = list(record['excluded'])

                    if span is None or not span['covered'] or span['overlapping']:
                        excluded.append('incomplete')

                    if span and span['clipped']:
                        excluded.append('clipped')

                    rows.append({'line': b['line'], 'length': length, 'codes': [event['code'] for event in path],
                                 'name': record['name'], 'href': f'maps/runs/{line}/index.html', 'path': path,
                                 'returned': b['returned'], 'same_visit': a['visit_line'] == b['visit_line'], 'span': span,
                                 'seconds': span['elapsed_seconds'] if span else None,
                                 'remaining_seconds': span['remaining_seconds'] if span else None,
                                 'excluded': sorted(set(excluded))})

        groups = {}

        for row in rows:
            groups.setdefault((tuple(row['codes']), row['returned'], row['same_visit']), []).append(row)

        return {'version': '1', 'rows': rows, 'signals': signals, 'ambiguous_maps': ambiguous,
                'groups': [{'codes': list(codes), 'label_keys': [MapObservationStatisticsBuilder.LABELS[code] for code in codes],
                            'returned': returned, 'same_visit': same_visit, 'count': len(records),
                            'summary': MeasuredSpanIndex.statistics(records),
                            'without_afk': MeasuredSpanIndex.statistics(records, 'remaining_seconds'),
                            'evidence': [event['href'] for row in records for event in row['path']]}
                           for (codes, returned, same_visit), records in sorted(groups.items())]}
