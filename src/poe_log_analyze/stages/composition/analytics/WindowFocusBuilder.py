from datetime import datetime

from poe_log_analyze.stages.composition.AfkMeasurements import AfkMeasurements
from poe_log_analyze.stages.composition.MapPaceBuilder import MapPaceBuilder
from poe_log_analyze.stages.composition.analytics.MeasuredSpanIndex import MeasuredSpanIndex
from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder


class WindowFocusBuilder:
    """Focus loss is independent of AFK; exact duration requires a message pair."""

    @classmethod
    def build(cls, evidence, spans) -> dict:
        spans.selection.control.check()
        grouped, rows, totals, bounded = {}, [], [], []

        for item in evidence['focus']:
            spans.selection.control.check()
            grouped.setdefault(item['line'], []).append(item)

        for line, candidates in sorted(grouped.items()):
            spans.selection.control.check()
            choices = {}

            for item in candidates:
                first = spans.sessions.session(line)
                span = (spans.measure(first, item['timestamp'], item['ended_at'])
                        if item['state'] == 'matched' else None)

                if span is None and not spans.selection.period.contains(item['timestamp'], spans.selection.zone_name):
                    continue

                excluded = [] if item['state'] == 'matched' and span is not None else ['incomplete']

                if span is not None and (not span['covered'] or span['overlapping']):
                    excluded.append('incomplete')

                if span is not None and span['clipped']:
                    excluded.append('clipped')

                choices[(item['end_line'], item['state'])] = {
                    **(span or AfkMeasurements.balance(None, None)), 'state': item['state'],
                    'end_href': LogHistoryBuilder.line_href(item['end_line']), 'excluded': list(dict.fromkeys(excluded))}

            options = list(choices.values())

            if not options:
                continue

            ambiguous = len(options) > 1
            first = spans.sessions.session(line)

            if not ambiguous and options[0]['state'] == 'matched':
                bounded.append({**options[0], 'excluded': ['clipped'] if options[0].get('clipped') else []})

            if (not ambiguous and options[0]['state'] == 'matched' and first is not None
                    and options[0].get('covered') and not options[0].get('overlapping')):
                totals.append(options[0])

            stamp = candidates[0]['timestamp']
            rows.append({'line': line, 'href': LogHistoryBuilder.line_href(line),
                         'time': cls.label(stamp, spans), 'state': 'ambiguous' if ambiguous else options[0]['state'],
                         'session_href': spans.sessions.rows[first]['path'] if first is not None else None,
                         'choices': options})

        signals = [item for item in evidence['events'] if item['code'] == 'window.focus'
                   and spans.selection.period.contains(item['timestamp'], spans.selection.zone_name)]
        zones = {}

        for row in totals:
            for zone in row['zones']:
                zones[zone['kind']] = zones.get(zone['kind'], 0) + zone['seconds']

        return {'version': '1', 'rows': rows, 'signals': {state: sum(item['fields']['state'] == state for item in signals)
                                                       for state in ('Lost', 'Gained')},
                'summary': MeasuredSpanIndex.statistics(totals), 'balance': AfkMeasurements.combine(totals),
                'elapsed_summary': MeasuredSpanIndex.statistics(bounded, 'elapsed_seconds'),
                'elapsed_seconds': sum(row['elapsed_seconds'] for row in bounded),
                'elapsed_duration': MapPaceBuilder.duration(sum(row['elapsed_seconds'] for row in bounded)),
                'ambiguous': sum(row['state'] == 'ambiguous' for row in rows),
                'unknown': sum(row['state'] != 'matched' for row in rows),
                'zones': [{'kind': kind, 'seconds': seconds, 'duration': MapPaceBuilder.duration(seconds)} for kind, seconds in sorted(zones.items())]}

    @staticmethod
    def label(stamp, spans) -> str | None:
        return datetime.fromisoformat(stamp).astimezone(spans.selection.zone).strftime('%d.%m.%Y %H:%M:%S %z') if stamp else None
