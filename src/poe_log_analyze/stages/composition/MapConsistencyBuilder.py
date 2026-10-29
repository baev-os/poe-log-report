from datetime import date

from poe_log_analyze.stages.composition.MapOutlierBuilder import MapOutlierBuilder
from poe_log_analyze.stages.composition.MapPaceBuilder import MapPaceBuilder
from poe_log_analyze.stages.composition.WeeklyPaceBuilder import WeeklyPaceBuilder


class MapConsistencyBuilder:
    """Quartiles of complete instances with one ID/level by week of first entry."""

    @staticmethod
    def quantile(values: list[float], fraction: float) -> float | None:
        if not values:
            return None

        position = (len(values) - 1) * fraction
        lower = int(position)
        upper = min(lower + 1, len(values) - 1)

        return values[lower] + (values[upper] - values[lower]) * (position - lower)

    @classmethod
    def statistics(cls, rows, field) -> dict:
        values = sorted(row[field] for row in rows if not row['excluded'] and row[field] is not None)
        q1, q3 = cls.quantile(values, .25), cls.quantile(values, .75)
        iqr = q3 - q1 if q1 is not None and q3 is not None else None

        return {**MapPaceBuilder.statistics(rows, duration_field = field),
                'q1_seconds': q1, 'q3_seconds': q3, 'iqr_seconds': iqr,
                'q1': MapPaceBuilder.duration(q1), 'q3': MapPaceBuilder.duration(q3),
                'iqr': MapPaceBuilder.duration(iqr), 'sparse': len(values) < 5,
                'lines': [row['line'] for row in rows]}

    @classmethod
    def build(cls, explorer, control) -> dict:
        rows = list({(row['area_id'], row['line']): row for row in explorer['rows']}.values())
        types, unmatched = {}, 0

        for row in rows:
            control.check()
            level = MapOutlierBuilder.level(row)

            if not row['area_id'] or level is None or not row['date']:
                unmatched += 1
                continue

            week = WeeklyPaceBuilder.monday(date.fromisoformat(row['date'])).isoformat()
            types.setdefault((row['area_id'], level), {}).setdefault(week, []).append(row)

        modes = {}

        for mode, field in (('all', 'seconds'), ('without_afk', 'remaining_seconds')):
            groups = []

            for (area_id, level), weeks in sorted(types.items()):
                control.check()
                candidates = [row for values in weeks.values() for row in values]
                first = candidates[0]
                week_rows = [{'week': week, **cls.statistics(values, field)} for week, values in sorted(weeks.items())]
                summary = cls.statistics(candidates, field)
                maximum = summary['max_seconds'] or 1

                for index, row in enumerate(week_rows):
                    control.check()
                    row['y'] = 26 + index * 36
                    row['geometry'] = ({key: 130 + row[key + '_seconds'] / maximum * 500
                                        for key in ('min', 'q1', 'median', 'q3', 'max')}
                                       if row['complete'] else None)

                groups.append({'area_id': area_id, 'level': level, 'name': first['name'], 'href': first['type'],
                               'summary': summary, 'weeks': week_rows, 'plot_height': 60 + 36 * len(week_rows),
                               'axis_max': MapPaceBuilder.duration(summary['max_seconds'])})

            modes[mode] = {'groups': groups}

        return {'version': '1', 'unmatched_maps': unmatched, 'quantile_method': 'linear-(n-1)*p', 'modes': modes}
