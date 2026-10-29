from poe_log_analyze.stages.merging.SourceObservationEvidence import SourceObservationEvidence


class FilterHistoryBuilder:
    """Saving, successful activation, and hash announcements remain separate events."""

    @classmethod
    def build(cls, index) -> dict:
        index.selection.control.check()
        events = {row['line']: row for row in index.evidence['events'] if row['code'] in SourceObservationEvidence.FILTERS}
        rows = index.selected(SourceObservationEvidence.FILTERS)
        groups = {}

        for row in rows:
            index.selection.control.check()
            previous = events.get(row.get('previous_filter_line'))
            row['previous'] = index.record(previous) if previous else None
            success = row['code'] == 'filter.saved' or row['code'] == 'filter.reloaded' and row['fields']['result'] == 'true'
            row['change'] = ('first' if previous is None else 'same' if previous['fields']['hash'] == row['fields']['hash'] else 'changed') if success else 'unconfirmed'
            row['failed'] = row['code'] == 'filter.reloaded' and row['fields']['result'] == 'false'

            for dimension, key in (('filter', row['fields'].get('filter_id')), ('date', row['date']), ('session', row['session_id'])):
                groups.setdefault((dimension, str(key or '')), []).append(row)

        return {'version': '1', 'rows': rows, 'summary': cls.counts(rows), 'groups': [
            {'dimension': dimension, 'key': key, **cls.counts(records), 'evidence': [row['href'] for row in records]}
            for (dimension, key), records in sorted(groups.items())]}

    @staticmethod
    def counts(rows):
        statuses = sorted({row['fields']['status'] for row in rows if 'status' in row['fields']})
        return {'count': len(rows), 'failed': sum(row['failed'] for row in rows),
                'saved': sum(row['code'] == 'filter.saved' for row in rows),
                'reloaded': sum(row['code'] == 'filter.reloaded' and not row['failed'] for row in rows),
                'changes': sum(row['change'] == 'changed' for row in rows),
                'same': sum(row['change'] == 'same' for row in rows),
                'statuses': [{'status': status, 'count': sum(row['fields'].get('status') == status for row in rows)} for status in statuses]}
