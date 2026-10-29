import json

from datetime import datetime, timezone


class DisconnectReturnLinks:
    """Establish the next entry within each source before mixing branches."""

    KINDS = ('network.abnormal_disconnect', 'network.maintenance_disconnect', 'network.instance_disconnect')

    @classmethod
    def read(cls, source, mapping, source_id, control) -> list[dict]:
        pending, result, previous, last = [], [], None, 0

        with (source.directory / 'lines.jsonl').open('rb') as stream:
            for raw in stream:
                control.check()
                row = json.loads(raw)
                last = row['line_number']
                stamp = row.get('timestamp')
                moment = datetime.fromisoformat(stamp).astimezone(timezone.utc) if stamp else None

                if moment is not None and previous is not None and moment < previous:
                    for item in pending:
                        result.append(cls.close(item, last, mapping, source_id, 'clock'))

                    pending = []

                if moment is not None:
                    previous = moment

                if row['status'] != 'recognized':
                    continue

                if row['type'] == 'area.enter':
                    for item in pending:
                        result.append(cls.close(item, last, mapping, source_id,
                                                'observed' if item['timestamp'] and stamp else 'missing_time', row))

                    pending = []

                if row['type'] in cls.KINDS:
                    pending.append({'line': last, 'timestamp': stamp, 'kind': row['type']})

        for item in pending:
            result.append(cls.close(item, last, mapping, source_id, 'no_entry'))

        return result

    @staticmethod
    def close(item, last, mapping, source_id, state, entry = None) -> dict:
        return {**item, 'line': mapping[item['line']], 'state': state,
                'entry_line': mapping[entry['line_number']] if entry else None,
                'entered_at': entry.get('timestamp') if entry else None,
                'area': entry['fields']['area'] if entry else None,
                'origin': {'source': source_id, 'first_line': item['line'], 'last_line': last}}

    @staticmethod
    def merge(records, measurements) -> list[dict]:
        groups = {}

        for row in records:
            measurements.control.check()
            groups.setdefault(row['line'], []).append(row)

        return [row for copies in groups.values() for row in measurements.maximal(copies)]
