from copy import deepcopy

from poe_log_analyze.stages.merging.SharedHistory import SharedHistory


class SharedIntervals:
    """Split measured paths at branches without merging independent-branch time."""

    def __init__(self, history: SharedHistory):
        self.history = history
        self.control = history.control

    def maximal(self, records: list[dict]) -> list[dict]:
        selected = []
        ordered = sorted(records, key = self.history.order)

        for index, record in enumerate(ordered):
            self.control.check()
            origin = record['origin']
            redundant = any(self.history.prefix(origin, other['origin'])['lines'] >= origin['last_line']
                            and (other['origin']['last_line'] > origin['last_line'] or position < index)
                            for position, other in enumerate(ordered) if position != index)

            if not redundant:
                selected.append(record)

        return selected

    def segments(self, records: list[dict], start_key: str, end_key: str) -> list[dict]:
        result = []
        ordered = sorted(records, key = self.history.order)

        for index, record in enumerate(ordered):
            self.control.check()
            start, end = self.history.moment(record[start_key]), self.history.moment(record[end_key])
            shared = [self.history.shared_end(record, other, start_key, end_key) if other is not record else end
                      for other in ordered]
            points = sorted({start, end, *(point for point in shared if point is not None and start < point < end)})
            spans = list(zip(points, points[1:])) if start != end else [(start, end)]

            for begin, stop in spans:
                self.control.check()

                if any(point is not None and point >= stop for point in shared[:index]):
                    continue

                afk_intervals = []

                for afk in record.get('afk_intervals', []):
                    left = max(begin, self.history.moment(afk['entered_at']))
                    right = min(stop, self.history.moment(afk['ended_at']))

                    if left < right:
                        afk_intervals.append({**afk, 'entered_at': left.isoformat(), 'ended_at': right.isoformat()})

                afk = sum((self.history.moment(item['ended_at']) - self.history.moment(item['entered_at'])).total_seconds()
                          for item in afk_intervals)
                part = {**deepcopy(record), start_key: begin.isoformat(), end_key: stop.isoformat(),
                        'seconds': (stop - begin).total_seconds(), 'afk_seconds': afk, 'afk_intervals': afk_intervals,
                        'origins': [deepcopy(other['origin']) for other, point in zip(ordered, shared)
                                    if point is not None and point >= stop]}

                if start_key == 'entered_at':
                    part['original_entered_at'] = record['entered_at']
                    part['is_segment'] = True

                    for key in ('mechanics', 'discoveries', 'mercenaries', 'death_messages',
                                'period_observations', 'comparison_observations'):
                        part.pop(key, None)

                result.append(part)

        return result

    def exclusions(self, records: list[dict], selected: list[dict], kind: str) -> None:
        for record in records:
            self.control.check()

            if any(record is kept for kept in selected):
                continue

            kept = next(item for item in selected
                        if self.history.prefix(record['origin'], item['origin'])['lines'] >= record['origin']['last_line'])
            self.history.summary['excluded'].append({'kind': kind, **deepcopy(record['origin']), 'kept': deepcopy(kept['origin'])})

    def activity(self, intervals: list[dict]) -> list[dict]:
        groups = {}

        for interval in intervals:
            groups.setdefault(interval['first_line'], []).append(interval)

        result = []

        for records in groups.values():
            self.control.check()
            maximal = self.maximal(records)
            self.exclusions(records, maximal, 'activity')
            self.history.summary['removed_intervals'] += len(records) - len(maximal)
            parts = self.segments(records, 'started_at', 'ended_at')

            for part in parts:
                part['incomplete'] = False

                if self.history.moment(part['ended_at']) != self.history.moment(next(r['ended_at'] for r in records if r['origin'] == part['origin'])):
                    part['reason'] = 'shared_prefix'

            for record in maximal:
                if not record['incomplete']:
                    continue

                matching = [part for part in parts if record['origin'] in part['origins']
                            and self.history.moment(part['ended_at']) == self.history.moment(record['ended_at'])]

                if matching:
                    matching[-1]['incomplete'] = True
                    matching[-1]['reason'] = record['reason']

            result.extend(parts)

        self.history.summary['removed_play_seconds'] = sum(r['seconds'] for r in intervals) - sum(p['seconds'] for p in result)

        return sorted(result, key = lambda p: (p['started_at'], p['ended_at'], self.history.order(p)))
