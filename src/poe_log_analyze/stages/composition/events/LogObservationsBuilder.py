from decimal import Decimal

from poe_log_analyze.runtime.DurationFormatter import DurationFormatter

from poe_log_analyze.stages.parsing.DiagnosticSummary import DiagnosticSummary
from poe_log_analyze.stages.composition.events.RecordedMessage import RecordedMessage


class LogObservationsBuilder:
    """Message counters and the complete remainder from the already merged registry."""

    def __init__(self):
        self.diagnostics = DiagnosticSummary()
        self.originals = {}
        self.loading_seconds = Decimal(0)
        self.loading_count = 0
        self.items_identified = 0
        self.identification_count = 0

    def add(self, row: dict) -> None:
        if row['status'] != 'recognized':
            previous = len(self.diagnostics.groups)
            self.diagnostics.add(row)

            if len(self.diagnostics.groups) != previous:
                self.originals[row['line_number']] = RecordedMessage.from_record(row)['original']

            return

        if row.get('record_id') != row['line_number']:
            return

        if row['type'] == 'loading.duration':
            self.loading_seconds += Decimal(row['fields']['seconds'])
            self.loading_count += 1
        elif row['type'] == 'screen.items_identified':
            self.items_identified += int(row['fields']['count'])
            self.identification_count += 1

    def result(self) -> dict:
        categories = {}

        for group in sorted(self.diagnostics.groups.values(), key = lambda item: (-item['count'], item['group_id'])):
            code = group['category']
            category = categories.setdefault(code, {'code': code, 'label': DiagnosticSummary.CATEGORIES[code],
                                                     'count': self.diagnostics.categories[code], 'messages': []})
            category['messages'].append({'text': self.originals[group['first_line']],
                                         'reason': group['reason'], 'status': group['status'],
                                         'count': group['count'], 'first_line': group['first_line'],
                                         'last_line': group['last_line']})

        fraction = format(self.loading_seconds % 1, 'f')[1:].rstrip('0')
        duration = DurationFormatter.duration_label(self.loading_seconds) + (fraction if fraction != '.' else '')

        return {'version': '1', 'diagnostics': [categories[key] for key in sorted(categories)],
                'loading_seconds': str(self.loading_seconds), 'loading_duration': duration,
                'loading_count': self.loading_count, 'items_identified': self.items_identified,
                'identification_count': self.identification_count}
