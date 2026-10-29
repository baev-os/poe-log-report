from poe_log_analyze.stages.composition.analytics.MeasuredSpanIndex import MeasuredSpanIndex
from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder
from poe_log_analyze.stages.merging.SourceFaultIntervals import SourceFaultIntervals

from datetime import datetime


class FaultIntervalsBuilder:
    """Intervals between messages, not estimates of client crash probability."""

    @classmethod
    def build(cls, index, source_spans) -> dict:
        index.selection.control.check()
        events = {row['line']: row for row in index.evidence['events'] if row['code'] == 'area.enter'}
        groups, rows = {}, []

        for item in index.evidence.get('fault_intervals', []):
            index.selection.control.check()
            span = source_spans.measure(item['origin'], item['timestamp'], item['ended_at'])

            if span is None:
                continue

            entries = [index.record(events[line]) for line in item['entry_lines'] if line in events]
            selected = [row for row in entries if index.selection.period.contains(row['timestamp'], index.selection.zone_name)]
            new = [row for row in selected if row['context'] and row['context']['kind'] == 'map' and
                   row['context']['run_line'] == row['line'] and row['context']['identity_complete']]
            choice = {**item, 'span': span, 'new_maps': len({row['line'] for row in new}),
                      'start_time': datetime.fromisoformat(item['timestamp']).astimezone(index.selection.zone).strftime('%d.%m.%Y %H:%M:%S %z'),
                      'end_time': datetime.fromisoformat(item['ended_at']).astimezone(index.selection.zone).strftime('%d.%m.%Y %H:%M:%S %z'),
                      'unknown_entries': sum(row['context'] is None or not row['context']['identity_complete'] for row in selected),
                      'start_href': LogHistoryBuilder.line_href(item['line']),
                      'end_href': LogHistoryBuilder.line_href(item['end_line'])}
            groups.setdefault((item['category'], item['line']), {})[(item['end_line'], item['left_censored'], item['right_censored'])] = choice

        for (category, line), options in sorted(groups.items()):
            choices = list(options.values())
            ambiguous = len(choices) > 1
            choice = choices[0]
            censored = choice['left_censored'] or choice['right_censored']
            excluded = ['incomplete'] if censored or ambiguous else []

            if choice['span']['clipped']:
                excluded.append('clipped')

            measured_excluded = list(excluded)

            if not choice['span']['covered'] or choice['span']['overlapping']:
                measured_excluded.append('incomplete')

            rows.append({'line': line, 'category': category, 'choices': choices, 'ambiguous': ambiguous,
                         'branched': ambiguous, 'clipped': any(option['span']['clipped'] for option in choices),
                         'seconds': choice['span']['seconds'] if not ambiguous else None,
                         'remaining_seconds': choice['span']['remaining_seconds'] if not ambiguous else None,
                         'elapsed_seconds': choice['span']['elapsed_seconds'] if not ambiguous else None,
                         'new_maps': choice['new_maps'] if not ambiguous else None,
                         'excluded': sorted(set(measured_excluded)), 'calendar_excluded': excluded,
                         'href': choice['start_href']})

        return {'version': '1', 'rows': rows, 'categories': [
            {'category': category, 'count': sum(row['category'] == category for row in rows),
             'summary': MeasuredSpanIndex.statistics([row for row in rows if row['category'] == category]),
             'without_afk': MeasuredSpanIndex.statistics([row for row in rows if row['category'] == category], 'remaining_seconds'),
             'calendar': MeasuredSpanIndex.statistics([{**row, 'excluded': row['calendar_excluded']}
                          for row in rows if row['category'] == category], 'elapsed_seconds')}
            for category in SourceFaultIntervals.CATEGORIES]}
