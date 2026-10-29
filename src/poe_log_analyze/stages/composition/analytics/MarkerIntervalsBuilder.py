from statistics import median

from poe_log_analyze.stages.composition.analytics.MeasuredSpanIndex import MeasuredSpanIndex


class MarkerIntervalsBuilder:
    """Gaps between maps with markers without estimating their true appearance probability."""

    @classmethod
    def build(cls, observations, explorer, spans) -> dict:
        spans.selection.control.check()
        sequences, skipped = cls.sequences(explorer, spans)
        groups = []

        for group in observations['groups']:
            spans.selection.control.check()
            members = {row['line'] for month in group['months'] for day in month['days'] for row in day['rows']}
            members.update(row['line'] for row in group['undated'])
            intervals, spells, observed_count = [], [], 0

            for first, maps in sequences:
                spans.selection.control.check()
                positions = [number for number, row in enumerate(maps) if row['line'] in members]
                observed_count += len(positions)

                for a, b in zip(positions, positions[1:]):
                    span = spans.measure(first, maps[a]['timestamp'], maps[b]['timestamp'])
                    excluded = []

                    if span is None or not span['covered'] or span['overlapping']:
                        excluded.append('incomplete')

                    if span is not None and span['clipped']:
                        excluded.append('clipped')

                    intervals.append({**(span or {'seconds': None, 'remaining_seconds': None}),
                                      'count': b - a - 1, 'excluded': excluded,
                                      'from_line': maps[a]['line'], 'to_line': maps[b]['line'],
                                      'from_href': cls.href(maps[a]), 'to_href': cls.href(maps[b]),
                                      'session_href': spans.sessions.rows[first]['path']})

                boundaries = [-1, *positions, len(maps)]

                for a, b in zip(boundaries, boundaries[1:]):
                    if b - a <= 1:
                        continue

                    spells.append({'count': b - a - 1, 'left_censored': a == -1, 'right_censored': b == len(maps),
                                   'first_href': cls.href(maps[a + 1]), 'last_href': cls.href(maps[b - 1]),
                                   'first_line': maps[a + 1]['line'], 'last_line': maps[b - 1]['line'],
                                   'session_href': spans.sessions.rows[first]['path']})

            groups.append({'code': group['code'], 'label_key': group['label_key'], 'observed_count': observed_count,
                           'all_observed_count': group['count'], 'intervals': intervals, 'spells': spells,
                           'median_maps': median(row['count'] for row in intervals) if intervals else None,
                           'max_maps': max((row['count'] for row in intervals), default = None),
                           'longest_observed': max((row['count'] for row in spells), default = 0),
                           'summary': MeasuredSpanIndex.statistics(intervals),
                           'without_afk': MeasuredSpanIndex.statistics(intervals, 'remaining_seconds')})

        return {'version': '1', 'groups': groups, 'skipped_maps': skipped, 'sequence_count': len(sequences)}

    @staticmethod
    def href(row) -> str:
        return f"maps/runs/{row['line']}/index.html"

    @staticmethod
    def sequences(explorer, spans) -> tuple[list, int]:
        grouped, sequences, skipped = {}, [], 0

        for row in explorer['rows']:
            spans.selection.control.check()

            if not row['new']:
                continue

            first = int(row['session_id']) if row['session_id'] is not None else None

            if first is None or not row['timestamp'] or spans.sessions.rows[first]['branched']:
                skipped += 1
                continue

            grouped.setdefault(first, []).append(row)

        for first, rows in grouped.items():
            current = []

            for row in sorted(rows, key = lambda item: item['line']):
                if 'identity' in row['excluded'] or 'branched' in row['excluded']:
                    skipped += 1

                    if current:
                        sequences.append((first, current))

                    current = []
                else:
                    current.append(row)

            if current:
                sequences.append((first, current))

        return sequences, skipped
