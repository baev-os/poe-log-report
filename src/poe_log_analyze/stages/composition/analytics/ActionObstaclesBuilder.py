from collections import Counter

from poe_log_analyze.stages.composition.MapPaceBuilder import MapPaceBuilder
from poe_log_analyze.stages.composition.analytics.MeasuredSpanIndex import MeasuredSpanIndex
from poe_log_analyze.stages.merging.SourceActivityEvidence import SourceActivityEvidence


class ActionObstaclesBuilder:
    """Gameplay obstacles are separate from technical faults; a pause does not measure their cost."""

    @classmethod
    def build(cls, index, gaps) -> dict:
        rows = index.selected(SourceActivityEvidence.OBSTACLES)
        by_line = {row['line']: row for row in rows}
        parents = {line: line for line in by_line}
        children, days, categories, marked_gaps = Counter(), {}, Counter(), {}

        for row in rows:
            index.selection.control.check()
            row['category'] = SourceActivityEvidence.OBSTACLES[row['code']]
            days[row['date']] = days.get(row['date'], 0) + 1
            categories[row['category']] += 1
            previous = by_line.get(row.get('previous_line'))
            same_area = (previous is not None and row['context'] is not None and previous['context'] is not None
                         and row['context']['visit_line'] == previous['context']['visit_line'])

            if (previous is not None and previous['code'] == row['code'] and same_area
                    and row['session_id'] is not None and row['session_id'] == previous['session_id']):
                parents[cls.root(parents, row['line'])] = cls.root(parents, previous['line'])
                children[previous['line']] += 1

            if not row['timestamp']:
                continue

            for number, gap in enumerate(gaps['rows']):
                index.selection.control.check()

                if (row['session_id'] == gap['session_id'] and gap['from_line'] <= row['line'] < gap['line']
                        and MeasuredSpanIndex.moment(gap['started_at']) <= MeasuredSpanIndex.moment(row['timestamp']) <= MeasuredSpanIndex.moment(gap['ended_at'])):
                    marked = marked_gaps.setdefault(number, {'start': gap['start'], 'end': gap['end'], 'duration': gap['duration'],
                        'from_href': gap['from_href'], 'to_href': gap['to_href'], 'from_name': gap['from_name'],
                        'to_name': gap['to_name'], 'lines': [], 'events': []})
                    marked['lines'].append(row['line'])
                    marked['events'].append({'line': row['line'], 'href': row['href'], 'time': row['time']})

        components = {}

        for row in rows:
            components.setdefault(cls.root(parents, row['line']), []).append(row)

        groups = []

        for events in components.values():
            index.selection.control.check()
            events.sort(key = lambda row: row['line'])
            branched = any(children[row['line']] > 1 for row in events)
            first, last = events[0], events[-1]
            seconds = ((MeasuredSpanIndex.moment(last['timestamp']) - MeasuredSpanIndex.moment(first['timestamp'])).total_seconds()
                       if not branched and first['timestamp'] and last['timestamp'] else None)
            groups.append({'line': first['line'], 'code': first['code'], 'category': first['category'],
                           'count': len(events), 'branched': branched, 'events': events,
                           'seconds': seconds, 'duration': MapPaceBuilder.duration(seconds)})

        return {'version': '1', 'count': len(rows), 'groups': groups,
                'unknown_context': sum(row['context'] is None for row in rows),
                'days': [{'date': day, 'count': count} for day, count in sorted(days.items())],
                'categories': [{'code': code, 'count': count} for code, count in sorted(categories.items())],
                'gaps': list(marked_gaps.values())}

    @staticmethod
    def root(parents, line):
        while parents[line] != line:
            parents[line] = parents[parents[line]]
            line = parents[line]

        return line
