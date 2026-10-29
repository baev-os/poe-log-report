from collections import Counter
from datetime import date, timedelta

from poe_log_analyze.stages.composition.analytics.MarkerIntervalsBuilder import MarkerIntervalsBuilder


class MapPoolBuilder:
    """New-instance concentration by ID and streaks within proven linear sessions."""

    @classmethod
    def build(cls, explorer, spans) -> dict:
        spans.selection.control.check()
        rows = [row for row in explorer['rows'] if row['new']]
        weeks = {}

        for row in rows:
            spans.selection.control.check()

            if row['date']:
                day = date.fromisoformat(row['date'])
                weeks.setdefault((day - timedelta(days = day.weekday())).isoformat(), []).append(row)

        weekly, previous = [], None

        for week, records in sorted(weeks.items()):
            current = cls.summary(records)
            ids = {row['area_id'] for row in records if row['area_id']}
            weekly.append({'week': week, **current, 'previous_week': previous[0] if previous else None,
                           'added': sorted(ids - previous[1]) if previous else [],
                           'absent': sorted(previous[1] - ids) if previous else []})
            previous = week, ids

        sequences, skipped = MarkerIntervalsBuilder.sequences(explorer, spans)
        streaks = []

        for first, records in sequences:
            current = []

            for row in records:
                spans.selection.control.check()

                if current and current[-1]['area_id'] != row['area_id']:
                    streaks.append(cls.streak(current))
                    current = []

                current.append(row)

            if current:
                streaks.append(cls.streak(current))

        return {'version': '1', 'rows': rows, 'summary': cls.summary(rows), 'weeks': weekly,
                'streaks': sorted(streaks, key = lambda row: (-row['count'], row['line'])), 'skipped_streak_maps': skipped}

    @staticmethod
    def summary(rows, *, evidence: bool = True) -> dict:
        counts = Counter(row['area_id'] for row in rows if row['area_id'])
        known = sum(counts.values())
        ordered = sorted(counts, key = lambda key: (-counts[key], key))

        return {'count': len(rows), 'known': known, 'unknown': len(rows) - known, 'unique': len(counts),
                'top1': counts[ordered[0]] * 100 / known if known else None,
                'top3': sum(counts[key] for key in ordered[:3]) * 100 / known if known else None,
                'types': [{'area_id': key, 'name': next(row['name'] for row in rows if row['area_id'] == key),
                           'count': counts[key], 'share': counts[key] * 100 / known,
                           **({'evidence': [f"maps/runs/{row['line']}/index.html" for row in rows if row['area_id'] == key]}
                              if evidence else {})}
                          for key in ordered]}

    @staticmethod
    def streak(rows) -> dict:
        return {'line': rows[0]['line'], 'area_id': rows[0]['area_id'], 'name': rows[0]['name'], 'count': len(rows),
                'evidence': [f"maps/runs/{row['line']}/index.html" for row in rows]}
