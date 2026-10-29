from datetime import datetime

from poe_log_analyze.runtime.AreaKind import AreaKind

from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder


class RecordedActivityIndex:
    """Context comes from the original area entry rather than matching timestamps."""

    def __init__(self, evidence, runs, details, sessions, selection) -> None:
        selection.control.check()
        self.evidence, self.sessions, self.selection = evidence, sessions, selection
        self.contexts = {}

        for run in runs:
            selection.control.check()
            levels = {visit.get('level') for visit in run['visits']}
            level = int(next(iter(levels))) if len(levels) == 1 and None not in levels else None

            for visit in run['visits']:
                self.contexts[visit['entry_line']] = {
                    'run_line': run['first_line'], 'visit_line': visit['entry_line'], 'name': run['name'],
                    'area_id': run['area_id'], 'kind': AreaKind.code(run), 'level': level,
                    'identity_complete': bool(run.get('identity_complete')),
                    'branched': bool(run.get('branched') or visit.get('branches')),
                    'href': details['links'].get(str(visit['entry_line'])) or LogHistoryBuilder.line_href(visit['entry_line'])}

    def selected(self, codes) -> list[dict]:
        self.selection.control.check()
        result = []

        for row in self.evidence['events']:
            self.selection.control.check()

            if row['code'] not in codes or not self.selection.period.contains(row['timestamp'], self.selection.zone_name):
                continue

            result.append(self.record(row))

        return result

    def record(self, row) -> dict:
        stamp = row['timestamp']
        moment = datetime.fromisoformat(stamp).astimezone(self.selection.zone) if stamp else None
        first = self.sessions.session(row['line'])
        context = self.contexts.get(row['entry_line'])

        return {**row, 'fields': dict(row['fields']), 'context': dict(context) if context else None,
                'href': LogHistoryBuilder.line_href(row['line']), 'session_id': str(first) if first is not None else None,
                'session_href': self.sessions.rows[first]['path'] if first is not None else None,
                'date': moment.date().isoformat() if moment else 'undated',
                'time': moment.strftime('%d.%m.%Y %H:%M:%S %z') if moment else None}
