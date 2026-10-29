from datetime import datetime

from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder


class ObservationLinks:
    """Present source alternatives while retaining open boundaries and period context."""

    @staticmethod
    def build(kind, index, spans, *, overlap = False) -> list[dict]:
        index.selection.control.check()
        events = {row['line']: row for row in index.evidence['events']}
        groups, rows = {}, []

        for item in index.evidence['links']:
            index.selection.control.check()

            if item['kind'] == kind:
                groups.setdefault(item['line'], []).append(item)

        for line, candidates in sorted(groups.items()):
            index.selection.control.check()
            choices = {}
            event = index.record(events[line])
            first = index.sessions.session(line)

            for item in candidates:
                span = (spans.measure(first, item['timestamp'], item['ended_at'])
                        if item['state'] == 'matched' else None)
                selected = index.selection.period.contains(item['timestamp'], index.selection.zone_name)

                if not selected and not (overlap and span is not None):
                    continue

                stamp = item.get('ended_at')
                end = index.record(events[item['end_line']]) if item['end_line'] in events else None
                choices[(item['end_line'], item['state'])] = {
                    'state': item['state'], 'end_line': item['end_line'], 'end_href': LogHistoryBuilder.line_href(item['end_line']),
                    'end_time': datetime.fromisoformat(stamp).astimezone(index.selection.zone).strftime('%d.%m.%Y %H:%M:%S %z') if stamp else None,
                    'end_outside': bool(stamp and not index.selection.period.contains(stamp, index.selection.zone_name)),
                    'end': end, 'span': span}

            if not choices:
                continue

            options = list(choices.values())
            ambiguous = len(options) > 1 or any(option['state'] == 'ambiguous' for option in options)
            rows.append({'line': line, 'event': event, 'choices': options,
                         'state': 'ambiguous' if ambiguous else options[0]['state']})

        return rows
