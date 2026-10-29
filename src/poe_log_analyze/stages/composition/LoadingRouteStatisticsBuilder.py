import hashlib
import json

from datetime import date
from decimal import Decimal

from poe_log_analyze.core.request.ReportPeriod import ReportPeriod

from poe_log_analyze.stages.composition.LoadingStatisticsBuilder import LoadingStatisticsBuilder
from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder


class LoadingRouteStatisticsBuilder:
    """Directed route summaries from selected-period LOADING SCREEN durations."""

    @classmethod
    def build(cls, loading: dict, routes: list[dict], control) -> dict:
        control.check()
        context = {row['line']: row for row in routes}
        groups, known = {}, 0
        calculator = LoadingStatisticsBuilder(ReportPeriod(), loading['timezone'], control)

        for row in loading['rows']:
            control.check()
            route = context.get(row['line'], {'from_area': None, 'from_line': None, 'to_area': row['area'],
                                             'to_line': None, 'reason': 'no_entry'})
            known += route['from_area'] is not None
            key = (route['from_area'], row['area'])
            groups.setdefault(key, []).append({**row, **route,
                'from_href': LogHistoryBuilder.line_href(route['from_line']) if route['from_line'] else None,
                'to_href': LogHistoryBuilder.line_href(route['to_line']) if route['to_line'] else None})

        result = []

        for (source, target), rows in groups.items():
            control.check()
            identity = json.dumps([source, target], ensure_ascii = False).encode('utf-8')
            anchor = 'route-' + hashlib.sha256(identity).hexdigest()[:20]
            daily = {}

            for row in rows:
                control.check()
                row['anchor'] = 'loading-route-row-' + str(row['line'])
                daily.setdefault(row['date'], []).append(row)

            days = [{'date': day, 'anchor': anchor + '-day-' + day,
                     **cls.statistics(items, calculator)} for day, items in sorted(daily.items())]
            slowest = min(rows, key = lambda row: (-Decimal(row['seconds']), row['line']))
            result.append({'from_area': source, 'to_area': target, 'anchor': anchor, 'rows': rows,
                           'days': days, 'chart': cls.chart(days), 'slowest_href': slowest['href'],
                           **cls.statistics(rows, calculator)})

        result.sort(key = lambda row: (-Decimal(row['total_seconds']), row['from_area'] is None,
                                    row['from_area'] or '', row['to_area']))

        return {'version': '1', 'count': len(loading['rows']), 'known': known,
                'unknown': len(loading['rows']) - known, 'routes': result}

    @staticmethod
    def statistics(rows: list[dict], calculator: LoadingStatisticsBuilder) -> dict:
        stats = calculator.statistics(rows)
        values = sorted(Decimal(row['seconds']) for row in rows)
        value = values[(95 * len(values) + 99) // 100 - 1] if values else None

        return {**stats, 'p95_seconds': str(value) if value is not None else None,
                'p95': calculator.label(value), 'small_sample': len(values) < 20}

    @staticmethod
    def chart(days: list[dict]) -> dict:
        dated = [day for day in days if day['date'] != 'undated']

        if not dated:
            return {'bars': [], 'ticks': [], 'dates': []}

        start = date.fromisoformat(dated[0]['date']).toordinal()
        end = date.fromisoformat(dated[-1]['date']).toordinal()
        span = end - start + 1
        maximum = max(Decimal(day['p95_seconds']) for day in dated) or Decimal(1)
        bars = []

        for day in dated:
            center = 70 + 860 * (date.fromisoformat(day['date']).toordinal() - start + .5) / span
            width = min(16, 300 / span)
            bars.append({**day, 'x': center, 'width': width,
                         'median_height': float(Decimal(day['median_seconds']) / maximum) * 210,
                         'p95_height': float(Decimal(day['p95_seconds']) / maximum) * 210})

        positions = sorted({round((span - 1) * i / 5) for i in range(6)})

        return {'bars': bars,
                'ticks': [{'y': 260 - 52.5 * i, 'value': LoadingStatisticsBuilder.label(maximum * i / 4)} for i in range(5)],
                'dates': [{'x': 70 + 860 * (i + .5) / span, 'label': date.fromordinal(start + i).isoformat()}
                          for i in positions]}
