from datetime import datetime, timezone
from decimal import Decimal


class LoadingRouteTracker:
    """Link loading to entry within one source file before merging branches."""

    def __init__(self, boundaries: set[str], max_gap_seconds: int, control):
        self.boundaries, self.max_gap_seconds, self.control = boundaries, max_gap_seconds, control
        self.previous = self.current = self.pending = None
        self.rows = []

    def reset(self) -> None:
        self.current = self.pending = None

    def add(self, row: dict) -> None:
        self.control.check()
        stamp = row.get('timestamp')
        moment = datetime.fromisoformat(stamp).astimezone(timezone.utc) if stamp else None

        if moment is not None:
            if self.previous is not None and (moment < self.previous
                    or (moment - self.previous).total_seconds() > self.max_gap_seconds):
                self.reset()

            self.previous = moment

        if row.get('record_id') != row['line_number']:
            return

        kind = row['type']
        critical = kind in self.boundaries or kind in ('area.enter', 'area.generate', 'network.instance_connect')

        if critical and (moment is None or row['status'] != 'recognized'):
            self.reset()
            return

        if row['status'] != 'recognized':
            return

        if kind in self.boundaries:
            self.reset()
        elif kind in ('area.generate', 'network.instance_connect'):
            self.pending = None
        elif kind == 'area.enter':
            area = {'name': row['fields']['area'], 'line': row['line_number'], 'moment': moment}
            self.pending = {'source': self.current, 'target': area}
            self.current = area
        elif kind == 'loading.duration':
            self.loading(row, moment)

    def loading(self, row: dict, moment: datetime | None) -> None:
        target = row['fields']['area']
        pending, self.pending = self.pending, None
        reason = 'no_entry'
        source = entry = None

        if moment is None:
            reason = 'missing_time'
        elif pending is not None:
            age = Decimal(str((moment - pending['target']['moment']).total_seconds()))

            if pending['target']['name'] != target:
                reason = 'different_area'
            elif not 0 <= age <= Decimal(row['fields']['seconds']) + 1:
                # Client.txt timestamps have one-second precision; do not infer long delays.
                reason = 'outside_loading'
            else:
                source, entry = pending['source'], pending['target']
                reason = 'matched' if source is not None else 'unknown_source'

        if entry is None:
            self.current = None

        self.rows.append({'line': row['line_number'], 'from_area': source['name'] if source else None,
                          'from_line': source['line'] if source else None, 'to_area': target,
                          'to_line': entry['line'] if entry else None, 'reason': reason})
