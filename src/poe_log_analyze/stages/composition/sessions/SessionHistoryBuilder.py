from bisect import bisect_right
from datetime import datetime
from zoneinfo import ZoneInfo

from poe_log_analyze.runtime.DurationFormatter import DurationFormatter

from poe_log_analyze.stages.composition.AllTimeStatisticsBuilder import AllTimeStatisticsBuilder
from poe_log_analyze.stages.composition.MapFlowBuilder import MapFlowBuilder
from poe_log_analyze.stages.composition.MapObservationStatisticsBuilder import MapObservationStatisticsBuilder
from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection
from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder
from poe_log_analyze.stages.composition.events.LogObservationsBuilder import LogObservationsBuilder


class SessionHistoryBuilder:
    """Observed-session summaries linked independently through source line numbers."""

    def __init__(self, definitions: list[dict], intervals: list[dict], runs: list[dict],
                 selection: ReportPeriodSelection, *, extended: bool = True):

        self.selection = selection
        self.control = selection.control
        self.zone = ZoneInfo(selection.zone_name)
        self.rows, self.counters = {}, {}
        grouped = {}

        for interval in intervals:
            grouped.setdefault(interval['first_line'], []).append(interval)

        for definition in definitions:
            self.control.check()
            first = definition['first_line']
            original = grouped.get(first, [])
            parts = selection.intervals(original)

            if not parts:
                continue

            start = min((part['started_at'] for part in parts), key = datetime.fromisoformat)
            end = max((part['ended_at'] for part in parts), key = datetime.fromisoformat)
            seconds = sum(part['seconds'] for part in parts)
            self.rows[first] = {
                'id': str(first), 'path': f'sessions/{first}/index.html', 'first_line': first,
                'start_href': LogHistoryBuilder.line_href(first), 'started_at': start, 'ended_at': end,
                'start': self.label(start), 'end': self.label(end), 'seconds': seconds,
                'duration': DurationFormatter.duration_label(seconds),
                'incomplete': sum(bool(part['incomplete']) for part in parts),
                'branched': len(definition['branches']) > 1,
                'ending_reasons': list(dict.fromkeys(branch['reason'] for branch in definition['branches'])),
                'clipped': len(parts) != len(original) or seconds != sum(part['seconds'] for part in original),
                'line_ranges': definition['line_ranges'],
                'branches': [{**branch, 'start': self.label(branch['started_at']),
                              'end': self.label(branch['ended_at']),
                              'end_href': LogHistoryBuilder.line_href(branch['last_line'])}
                             for branch in definition['branches']],
                'events': [],
            }
            self.counters[first] = LogObservationsBuilder()

        self.ranges = sorted((start, end, first) for first, row in self.rows.items()
                             for start, end in row['line_ranges'])
        self.starts = [span[0] for span in self.ranges]

        if extended:
            self.visits(runs)

    def label(self, stamp: str) -> str:
        return datetime.fromisoformat(stamp).astimezone(self.zone).strftime('%d.%m.%Y %H:%M:%S')

    def session(self, line: int) -> int | None:
        index = bisect_right(self.starts, line) - 1

        if index >= 0 and line <= self.ranges[index][1]:
            return self.ranges[index][2]

        return None

    def visits(self, runs: list[dict]) -> None:
        grouped = {first: [] for first in self.rows}

        for run in runs:
            self.control.check()
            selected = {}

            for visit in run['visits']:
                first = self.session(visit['entry_line'])

                if first is not None:
                    selected.setdefault(first, []).append(visit)

            for first, visits in selected.items():
                grouped[first].append({**run, 'visits': visits})

        for first, selected in grouped.items():
            self.control.check()
            row = self.rows[first]
            row['statistics'] = AllTimeStatisticsBuilder.build(selected, self.control)
            model = self.selection.model(selected, self.selection.zone_name)
            row['maps'] = MapFlowBuilder.build_map_flow(model)['rows']
            observations = MapObservationStatisticsBuilder.build(model, self.control)
            row['mechanics'] = [item for item in observations['rows'] if item['count']]

    def add(self, row: dict) -> None:
        if row['type'] not in ('loading.duration', 'screen.items_identified'):
            return

        if not self.selection.period.contains(row.get('timestamp'), self.selection.zone_name):
            return

        first = self.session(row['line_number'])

        if first is not None:
            self.counters[first].add(row)

    def result(self, timeline: dict) -> dict:
        for day in timeline['by_date'].values():
            for event in day['events']:
                self.control.check()

                if event['type'] in ('area.enter', 'log.open'):
                    continue

                if not self.selection.period.contains(event['timestamp'], self.selection.zone_name):
                    continue

                first = self.session(event['line_number'])

                if first is not None:
                    self.rows[first]['events'].append({'event': event, 'time': self.label(event['timestamp']),
                                                      'href': LogHistoryBuilder.line_href(event['line_number'])})

        rows = sorted(self.rows.values(), key = lambda row: (datetime.fromisoformat(row['started_at']), row['first_line']))

        for index, row in enumerate(rows):
            self.control.check()
            row['observations'] = self.counters[row['first_line']].result()
            row['previous'] = rows[index - 1]['path'] if index else None
            row['next'] = rows[index + 1]['path'] if index + 1 < len(rows) else None
            row['events'].sort(key = lambda item: (item['event']['utc'], item['event']['line_number']))

        seconds = sum(row['seconds'] for row in rows)

        return {'version': '2', 'timezone': self.selection.zone_name, 'count': len(rows), 'rows': rows,
                'seconds': seconds, 'duration': DurationFormatter.duration_label(seconds),
                'incomplete': sum(bool(row['incomplete']) for row in rows)}
