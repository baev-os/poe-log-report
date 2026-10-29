from datetime import datetime, timezone

from poe_log_analyze.stages.parsing.TechnicalIssueClassifier import TechnicalIssueClassifier
from poe_log_analyze.stages.reconstruction.MapActivityBuilder import MapActivityBuilder


class SourceFaultIntervals:
    """Original observation intervals whose boundaries retain censoring."""

    CATEGORIES = ('disconnect', 'client', 'warning', 'crash')
    DISCONNECTS = {'network.abnormal_disconnect', 'network.maintenance_disconnect', 'network.instance_disconnect'}

    def __init__(self, mapping, source_id, control):
        self.mapping, self.source_id, self.control = mapping, source_id, control
        self.rows, self.pending = [], {}
        self.last = self.pid = self.tick = None

    def add(self, row):
        self.control.check()
        stamp, line, code = row.get('timestamp'), row['line_number'], row['type']
        header = row.get('header') or {}
        pid, tick = header.get('pid'), int(header['tick']) if 'tick' in header else None
        moment = datetime.fromisoformat(stamp).astimezone(timezone.utc) if stamp else None
        own = row.get('record_id') == line
        boundary = own and (code in ('log.open', 'game.closing') or
                            code == 'engine.lifecycle' and row['fields'].get('stage') == 'Init')
        broken = (pid is not None and self.pid is not None and pid != self.pid or
                  tick is not None and self.tick is not None and tick < self.tick)

        if self.last and moment:
            difference = (moment - self.last['moment']).total_seconds()
            broken = broken or difference < 0 or difference > MapActivityBuilder.DEFAULT_MAX_GAP_SECONDS

        if broken or boundary:
            # Explicit exit bounds observation by its timestamp; a gap uses the last record.
            if boundary and not broken and moment and self.last:
                self.last = {'line': line, 'timestamp': stamp, 'moment': moment}

            self.finish('boundary' if boundary else 'gap')

        if pid is not None:
            self.pid = pid

        if tick is not None:
            self.tick = tick

        if moment is None:
            if own and (code in self.DISCONNECTS or TechnicalIssueClassifier.category(row) in self.CATEGORIES):
                self.finish('missing_time')

            return

        if boundary:
            return

        item = {'line': line, 'timestamp': stamp, 'moment': moment}

        for category in self.CATEGORIES:
            self.pending.setdefault(category, {**item, 'left_censored': True, 'entry_lines': []})

        issue = TechnicalIssueClassifier.category(row) if own else None
        categories = ({'disconnect'} if own and code in self.DISCONNECTS else set()) | ({issue} if issue in self.CATEGORIES else set())

        for category in sorted(categories):
            self.close(category, item, False, 'event')
            self.pending[category] = {**item, 'left_censored': False, 'entry_lines': []}

        if own and code == 'area.enter':
            for pending in self.pending.values():
                if line != pending['line']:
                    pending['entry_lines'].append(self.mapping[line])

        self.last = item

    def close(self, category, end, right_censored, reason):
        start = self.pending[category]

        if start['left_censored'] and start['line'] == end['line']:
            return

        self.rows.append({'category': category, 'line': self.mapping[start['line']], 'timestamp': start['timestamp'],
                          'end_line': self.mapping[end['line']], 'ended_at': end['timestamp'],
                          'left_censored': start['left_censored'], 'right_censored': right_censored, 'reason': reason,
                          'entry_lines': list(start['entry_lines']),
                          'origin': {'source': self.source_id, 'first_line': start['line'], 'last_line': end['line']}})

    def finish(self, reason):
        if self.last is not None:
            for category in self.pending:
                self.control.check()
                self.close(category, self.last, True, reason)

        self.pending.clear()
        self.last = None
