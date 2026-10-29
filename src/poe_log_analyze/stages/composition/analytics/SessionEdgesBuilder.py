from poe_log_analyze.runtime.AreaKind import AreaKind

from poe_log_analyze.stages.composition.analytics.MeasuredSpanIndex import MeasuredSpanIndex
from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder


class SessionEdgesBuilder:
    """Measured spans before the first and after the last map visit."""

    @classmethod
    def build(cls, original, spans) -> dict:
        spans.selection.control.check()
        maps = {}

        for run in original:
            if AreaKind.code(run) != 'map':
                continue

            for visit in run['visits']:
                spans.selection.control.check()
                first = spans.sessions.session(visit['entry_line'])
                maps.setdefault(first, []).append(visit)

        rows, leading, trailing, without_maps = [], [], [], []

        for first, session in sorted(spans.sessions.rows.items()):
            spans.selection.control.check()
            visits = sorted(maps.get(first, []), key = lambda visit: visit['entry_line'])
            row = {'id': str(first), 'href': session['path'], 'start': session.get('start'),
                   'map_visits': len(visits), 'state': 'branched' if session['branched'] else 'measured',
                   'leading': None, 'trailing': None, 'without_maps': None,
                   'first_map_href': LogHistoryBuilder.line_href(visits[0]['entry_line']) if visits else None,
                   'last_map_href': LogHistoryBuilder.line_href(visits[-1]['entry_line']) if visits else None}

            if session['branched']:
                rows.append(row)
                continue

            branch = session['branches'][0]
            start, end = branch['started_at'], branch['ended_at']

            if not visits:
                row['state'] = 'no_maps'
                row['without_maps'] = cls.edge(spans, first, start, end, not branch.get('incomplete', True))

                if row['without_maps'] is not None:
                    without_maps.append(row['without_maps'])
            else:
                row['leading'] = cls.edge(spans, first, start, visits[0].get('entered_at'), True)
                last = visits[-1]
                row['trailing'] = cls.edge(spans, first, last.get('ended_at') if last['bounded'] else None,
                                           end, not branch.get('incomplete', True))

                if row['leading'] is not None:
                    leading.append(row['leading'])

                if row['trailing'] is not None:
                    trailing.append(row['trailing'])

            rows.append(row)

        return {'version': '1', 'rows': rows, 'no_map_sessions': sum(row['state'] == 'no_maps' for row in rows),
                'branched_sessions': sum(row['state'] == 'branched' for row in rows),
                'leading': MeasuredSpanIndex.statistics(leading), 'trailing': MeasuredSpanIndex.statistics(trailing),
                'without_maps': MeasuredSpanIndex.statistics(without_maps)}

    @staticmethod
    def edge(spans, first, start, end, complete) -> dict | None:
        if not start or not end or spans.moment(end) < spans.moment(start):
            return None

        span = spans.measure(first, start, end)

        if span is None:
            return None

        excluded = []

        if not complete or not span['covered'] or span['overlapping']:
            excluded.append('incomplete')

        if span['clipped']:
            excluded.append('clipped')

        return {**span, 'excluded': excluded}
