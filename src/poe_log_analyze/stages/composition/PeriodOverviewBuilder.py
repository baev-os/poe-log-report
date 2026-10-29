from decimal import Decimal
from datetime import datetime

from poe_log_analyze.stages.composition.PeriodComparisonBuilder import PeriodComparisonBuilder


class PeriodOverviewBuilder:
    """Brief overview from selected-period measurements without new event links."""

    @classmethod
    def build(cls, views: dict, activity: dict, control) -> dict:
        control.check()
        balance = views['afk']['summary']
        destinations = {'map': 'statistics/index.html', 'hideout': 'areas/index.html',
                        'other': 'areas/index.html', 'unallocated': 'sessions/index.html'}
        categories = [{**row, 'href': destinations[row['code']]} for row in balance['categories']]
        sessions = {row['id']: row for row in views['sessions']['rows']}
        pace_sessions = {row['id']: row for row in views['map_pace']['sessions']}
        days, session_rows = [], []

        for row in views['map_pace']['days']:
            control.check()
            date = row['date']

            if date in ('outside', 'undated'):
                continue

            detail = views['day_overview']['by_date'].get(date, {})
            related = [sessions[item['id']] for item in detail.get('sessions', [])]
            days.append(cls.candidate(date, date, 'maps/' + date + '/index.html', row['play_seconds'],
                                     row['new'], detail.get('loading_seconds', '0'), cls.flags(related), date))

        for row in sessions.values():
            control.check()
            session_rows.append(cls.candidate(row['id'], row['start'], row['path'], row['seconds'],
                pace_sessions.get(row['id'], {}).get('new', 0), row['observations']['loading_seconds'], cls.flags([row]),
                datetime.fromisoformat(row['started_at']).timestamp()))

        highlights = []

        for scope, rows in (('day', days), ('session', session_rows)):
            for metric in ('seconds', 'new', 'loading_share'):
                control.check()
                highlights.append({'code': scope + '_' + metric, 'metric': metric, **cls.winner(rows, metric)})

        popular = sorted(views['statistics_summary']['map_types'],
                         key = lambda row: (-row['count'], -row['visits'], row['name'], row['area_id']))[:3]
        popular = [{**row, 'href': views['area_details']['links']['map'][row['area_id'] or row['name']]}
                   for row in popular]
        outliers = {}

        for mode, result in views['map_outliers']['modes'].items():
            control.check()
            outliers[mode] = {'count': result['count'], 'compared': result['compared'],
                'insufficient': result['insufficient'], 'excluded': result['excluded'],
                'rows': [{key: row[key] for key in ('line', 'name', 'entry', 'icon', 'selected_duration',
                         'median_duration', 'excess_duration', 'peers')} | {
                         'href': views['map_run_details']['links'][str(row['line'])]}
                         for row in result['rows'][:3]]}

        comparison = cls.comparison(views['period_comparison'])

        return {'version': '1', 'timezone': views['report_period']['timezone'],
                'seconds': balance['seconds'], 'duration': balance['duration'],
                'afk_seconds': balance['afk_seconds'], 'afk_duration': balance['afk_duration'],
                'afk_share': balance['afk_share'] if balance['seconds'] else None,
                'incomplete': activity['incomplete'], 'categories': categories,
                'highlights': highlights, 'popular': popular, 'outliers': outliers, 'comparison': comparison}

    @staticmethod
    def flags(rows: list[dict]) -> list[str]:
        return [key for key in ('incomplete', 'clipped', 'branched') if any(row[key] for row in rows)]

    @staticmethod
    def candidate(identity: str, label: str, href: str, seconds: float, new: int,
                  loading: str, flags: list[str], order: str | float) -> dict:

        share = float(Decimal(loading) * 100 / Decimal(str(seconds))) if seconds > 0 else None
        return {'id': identity, 'label': label, 'order': order, 'href': href, 'seconds': seconds, 'new': new,
                'loading_seconds': loading, 'loading_share': share, 'flags': flags}

    @staticmethod
    def winner(rows: list[dict], metric: str) -> dict:
        eligible = [row for row in rows if row[metric] is not None and row[metric] > 0]

        if not eligible:
            return {'row': None, 'ties': 0}

        ordered = sorted(eligible, key = lambda row: (-row[metric], row['order'], row['id']))
        best = ordered[0]

        return {'row': dict(best), 'ties': sum(row[metric] == best[metric] for row in ordered) - 1}

    @staticmethod
    def comparison(model: dict) -> dict:
        if not model['enabled']:
            return {'enabled': False}

        codes = ('maps_per_hour', 'maps_per_hour_without_afk', 'mean_map_seconds', 'loading_per_day')
        metrics = {row['code']: row for section in model['sections'] for row in section['rows']}
        rows = [dict(metrics[code]) for code in codes]
        gaps = [model[side]['gaps'] for side in ('a', 'b')]
        averages = [gap['seconds'] / gap['count'] if gap['count'] else None for gap in gaps]
        rows.append(PeriodComparisonBuilder.row('gap_mean', 'overview.gap_mean', 'duration', *averages))

        return {'enabled': True, 'rows': rows, 'overlap': model['overlap'],
                'a': dict(model['a']['period']), 'b': dict(model['b']['period']),
                'incomplete': {side: model[side]['incomplete_play_intervals'] for side in ('a', 'b')},
                'gaps': {side: model[side]['gaps'] for side in ('a', 'b')}}
