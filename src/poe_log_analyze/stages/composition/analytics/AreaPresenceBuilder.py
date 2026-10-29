from poe_log_analyze.stages.composition.analytics.MeasuredSpanIndex import MeasuredSpanIndex
from poe_log_analyze.stages.composition.analytics.ObservationLinks import ObservationLinks


class AreaPresenceBuilder:
    """Joined/left pairs describe client observations, not party membership or trade."""

    @classmethod
    def build(cls, index, spans) -> dict:
        signals = index.selected({'screen.area_presence'})
        rows = ObservationLinks.build('presence', index, spans, overlap = True)
        known = []

        for row in rows:
            index.selection.control.check()
            row['character'] = row['event']['fields']['character']
            span = row['choices'][0]['span'] if row['state'] == 'matched' else None
            excluded = [] if span is not None else ['incomplete']

            if span is not None and span['clipped']:
                excluded.append('clipped')

            row.update(seconds = span['elapsed_seconds'] if span else None, excluded = excluded)

            if span is not None:
                known.append(row)

        names = sorted({row['fields']['character'] for row in signals} | {row['character'] for row in rows})
        characters = []

        for name in names:
            index.selection.control.check()
            messages = [row for row in signals if row['fields']['character'] == name]
            intervals = [row for row in rows if row['character'] == name]
            characters.append({'name': name, 'joined': sum(row['fields']['action'] == 'joined' for row in messages),
                               'left': sum(row['fields']['action'] == 'left' for row in messages),
                               'matched': sum(row['state'] == 'matched' for row in intervals),
                               'unknown': sum(row['state'] != 'matched' for row in intervals),
                               'summary': MeasuredSpanIndex.statistics(intervals)})

        return {'version': '1', 'rows': rows, 'signals': signals, 'characters': characters,
                'joined_count': sum(row['fields']['action'] == 'joined' for row in signals),
                'left_count': sum(row['fields']['action'] == 'left' for row in signals),
                'matched_count': len(known), 'unknown_count': len(rows) - len(known),
                'summary': MeasuredSpanIndex.statistics(rows)}
