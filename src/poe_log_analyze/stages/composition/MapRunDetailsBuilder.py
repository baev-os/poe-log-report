from collections import defaultdict

from poe_log_analyze.runtime.AreaKind import AreaKind

from poe_log_analyze.stages.composition.AfkMeasurements import AfkMeasurements
from poe_log_analyze.stages.composition.MapGapBuilder import MapGapBuilder
from poe_log_analyze.stages.composition.MapOutlierBuilder import MapOutlierBuilder
from poe_log_analyze.stages.composition.MapPaceBuilder import MapPaceBuilder
from poe_log_analyze.stages.composition.MapRunTimelineBuilder import MapRunTimelineBuilder
from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder


class MapRunDetailsBuilder:
    """Instance cards join existing measurements through evidence line numbers."""

    @staticmethod
    def path(line: int) -> str:
        return f'maps/runs/{line}/index.html'

    @classmethod
    def build(cls, original: list[dict], selected: list[dict], views: dict, sessions, selection) -> dict:
        control = selection.control
        records = views['map_explorer']['rows']
        sources = {run['first_line']: run for run in original if AreaKind.code(run) == 'map'}
        runs = {run['first_line']: run for run in selected if AreaKind.code(run) == 'map'}
        visits = {visit['line']: visit for area in views['area_details']['pages']
                  for day in area['days'] for visit in day['rows']}
        loads, issues, marked = defaultdict(list), defaultdict(list), defaultdict(list)
        return_gaps = {gap['line']: gap for gap in views['map_pace']['gaps']['rows'] if gap['return']}

        for route in views['loading_routes']['routes']:
            for load in route['rows']:
                control.check()

                for line in {load['from_line'], load['to_line']} - {None}:
                    loads[line].append(load)

        for group in views['stability']['series'].values():
            for issue in group['rows']:
                control.check()

                if issue['area']:
                    issues[issue['area']['line']].append(issue)

        visit_afk = defaultdict(list)

        for row in views['afk']['rows']:
            marked[row['session_id']].append(row)
            visit_afk[row['visit_line']].append(row)

        comparisons = cls.comparisons(records, control)
        pages, links, visit_links = [], {}, {}

        for record in records:
            control.check()
            line = record['line']
            source, run = sources[line], runs[line]
            history = [dict(visits[item['entry_line']], level = item.get('level')) for item in run['visits']]
            selected_lines = {visit['line'] for visit in history}
            loading = {load['line']: load for entry in selected_lines for load in loads[entry]}
            failures = {issue['line']: issue for entry in selected_lines for issue in issues[entry]}
            gaps = cls.gaps(source, return_gaps, marked, selection)
            measured_gaps = [gap for gap in gaps if gap['known']]
            path = cls.path(line)
            page = {**record, 'path': path, 'visits': history,
                    'gaps': gaps, 'gap_balance': (AfkMeasurements.combine(measured_gaps) if measured_gaps or not gaps
                                                else AfkMeasurements.balance(None, None)),
                    'afk_rows': [row for entry in selected_lines for row in visit_afk[entry]],
                    'unknown_gaps': sum(not gap['known'] for gap in gaps),
                    'loading': sorted(loading.values(), key = lambda row: row['line']),
                    'issues': sorted(failures.values(), key = lambda row: row['line']),
                    'comparisons': comparisons[line], 'previous': None, 'next': None,
                    'original_visits': len(source['visits'])}
            page['timeline'] = MapRunTimelineBuilder.build(page, run, selection)
            pages.append(page)
            links[str(line)] = path

            for visit in history:
                visit_links[str(visit['line'])] = path + '#' + visit['anchor']

        cls.navigation(pages, sources, sessions)

        return {'version': '1', 'timezone': selection.zone_name, 'pages': pages,
                'links': links, 'visit_links': visit_links, 'minimum_peers': MapOutlierBuilder.MINIMUM_PEERS}

    @staticmethod
    def comparisons(rows: list[dict], control) -> dict:
        result = {row['line']: {} for row in rows}

        for mode, field in (('all', 'seconds'), ('without_afk', 'remaining_seconds')):
            groups = defaultdict(list)

            for row in rows:
                control.check()
                level = MapOutlierBuilder.level(row)
                result[row['line']][mode] = {'status': 'excluded', 'peers': 0, 'median_seconds': None,
                                             'difference_seconds': None, 'percent': None}

                if not row['excluded'] and row['area_id'] and level is not None and row[field] is not None:
                    groups[(row['area_id'], level)].append(row)

            for group in groups.values():
                ordered = sorted(group, key = lambda row: (row[field], row['line']))
                values = [row[field] for row in ordered]

                for index, row in enumerate(ordered):
                    control.check()
                    peers = len(group) - 1
                    median = MapOutlierBuilder.peer_median(values, index) if peers >= MapOutlierBuilder.MINIMUM_PEERS else None
                    difference = row[field] - median if median is not None else None
                    result[row['line']][mode] = {'status': 'ready' if median is not None else 'insufficient',
                        'peers': peers, 'median_seconds': median, 'median': MapPaceBuilder.duration(median),
                        'difference_seconds': difference, 'percent': difference * 100 / median if median else None,
                        'difference': (('+' if difference > 0 else '−' if difference < 0 else '')
                                       + MapPaceBuilder.duration(abs(difference))) if difference is not None else '—'}

        return result

    @staticmethod
    def gaps(source: dict, known: dict, marked: dict, selection) -> list[dict]:
        result = []
        ordered = sorted(source['visits'], key = lambda visit: visit['entry_line'])

        for left, right in zip(ordered, ordered[1:]):
            selection.control.check()
            start, end = left.get('ended_at'), right.get('entered_at')
            bounds = selection.clip(start, end) if start and end else None

            if bounds is None and start and end and MapGapBuilder.moment(end) >= MapGapBuilder.moment(start):
                continue

            if bounds is None and selection.visit(left) is None and selection.visit(right) is None:
                continue

            gap = {'line': right['entry_line'], 'anchor': 'gap-' + str(right['entry_line']), 'known': False,
                   'from_href': LogHistoryBuilder.line_href(left['end_line']),
                   'to_href': LogHistoryBuilder.line_href(right['entry_line'])}
            result.append(gap)

            measured = known.get(right['entry_line'])

            if measured is None or measured['from_href'] != gap['from_href']:
                continue

            a, b = measured['started_at'], measured['ended_at']
            afk = []

            for row in marked[measured['session_id']]:
                selection.control.check()
                begin, finish = max(MapGapBuilder.moment(a), MapGapBuilder.moment(row['entered_at'])), min(MapGapBuilder.moment(b), MapGapBuilder.moment(row['ended_at']))

                if finish > begin:
                    afk.append({**row, 'entered_at': begin.isoformat(), 'ended_at': finish.isoformat(),
                                'seconds': (finish - begin).total_seconds()})

            gap.update(measured, known = True, afk = afk)

        return result

    @staticmethod
    def navigation(pages: list[dict], sources: dict, sessions) -> None:
        grouped = defaultdict(list)

        for page in pages:
            sessions.control.check()
            source = sources[page['line']]
            membership = {sessions.session(visit['entry_line']) for visit in source['visits']}

            if len(membership) != 1 or None in membership:
                continue

            first = next(iter(membership))

            if not sessions.rows[first]['branched']:
                grouped[first].append(page)

        for rows in grouped.values():
            rows.sort(key = lambda page: page['line'])

            for index, page in enumerate(rows):
                for field, position in (('previous', index - 1), ('next', index + 1)):
                    if 0 <= position < len(rows):
                        other = rows[position]
                        page[field] = {'name': other['name'], 'path': other['path']}
