from poe_log_analyze.stages.composition.analytics.MeasuredSpanIndex import MeasuredSpanIndex
from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder
from poe_log_analyze.stages.merging.SourceObservationEvidence import SourceObservationEvidence


class MilestoneHistoryBuilder:
    """Marker order and /played/age snapshots without assigning ownership or totals."""

    @classmethod
    def build(cls, index, spans) -> dict:
        events = {row['line']: row for row in index.evidence['events']}
        rows = index.selected(SourceObservationEvidence.MILESTONES | SourceObservationEvidence.CLOCKS)
        groups = {}

        for row in rows:
            index.selection.control.check()
            previous = events.get(row.get('previous_milestone_line'))
            row['previous'] = index.record(previous) if previous else None
            start, end = previous['timestamp'] if previous else None, row['timestamp']
            row['seconds'] = ((spans.moment(end) - spans.moment(start)).total_seconds()
                              if start and end and spans.moment(end) >= spans.moment(start) else None)
            row['span'] = spans.measure(index.sessions.session(row['line']), start, end) if row['seconds'] is not None else None
            row['excluded'] = [] if row['seconds'] is not None else ['incomplete']

            if row['span'] is not None and row['span']['clipped']:
                row['excluded'].append('clipped')

            first = index.sessions.session(row['line'])

            if first is not None and index.sessions.rows[first]['branched']:
                row['excluded'].append('branched')

            row['clock_seconds'] = (sum(int(row['fields'].get(field, 0)) * factor for field, factor in
                                        (('days', 86400), ('hours', 3600), ('minutes', 60), ('seconds', 1)))
                                    if row['code'] in SourceObservationEvidence.CLOCKS else None)
            row['previous_href'] = LogHistoryBuilder.line_href(previous['line']) if previous else None

            for dimension, key in (('code', row['code']), ('date', row['date']), ('session', row['session_id'])):
                groups.setdefault((dimension, str(key or '')), []).append(row)

        return {'version': '1', 'rows': rows, 'groups': [
            {'dimension': dimension, 'key': key, 'count': len(records), 'evidence': [row['href'] for row in records]}
            for (dimension, key), records in sorted(groups.items())]}
