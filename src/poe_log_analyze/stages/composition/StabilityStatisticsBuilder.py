from collections import Counter
from datetime import date, datetime
from math import ceil

from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder


class StabilityStatisticsBuilder:
    """Message and repetition summaries; source-branch evidence confirms area and loading links."""

    FAMILIES = ('disconnect', 'network', 'render', 'crash', 'client', 'warning', 'reading')

    @staticmethod
    def family(category: str, code: str) -> str:
        if category in ('crash', 'reading'):
            return category

        if code == 'network.abnormal_disconnect':
            return 'disconnect'

        if code.startswith('network.') or code in ('screen.join_instances_failed', 'screen.join_disconnected',
                                                   'screen.achievement_server_failed'):
            return 'network'

        if code.startswith('render.') or code == 'graph.deadlock':
            return 'render'

        return 'warning' if category == 'warning' else 'client'

    @staticmethod
    def signature(row: dict) -> tuple:
        event = row['event']
        return row['category'], row['code'], event['level'], row['raw_text'], tuple(event['details'])

    @classmethod
    def build(cls, issues: dict, contexts: list[dict], sessions, selection) -> dict:
        control = selection.control
        context = {row['line']: row for row in contexts}
        rows = {}

        for group in issues['groups']:
            for event in group['events']:
                control.check()

                if not selection.period.contains(event['timestamp'], selection.zone_name):
                    continue

                stamp = datetime.fromisoformat(event['timestamp']).astimezone(selection.zone) if event['timestamp'] else None
                line = event['line']
                evidence = context.get(line, {})
                first = sessions.session(line)
                session = sessions.rows.get(first)
                area = evidence.get('area')
                rows[line] = {'line': line, 'event': event, 'raw_text': event['text'], 'code': group['code'],
                    'category': group['category'], 'family': cls.family(group['category'], group['code']),
                    'date': stamp.date().isoformat() if stamp else 'undated',
                    'time': stamp.strftime('%d.%m.%Y %H:%M:%S %z') if stamp else None,
                    'instant': stamp.timestamp() if stamp else None,
                    'href': LogHistoryBuilder.line_href(line), 'previous': evidence.get('previous_line'),
                    'area': {**area, 'href': LogHistoryBuilder.line_href(area['line'])} if area else None,
                    'loading': [{**load, 'href': LogHistoryBuilder.line_href(load['line'])}
                                for load in sorted(evidence.get('loading', []), key = lambda load: (load['timestamp'], load['line']))],
                    'session_id': str(first) if session else None,
                    'session_href': session['path'] + '#session-timeline' if session else None,
                    'session_start': session['start'] if session else None}

        parents = {}

        for line, row in rows.items():
            control.check()
            previous = rows.get(row['previous'])

            if (previous and previous['date'] == row['date'] and row['date'] != 'undated'
                    and previous['session_id'] == row['session_id']
                    and cls.signature(previous) == cls.signature(row)
                    and 0 <= row['instant'] - previous['instant'] <= 60):
                parents[line] = previous['line']

        children = Counter(row['previous'] for row in rows.values() if row['previous'] in rows)
        groups, membership = {}, {}

        for line, row in sorted(rows.items()):
            control.check()
            previous = parents.get(line)
            anchor = membership[previous] if previous in membership and children[previous] == 1 else 'stability-series-' + str(line)
            membership[line] = anchor
            groups.setdefault(anchor, {'anchor': anchor, 'family': row['family'], 'date': row['date'],
                                       'session_id': row['session_id'], 'rows': []})['rows'].append(row)

        ordered = sorted(groups.values(), key = lambda group: (group['rows'][0]['instant'] is None,
                         group['rows'][0]['instant'] or 0, group['rows'][0]['line']))
        by_date, by_session = {}, {}

        for group in ordered:
            control.check()
            first, last = group['rows'][0], group['rows'][-1]
            group.update(count = len(group['rows']), start = first['time'], end = last['time'])
            day = by_date.setdefault(group['date'], {'date': group['date'], 'series': [],
                                                   'anchor': 'stability-day-' + group['date']})
            day['series'].append(group['anchor'])
            key = group['session_id'] or 'unassigned'
            session = by_session.setdefault(key, {'id': key, 'href': first['session_href'],
                'start': first['session_start'], 'series': [], 'anchor': 'stability-session-' + key})
            session['series'].append(group['anchor'])

        for item in [*by_date.values(), *by_session.values()]:
            control.check()
            selected = [row for anchor in item['series'] for row in groups[anchor]['rows']]
            item.update(cls.summary(selected), series_count = len(item['series']))
            areas = Counter(row['area']['name'] if row['area'] else None for row in selected)
            item['areas'] = [{'name': name, 'count': count} for name, count in sorted(areas.items(), key = lambda pair: (pair[0] is None, pair[0] or ''))]
            item['loading_count'] = len({load['line'] for row in selected for load in row['loading']})

        days = dict(sorted(by_date.items()))

        return {'version': '1', 'timezone': selection.zone_name, 'summary': cls.summary(list(rows.values())),
                'series_count': len(groups), 'affected_sessions': len([key for key in by_session if key != 'unassigned']),
                'families': list(cls.FAMILIES), 'series': {group['anchor']: group for group in ordered},
                'by_date': days, 'by_session': by_session, 'chart': cls.chart(days)}

    @classmethod
    def summary(cls, rows: list[dict]) -> dict:
        counts = Counter(row['family'] for row in rows)
        return {'count': len(rows), 'counts': {key: counts[key] for key in cls.FAMILIES},
                'undated': sum(row['date'] == 'undated' for row in rows),
                'unassigned': sum(row['session_id'] is None for row in rows)}

    @classmethod
    def chart(cls, days: dict) -> dict:
        dated = [day for key, day in days.items() if key != 'undated']

        if not dated:
            return {'bars': [], 'ticks': [], 'dates': []}

        first, last = (date.fromisoformat(day['date']).toordinal() for day in (dated[0], dated[-1]))
        span = last - first + 1
        step = max(1, ceil(max(day['count'] for day in dated) / 4))
        bars = []

        for day in dated:
            offset = 0
            segments = []

            for family in cls.FAMILIES:
                height = 210 * day['counts'][family] / (step * 4)
                segments.append({'family': family, 'count': day['counts'][family], 'y': 260 - offset - height, 'height': height})
                offset += height

            bars.append({'date': day['date'], 'anchor': day['anchor'], 'count': day['count'], 'segments': segments,
                         'x': 70 + 860 * (date.fromisoformat(day['date']).toordinal() - first + .5) / span,
                         'width': min(28, 600 / span)})

        ticks = sorted({round((span - 1) * i / 5) for i in range(6)})

        return {'bars': bars, 'ticks': [{'y': 260 - i * 52.5, 'value': i * step} for i in range(5)],
                'dates': [{'x': 70 + 860 * (i + .5) / span, 'label': date.fromordinal(first + i).isoformat()} for i in ticks]}
