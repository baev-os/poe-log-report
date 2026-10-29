from decimal import Decimal, ROUND_HALF_UP

from poe_log_analyze.runtime.DurationFormatter import DurationFormatter


class ComparisonPresenter:
    """Shared labels and numeric comparison presentation for HTML and PDF."""

    def __init__(self, catalogue):
        self.catalogue = catalogue

    def present(self, model: dict) -> None:
        if not model['enabled']:
            return

        for side in ('a', 'b'):
            period = model[side]['period']
            period['label'] = self.catalogue.text('period.range', start = period['date_from'], end = period['date_to'])

        for section in model['sections']:
            section['title'] = self.catalogue.text('comparison.' + section['code'])

            for row in section['rows']:
                self.row(row)

                if section['code'] == 'zones':
                    row['label'] += ' · ' + self.catalogue.text('comparison.share' if row['kind'] == 'share' else 'comparison.time')

    def row(self, row: dict) -> None:
        row['label'] = self.catalogue.text(row['label_key'])

        for key in ('a', 'b', 'delta'):
            row[key + '_text'] = self.format(row[key], row['kind'], signed = key == 'delta')

        row['change_text'] = self.format(row['change_percent'], 'percent', signed = True)

    def format(self, value: float | None, kind: str, signed: bool = False) -> str:
        if value is None:
            return '—'

        rounded = Decimal(str(abs(value))).quantize(Decimal('.01'), rounding = ROUND_HALF_UP)
        sign = ('+' if value > 0 else '−') if signed and rounded else ''

        if kind == 'duration':
            fraction = format(rounded % 1, '.2f')[1:].rstrip('0').rstrip('.')
            text = DurationFormatter.duration_label(float(rounded)) + fraction
        else:
            text = format(rounded, '.2f').rstrip('0').rstrip('.')

        if self.catalogue.language == 'ru':
            text = text.replace('.', ',')

        if kind in ('share', 'percent'):
            text += ' ' + (self.catalogue.text('comparison.pp') if kind == 'share' and signed else '%')

        return sign + text
