from poe_log_analyze.stages.composition.analytics.MeasuredSpanIndex import MeasuredSpanIndex
from poe_log_analyze.stages.composition.MapPaceBuilder import MapPaceBuilder
from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder


class LevelProgressBuilder:
    """Intervals between named level messages without assigning an owner or experience."""

    @classmethod
    def build(cls, index, spans) -> dict:
        index.selection.control.check()
        events = {row['line']: row for row in index.evidence['events']}
        successors = {}

        for event in events.values():
            index.selection.control.check()

            if event['code'] == 'screen.level_up' and event.get('previous_level_line') is not None:
                successors.setdefault(event['previous_level_line'], []).append(event['line'])

        rows = []

        for event in index.selected({'screen.level_up'}):
            index.selection.control.check()
            previous = events.get(event.get('previous_level_line'))
            start = index.record(previous) if previous else None
            a, b = previous['fields'] if previous else None, event['fields']
            state, span, wall = 'first', None, None

            if a is not None:
                delta = int(b['level']) - int(a['level'])
                state = ('class_changed' if a['class'] != b['class'] else 'repeated' if delta == 0 else
                         'reset' if delta < 0 else 'gap' if delta > 1 else 'consecutive')

                if len(successors[previous['line']]) > 1:
                    state = 'ambiguous'

                if previous['timestamp'] and event['timestamp'] and spans.moment(event['timestamp']) >= spans.moment(previous['timestamp']):
                    wall = (spans.moment(event['timestamp']) - spans.moment(previous['timestamp'])).total_seconds()
                    first = index.sessions.session(previous['line'])

                    if first is not None and index.sessions.session(event['line']) == first:
                        span = spans.measure(first, previous['timestamp'], event['timestamp'])

            excluded = [] if state == 'consecutive' else ['incomplete']

            if span is None or not span['covered'] or span['overlapping']:
                excluded.append('incomplete')

            if span is not None and span['clipped']:
                excluded.append('clipped')

            first = index.sessions.session(event['line'])

            if first is not None and index.sessions.rows[first]['branched']:
                excluded.append('branched')

            rows.append({'line': event['line'], 'event': event, 'previous': start, 'state': state,
                         'character': b['character'], 'level': int(b['level']), 'from_level': int(a['level']) if a else None,
                         'wall_seconds': wall, 'wall_duration': MapPaceBuilder.duration(wall), 'span': span,
                         'seconds': span['seconds'] if span else None,
                         'remaining_seconds': span['remaining_seconds'] if span else None,
                         'death_hrefs': [LogHistoryBuilder.line_href(line) for line in event.get('death_lines', [])] if previous else [],
                         'excluded': list(dict.fromkeys(excluded))})

        characters, ranges = {}, {}

        for row in rows:
            characters.setdefault(row['character'], []).append(row)
            ranges.setdefault('below_90' if row['level'] < 90 else 'from_90', []).append(row)

        return {'version': '1', 'rows': rows, 'consecutive_count': sum(row['state'] == 'consecutive' for row in rows),
                'groups': [{'character': name, **cls.statistics(records)} for name, records in sorted(characters.items())],
                'ranges': [{'key': key, **cls.statistics(records)} for key, records in sorted(ranges.items())]}

    @staticmethod
    def statistics(rows) -> dict:
        return {'count': len(rows), 'wall': MeasuredSpanIndex.statistics(rows, 'wall_seconds'),
                'summary': MeasuredSpanIndex.statistics(rows), 'without_afk': MeasuredSpanIndex.statistics(rows, 'remaining_seconds')}
