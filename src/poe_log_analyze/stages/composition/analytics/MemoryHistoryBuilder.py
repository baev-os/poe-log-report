from datetime import datetime
from decimal import Decimal

from poe_log_analyze.stages.composition.analytics.ObservationSamples import ObservationSamples


class MemoryHistoryBuilder:
    """Memory snapshots retain original units; values between records are not interpolated."""

    FIELDS = (('used', 'used_unit'), ('os_used', 'os_unit'), ('total', 'total_unit'))

    @classmethod
    def build(cls, index) -> dict:
        events = {row['line']: row for row in index.evidence['events']}
        rows = index.selected({'memory.usage'})
        groups = {}

        for row in rows:
            index.selection.control.check()
            previous = events.get(row.get('previous_memory_line'))
            row['previous'] = index.record(previous) if previous else None
            row['values'], row['changes'] = {}, {}

            for field, unit in cls.FIELDS:
                value = row['fields'][field]
                row['values'][field] = float(Decimal(value))
                row['changes'][field] = (float(Decimal(value) - Decimal(previous['fields'][field]))
                                         if previous and previous['fields'][unit] == row['fields'][unit] else None)

                for dimension, key in (('all', ''), ('date', row['date']), ('session', row['session_id']),
                                       ('area', row['context']['area_id'] if row['context'] else None)):
                    groups.setdefault((dimension, str(key or ''), field, row['fields'][unit]), []).append(row)

        return {'version': '1', 'rows': rows, 'plots': cls.plots(rows, index), 'groups': [
            {'dimension': dimension, 'key': key, 'field': field, 'unit': unit,
             'stats': ObservationSamples.build(row['values'][field] for row in records),
             'evidence': [row['href'] for row in records]}
            for (dimension, key, field, unit), records in sorted(groups.items())]}

    @classmethod
    def plots(cls, rows, index) -> list[dict]:
        plots = []

        for field, unit in cls.FIELDS:
            for label in sorted({row['fields'][unit] for row in rows}):
                index.selection.control.check()
                records = [row for row in rows if row['timestamp'] and row['fields'][unit] == label]

                if not records:
                    continue

                stamps = [datetime.fromisoformat(row['timestamp']).timestamp() for row in records]
                left, right = min(stamps), max(stamps)
                maximum = max(row['values'][field] for row in records)
                plots.append({'field': field, 'unit': label, 'maximum': maximum,
                              'first_time': min(records, key = lambda row: datetime.fromisoformat(row['timestamp']))['time'],
                              'last_time': max(records, key = lambda row: datetime.fromisoformat(row['timestamp']))['time'],
                              'points': [{'x': 45 + (stamp - left) * 580 / (right - left) if right > left else 335,
                                          'y': 160 - row['values'][field] * 125 / maximum if maximum else 160,
                                          'value': row['fields'][field], 'time': row['time'], 'href': row['href']}
                                         for row, stamp in zip(records, stamps)]})

        return plots
