from poe_log_analyze.stages.composition.analytics.ObservationSamples import ObservationSamples
from poe_log_analyze.stages.merging.SourceObservationEvidence import SourceObservationEvidence


class NetworkHealthBuilder:
    """Connection time is not continuous ping; resync values have no stated unit."""

    @classmethod
    def build(cls, index) -> dict:
        rows = index.selected(SourceObservationEvidence.NETWORK)
        samples = [row for row in rows if 'milliseconds' in row['fields']]

        for row in samples:
            row['milliseconds'] = int(row['fields']['milliseconds'])

        return {'version': '1', 'rows': rows, 'sample_count': len(samples),
                'resync_count': sum(row['code'] == 'network.resync' for row in rows),
                'disconnect_count': sum(row['code'].endswith('disconnect') for row in rows),
                'unknown_context': sum(row['context'] is None for row in rows),
                'summaries': cls.groups(rows, 'code', index), 'days': cls.groups(rows, 'date', index),
                'sessions': cls.groups(rows, 'session_id', index), 'areas': cls.groups(rows, 'area', index)}

    @staticmethod
    def groups(rows, field, index) -> list[dict]:
        groups = {}

        for row in rows:
            index.selection.control.check()
            context = row['context']
            key = ((context['area_id'], context['name']) if context else None) if field == 'area' else row[field]
            groups.setdefault((key, row['code']), []).append(row)

        result = []

        for (key, code), records in groups.items():
            index.selection.control.check()
            row = records[0]
            label = key[1] if field == 'area' and key else key
            result.append({'key': label, 'code': code, 'count': len(records),
                           'stats': ObservationSamples.build(item.get('milliseconds') for item in records),
                           'href': row['context']['href'] if field == 'area' and row['context'] else
                           row['session_href'] if field == 'session_id' else row['href']})

        return sorted(result, key = lambda row: (str(row['key']), row['code']))
