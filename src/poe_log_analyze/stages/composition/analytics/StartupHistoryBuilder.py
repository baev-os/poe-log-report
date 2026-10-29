from decimal import Decimal

from poe_log_analyze.stages.composition.analytics.MeasuredSpanIndex import MeasuredSpanIndex
from poe_log_analyze.stages.composition.analytics.ObservationLinks import ObservationLinks
from poe_log_analyze.stages.composition.analytics.ObservationSamples import ObservationSamples


class StartupHistoryBuilder:
    """Recorded stages are separate from the interval between first marker and area entry."""

    @classmethod
    def build(cls, index, spans) -> dict:
        signals = index.selected({'startup.stage_start', 'startup.stage_duration', 'engine.lifecycle'})
        groups = {}

        for event in signals:
            index.selection.control.check()

            if event['code'] == 'startup.stage_duration':
                groups.setdefault(event['fields']['stage'], []).append(event)

        rows = ObservationLinks.build('startup', index, spans)

        for row in rows:
            index.selection.control.check()
            choice = row['choices'][0] if row['state'] == 'matched' else None
            start, end = row['event']['timestamp'], choice['end']['timestamp'] if choice and choice['end'] else None
            row['seconds'] = (spans.moment(end) - spans.moment(start)).total_seconds() if start and end else None
            row['excluded'] = [] if row['seconds'] is not None else ['incomplete']

            if start and end:
                bounds = index.selection.clip(start, end)

                if bounds is None or bounds[2] != row['seconds']:
                    row['excluded'].append('clipped')

        return {'version': '1', 'rows': rows, 'signals': signals,
                'summary': MeasuredSpanIndex.statistics(rows),
                'slowest': sorted((row for row in rows if not row['excluded']),
                                  key = lambda row: (-row['seconds'], row['line']))[:10],
                'stages': [{'stage': stage, 'stats': ObservationSamples.build(
                    float(Decimal(event['fields']['seconds'])) for event in events),
                    'evidence': [event['href'] for event in events]} for stage, events in sorted(groups.items())]}
