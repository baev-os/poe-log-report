from poe_log_analyze.stages.composition.analytics.MeasuredSpanIndex import MeasuredSpanIndex


class AreaRoutePatternsBuilder:
    """Observed entry pairs and triples; equal IDs do not prove the same instance."""

    @classmethod
    def build(cls, index, spans) -> dict:
        index.selection.control.check()
        events = {row['line']: row for row in index.evidence['events'] if row['code'] == 'area.enter'}
        rows, unknown = [], 0

        for path in index.evidence['paths']:
            index.selection.control.check()
            records = [index.record(events[line]) for line in path]
            a, b = records[0], records[-1]

            if not index.selection.period.contains(b['timestamp'], index.selection.zone_name):
                continue

            contexts = [row['context'] for row in records]

            if any(context is None for context in contexts):
                unknown += 1
                continue

            first = index.sessions.session(a['line'])
            span = spans.measure(first, a['timestamp'], b['timestamp'])
            excluded = []

            if first is None or any(index.sessions.session(row['line']) != first for row in records):
                excluded.append('multiple_sessions')

            if first is not None and index.sessions.rows[first]['branched']:
                excluded.append('branched')

            if any(context['kind'] == 'map' and not context.get('identity_complete') for context in contexts):
                excluded.append('identity')

            if span is None or not span['covered'] or span['overlapping']:
                excluded.append('incomplete')

            if span is not None and span['clipped']:
                excluded.append('clipped')

            keys = [context['area_id'] or context['name'] for context in contexts]
            loop = len(keys) == 3 and all(context['area_id'] for context in contexts) and keys[0] == keys[2] and keys[0] != keys[1]
            rows.append({'line': b['line'], 'length': len(path), 'path': records, 'keys': keys,
                         'loop': loop, 'same_instance': bool(loop and contexts[0].get('identity_complete')
                                                           and contexts[2].get('identity_complete')
                                                           and contexts[0]['run_line'] == contexts[2]['run_line']),
                         'span': span, 'seconds': span['seconds'] if span else None,
                         'remaining_seconds': span['remaining_seconds'] if span else None, 'excluded': excluded})

        groups = {}

        for row in rows:
            groups.setdefault(tuple(row['keys']), []).append(row)

        return {'version': '1', 'rows': rows, 'unknown_paths': unknown,
                'edge_count': sum(row['length'] == 2 for row in rows), 'chain_count': sum(row['length'] == 3 for row in rows),
                'loop_count': sum(row['loop'] for row in rows), 'same_instance_count': sum(row['same_instance'] for row in rows),
                'groups': [{'path': records[0]['path'], 'count': len(records), 'loop': records[0]['loop'],
                            'same_instance_count': sum(row['same_instance'] for row in records),
                            'summary': MeasuredSpanIndex.statistics(records),
                            'without_afk': MeasuredSpanIndex.statistics(records, 'remaining_seconds')}
                           for key, records in sorted(groups.items(), key = lambda pair: (-len(pair[1]), pair[0]))]}
