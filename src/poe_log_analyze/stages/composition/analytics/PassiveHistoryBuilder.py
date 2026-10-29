from poe_log_analyze.stages.merging.SourceObservationEvidence import SourceObservationEvidence


class PassiveHistoryBuilder:
    """Recorded tree operations and GoldCost; infer neither a complete tree nor actual spending."""

    @classmethod
    def build(cls, index) -> dict:
        rows = index.selected(SourceObservationEvidence.TREE)
        nodes, days, sessions = {}, {}, {}

        for row in rows:
            index.selection.control.check()
            fields = row['fields']

            if row['code'] == 'passive.allocation':
                key = fields['skill_id'], fields['name']
                nodes.setdefault(key, []).append(row)

            for groups, key in ((days, row['date']), (sessions, row['session_id'])):
                groups.setdefault(key, []).append(row)

        return {'version': '1', 'rows': rows, 'summary': cls.counts(rows),
                'nodes': [{'skill_id': key[0], 'name': key[1], **cls.counts(records),
                           'evidence': [row['href'] for row in records]} for key, records in sorted(nodes.items())],
                'days': [{'key': key, **cls.counts(records)} for key, records in sorted(days.items())],
                'sessions': [{'key': key, 'href': records[0]['session_href'], **cls.counts(records)}
                             for key, records in sorted(sessions.items(), key = lambda pair: str(pair[0]))]}

    @staticmethod
    def counts(rows) -> dict:
        allocated = sum(row['code'] == 'passive.allocation' and row['fields']['operation'] == 'allocated' for row in rows)
        unallocated = sum(row['code'] == 'passive.allocation' and row['fields']['operation'] == 'unallocated' for row in rows)

        return {'count': len(rows), 'allocated': allocated, 'unallocated': unallocated, 'delta': allocated - unallocated,
                'masteries': sum(row['code'] == 'mastery.allocated' for row in rows),
                'gold_records': sum(row['code'] == 'settlers.gold_respec' for row in rows)}
