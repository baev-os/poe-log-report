from poe_log_analyze.stages.merging.SourceObservationEvidence import SourceObservationEvidence


class AcquisitionHistoryBuilder:
    """Quantities come only from explicit messages; different artifact types are not summed."""

    @classmethod
    def build(cls, index) -> dict:
        rows = index.selected(SourceObservationEvidence.ACQUISITIONS)
        groups = {}

        for row in rows:
            index.selection.control.check()

            row['quantity'] = 1 if row['code'] == 'screen.card_drawn' else int(row['fields']['count']) if 'count' in row['fields'] else None
            subject = row['fields'].get('artifact', row['fields'].get('card', ''))
            context = row['context']

            for dimension, key in (('all', ''), ('date', row['date']), ('session', row['session_id']),
                                   ('map', context['run_line'] if context and context['kind'] == 'map' else
                                    'outside' if context else None)):
                groups.setdefault((dimension, str(key or ''), row['code'], subject), []).append(row)

        cards = [row for row in rows if row['code'] == 'screen.card_drawn']
        names = sorted({row['fields']['card'] for row in cards})

        return {
            'version': '2',
            'rows': rows,
            'card_count': len(cards),
            'unique_cards': len(names),
            'repeated_cards': len(cards) - len(names),

            'cards': [
                {
                    'name': name,
                    'count': sum(row['fields']['card'] == name for row in cards),
                    'share': sum(row['fields']['card'] == name for row in cards) * 100 / len(cards),
                    'evidence': [row['href'] for row in cards if row['fields']['card'] == name]
                }
                for name in names
            ],

            'groups': [
                {
                    'dimension': dimension,
                    'key': key,
                    'code': code,
                    'subject': subject,
                    'artifact': subject if code == 'screen.expedition_added' else '',
                    'card': subject if code == 'screen.card_drawn' else '',
                    'messages': len(records),
                    'quantity': sum(row['quantity'] for row in records) if all(row['quantity'] is not None for row in records) else None,
                    'evidence': [row['href'] for row in records]
                }
                for (dimension, key, code, subject), records in sorted(groups.items())
            ]
        }
