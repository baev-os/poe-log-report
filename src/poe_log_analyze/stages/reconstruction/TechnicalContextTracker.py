from collections import deque
from datetime import datetime

from poe_log_analyze.stages.parsing.TechnicalIssueClassifier import TechnicalIssueClassifier


class TechnicalContextTracker:
    """Area and neighboring loading events for a technical message within one source."""

    WINDOW = 60

    def __init__(self, boundaries: set[str], max_gap_seconds: int, control):
        self.boundaries, self.max_gap_seconds, self.control = boundaries, max_gap_seconds, control
        self.previous = None
        self.rows = []
        self.reset()

    def reset(self) -> None:
        self.area = self.load = self.last_issue = None
        self.pending = deque()

    @staticmethod
    def moment(stamp: str | None) -> float | None:
        return datetime.fromisoformat(stamp).timestamp() if stamp else None

    def add(self, row: dict) -> None:
        self.control.check()
        moment = self.moment(row.get('timestamp'))

        if moment is not None:
            if self.previous is not None and (moment < self.previous or moment - self.previous > self.max_gap_seconds):
                self.reset()

            self.previous = moment

            while self.pending and moment - self.pending[0]['moment'] > self.WINDOW:
                self.pending.popleft()

        if row.get('record_id') not in (None, row['line_number']):
            return

        kind = row['type']
        critical = kind in self.boundaries or kind in ('area.enter', 'area.generate', 'network.instance_connect')

        if critical and (moment is None or row['status'] != 'recognized'):
            self.reset()
        elif kind in ('area.generate', 'network.instance_connect'):
            self.area = self.last_issue = None
        elif kind == 'area.enter':
            self.area = {'name': row['fields']['area'], 'line': row['line_number']}
            self.last_issue = None

        if kind == 'loading.duration' and row['status'] == 'recognized' and moment is not None:
            load = {'line': row['line_number'], 'timestamp': row['timestamp'], **row['fields']}

            for issue in self.pending:
                self.control.check()
                candidate = self.candidate(load, issue['moment'])
                earlier = issue['loading']

                if earlier is None or abs(candidate['delta_seconds']) < abs(earlier['delta_seconds']):
                    issue['loading'] = candidate

            self.pending.clear()
            self.load = load

        if TechnicalIssueClassifier.category(row) is not None:
            predecessor = self.last_issue
            previous_line = (predecessor['line'] if predecessor and moment is not None
                             and 0 <= moment - predecessor['moment'] <= self.WINDOW else None)
            load = self.candidate(self.load, moment) if self.load and moment is not None else None

            if load is not None and abs(load['delta_seconds']) > self.WINDOW:
                load = None

            issue = {'line': row['line_number'], 'previous_line': previous_line, 'moment': moment,
                     'area': dict(self.area) if self.area and moment is not None else None, 'loading': load}
            self.rows.append(issue)
            self.last_issue = issue if moment is not None else None

            if moment is not None:
                self.pending.append(issue)

        if kind in self.boundaries:
            self.reset()

    @classmethod
    def candidate(cls, load: dict, moment: float) -> dict:
        return {**load, 'delta_seconds': cls.moment(load['timestamp']) - moment}
