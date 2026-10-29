from bisect import bisect_left, bisect_right

from poe_log_analyze.stages.composition.AfkMeasurements import AfkMeasurements
from poe_log_analyze.stages.composition.analytics.MeasuredSpanIndex import MeasuredSpanIndex


class SourceSpanIndex:
    """Measurements use only the proven source path, including multiple sessions."""

    def __init__(self, intervals, selection) -> None:
        self.selection, self.sources = selection, {}

        for interval in intervals:
            selection.control.check()

            for origin in interval.get('origins', [interval.get('origin', {})]):
                if 'source' in origin:
                    self.sources.setdefault(origin['source'], []).append((origin['first_line'], origin['last_line'], interval))

        for source, rows in list(self.sources.items()):
            ordered = sorted(rows, key = lambda row: (row[0], row[1]))
            maximum, ends = 0, []

            for first, last, interval in ordered:
                maximum = max(maximum, last)
                ends.append(maximum)

            self.sources[source] = ordered, [row[0] for row in ordered], ends

    def measure(self, origin, start, end):
        self.selection.control.check()
        bounds = self.selection.clip(start, end)

        if bounds is None:
            return None

        a, b, elapsed = bounds
        left, right = MeasuredSpanIndex.moment(a), MeasuredSpanIndex.moment(b)
        rows, starts, ends = self.sources.get(origin['source'], ([], [], []))
        lo, hi = bisect_left(ends, origin['first_line']), bisect_right(starts, origin['last_line'])
        seconds, marked, known, observed, seen = 0, 0, True, False, set()

        for first, last, interval in rows[lo:hi]:
            self.selection.control.check()

            if last < origin['first_line'] or id(interval) in seen:
                continue

            seen.add(id(interval))
            amount = MeasuredSpanIndex.overlap(left, right, interval['started_at'], interval['ended_at'])
            zero = left == right and MeasuredSpanIndex.moment(interval['started_at']) <= left <= MeasuredSpanIndex.moment(interval['ended_at'])

            if not amount and not zero:
                continue

            observed = True
            seconds += amount
            known = known and 'afk_intervals' in interval

            for part in interval.get('afk_intervals', []):
                marked += MeasuredSpanIndex.overlap(left, right, part['entered_at'], part['ended_at'])

        return {**AfkMeasurements.balance(seconds if observed else None, marked if known and observed else None),
                'elapsed_seconds': elapsed, 'covered': observed and abs(seconds - elapsed) < .000001,
                'overlapping': seconds > elapsed + .000001,
                'clipped': left != MeasuredSpanIndex.moment(start) or right != MeasuredSpanIndex.moment(end)}
