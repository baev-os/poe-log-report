from poe_log_analyze.runtime.AreaKind import AreaKind

from poe_log_analyze.stages.composition.analytics.MeasuredSpanIndex import MeasuredSpanIndex
from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder


class MapCycleBuilder:
    """Cycle between adjacent first entries, including measured time outside maps."""

    @classmethod
    def build(cls, runs, spans, details) -> dict:
        spans.selection.control.check()
        groups, unassigned = {}, 0

        for run in runs:
            spans.selection.control.check()

            if AreaKind.code(run) != 'map':
                continue

            first = spans.sessions.session(run['first_line'])

            if first is None:
                unassigned += spans.selection.period.contains(run.get('started_at'), spans.selection.zone_name)
            else:
                groups.setdefault(first, []).append(run)

        rows, skipped, open_cycles = [], 0, 0

        for first, maps in sorted(groups.items()):
            spans.selection.control.check()
            maps.sort(key = lambda run: run['first_line'])
            session = spans.sessions.rows[first]
            open_cycles += bool(maps and spans.selection.period.contains(maps[-1].get('started_at'), spans.selection.zone_name))

            if session['branched']:
                for current, following in zip(maps, maps[1:]):
                    spans.selection.control.check()
                    a, b = current.get('started_at'), following.get('started_at')
                    selected = (spans.selection.clip(a, b) is not None if a and b and spans.moment(b) >= spans.moment(a)
                                else spans.selection.period.contains(a, spans.selection.zone_name)
                                or spans.selection.period.contains(b, spans.selection.zone_name))
                    skipped += selected

                continue

            for current, following in zip(maps, maps[1:]):
                spans.selection.control.check()
                start, end = current.get('started_at'), following.get('started_at')

                if not start or not end or spans.moment(end) < spans.moment(start):
                    skipped += 1
                    continue

                span = spans.measure(first, start, end)

                if span is None:
                    continue

                excluded = []

                if not current.get('identity_complete') or not following.get('identity_complete'):
                    excluded.append('identity')

                if span['clipped']:
                    excluded.append('clipped')

                if not span['covered'] or span['overlapping']:
                    excluded.append('incomplete')

                rows.append({**span, 'line': current['first_line'], 'next_line': following['first_line'],
                             'name': current['name'], 'next_name': following['name'], 'area_id': current['area_id'],
                             'href': details['links'].get(str(current['first_line'])) or LogHistoryBuilder.line_href(current['first_line']),
                             'next_href': details['links'].get(str(following['first_line'])) or LogHistoryBuilder.line_href(following['first_line']),
                             'source_href': LogHistoryBuilder.line_href(current['first_line']),
                             'session_href': session['path'], 'session_id': str(first), 'excluded': excluded})

        rows.sort(key = lambda row: (spans.moment(row['started_at']), row['line']))

        return {'version': '1', 'rows': rows, 'summary': MeasuredSpanIndex.statistics(rows),
                'without_afk': MeasuredSpanIndex.statistics(rows, 'remaining_seconds'),
                'unassigned': unassigned, 'skipped_pairs': skipped, 'open_cycles': open_cycles}
