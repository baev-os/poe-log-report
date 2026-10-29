from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.stages.merging.SharedIntervals import SharedIntervals


class SharedSessions:
    """Preserve session line membership regardless of timestamps and file order."""

    @staticmethod
    def line_ranges(mapping: list[int], first: int, last: int, control: ExecutionContext) -> list[list[int]]:
        ranges = []

        for number in range(first, last + 1):
            if number % 1000 == 0:
                control.check()

            line = mapping[number]

            if ranges and line == ranges[-1][1] + 1:
                ranges[-1][1] = line
            else:
                ranges.append([line, line])

        return ranges

    @staticmethod
    def merge(records: list[dict], measurements: SharedIntervals) -> list[dict]:
        groups = {}

        for record in records:
            groups.setdefault(record['first_line'], []).append(record)

        sessions = []

        for first, copies in groups.items():
            measurements.control.check()
            ranges = []

            for start, end in sorted(span for record in copies for span in record['line_ranges']):
                if ranges and start <= ranges[-1][1] + 1:
                    ranges[-1][1] = max(end, ranges[-1][1])
                else:
                    ranges.append([start, end])

            branches = [{key: record[key] for key in ('started_at', 'ended_at', 'first_line', 'last_line',
                                                      'reason', 'incomplete')}
                        for record in measurements.maximal(copies)]
            sessions.append({'first_line': first, 'line_ranges': ranges, 'branches': branches})

        return sessions
