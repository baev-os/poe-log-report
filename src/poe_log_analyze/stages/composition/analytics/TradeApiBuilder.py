from poe_log_analyze.stages.composition.analytics.ObservationLinks import ObservationLinks
from poe_log_analyze.stages.composition.analytics.ObservationSamples import ObservationSamples


class TradeApiBuilder:
    """ETrade responses and codes do not substitute for confirmed player trades."""

    @classmethod
    def build(cls, index, spans) -> dict:
        signals = index.selected({'etrade.request', 'etrade.response'})
        rows = ObservationLinks.build('api', index, spans)
        samples, groups, errors = [], {}, {}

        for row in rows:
            index.selection.control.check()
            event = row['event']
            row['api_type'] = event['fields'].get('api_type')

            for choice in row['choices']:
                end = choice['end']
                choice['milliseconds'] = int(end['fields']['milliseconds']) if end and end['code'] == 'etrade.response' else None
                choice['error'] = end['fields'].get('error') if end and end['code'] == 'etrade.response' else None

            if row['state'] == 'matched':
                choice = row['choices'][0]
                sample = {'api_type': row['api_type'], 'date': event['date'], 'milliseconds': choice['milliseconds']}
                samples.append(sample)

                for dimension in ('api_type', 'date'):
                    groups.setdefault((dimension, sample[dimension]), []).append(sample['milliseconds'])

        for event in signals:
            if event['code'] == 'etrade.response':
                code = event['fields']['error']
                errors[code] = errors.get(code, 0) + 1

        return {'version': '1', 'rows': rows, 'signals': signals,
                'request_count': sum(row['code'] == 'etrade.request' for row in signals),
                'response_count': sum(row['code'] == 'etrade.response' for row in signals),
                'matched_count': len(samples), 'unknown_count': sum(row['state'] != 'matched' for row in rows),
                'summary': ObservationSamples.build(row['milliseconds'] for row in samples),
                'groups': [{'dimension': dimension, 'key': key, 'stats': ObservationSamples.build(values)}
                           for (dimension, key), values in sorted(groups.items())],
                'codes': [{'code': code, 'count': count} for code, count in sorted(errors.items())]}
