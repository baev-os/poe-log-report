from poe_log_analyze.stages.composition.analytics.AnalyticsNavigation import AnalyticsNavigation
from poe_log_analyze.stages.composition.MapOutlierBuilder import MapOutlierBuilder


class MeasurementCoverageBuilder:
    """Coverage of each page's primary dataset; exclusion reasons may overlap."""

    VIEWS = {'trading': 'trade_activity', 'recovery': 'disconnect_returns', 'cycles': 'map_cycles',
             'focus': 'window_focus', 'remaining': 'remaining_monsters', 'returns': 'return_profile',
             'session_edges': 'session_edges', 'network': 'network_health', 'passives': 'passive_history',
             'marker_timing': 'marker_timing', 'routes': 'area_route_patterns', 'trade_api': 'trade_api',
             'level_progress': 'level_progress', 'presence': 'area_presence', 'memory': 'memory_history',
             'startup': 'startup_history', 'environment': 'client_environment',
             'acquisitions': 'acquisition_history', 'milestones': 'milestone_history',
             'pool': 'map_pool', 'marker_order': 'marker_order', 'fault_intervals': 'fault_intervals', 'filters': 'filter_history'}

    @classmethod
    def build(cls, views, control) -> dict:
        result = []

        for page in AnalyticsNavigation.PAGES:
            control.check()

            if page == 'coverage':
                continue

            records, basis = cls.records(page, views)
            rows = []

            for record in records:
                control.check()
                event = record.get('event', record)
                context = event.get('context')
                choices = record.get('choices', [])
                exclusions = set(record.get('excluded', []))

                if len(choices) == 1:
                    exclusions.update(choices[0].get('excluded', []))

                branched = bool(record.get('branched') or context and context.get('branched') or
                                'branched' in exclusions or record.get('state') in ('branched', 'ambiguous'))
                clipped = bool(record.get('clipped') or 'clipped' in exclusions or
                               any(choice.get('span') and choice['span']['clipped'] for choice in choices))
                usable = cls.usable(page, record, exclusions, branched, clipped)
                rows.append({'usable': usable, 'unknown_context': 'context' in event and context is None,
                             'context_assessed': 'context' in event,
                             'date_assessed': 'timestamp' in event or 'date' in event,
                             'undated': ('timestamp' in event and not event['timestamp'] or
                                         'date' in event and event['date'] in (None, '', 'undated')),
                             'clipped': clipped, 'branched': branched,
                             'href': event.get('href') or record.get('href')})

            count = len(rows)
            usable = sum(row['usable'] for row in rows)
            result.append({'page': page, 'basis': basis, 'count': count, 'usable': usable,
                           'share': usable * 100 / count if count else None,
                           'unknown_context': (sum(row['unknown_context'] for row in rows)
                                               if any(row['context_assessed'] for row in rows) else None),
                           'undated': (sum(row['undated'] for row in rows)
                                       if any(row['date_assessed'] for row in rows) else None),
                           **{key: sum(row[key] for row in rows) for key in ('clipped', 'branched')},
                           'excluded': [row for row in rows if not row['usable']]})

        return {'version': '1', 'rows': result}

    @classmethod
    def records(cls, page, views):
        if page in ('mechanics', 'consistency'):
            return views['map_explorer']['rows'], 'maps'

        if page == 'rhythm':
            return list(views['session_rhythm']['by_session'].values()), 'sessions'

        if page == 'obstacles':
            return [event for group in views['action_obstacles']['groups'] for event in group['events']], 'events'

        if page == 'marker_intervals':
            return [row for group in views['marker_intervals']['groups'] for row in group['intervals']], 'intervals'

        if page == 'session_edges':
            return [edge or {'excluded': ['incomplete'], 'branched': row['state'] == 'branched'}
                    for row in views['session_edges']['rows']
                    for edge in ([row['without_maps']] if row['state'] == 'no_maps' else [row['leading'], row['trailing']])], 'intervals'

        rows = views[cls.VIEWS[page]]['rows']

        if page == 'network':
            rows = [row for row in rows if 'milliseconds' in row['fields']]
        elif page == 'environment':
            rows = [row for row in rows if 'value' in row]

        basis = ('events' if page in ('trading', 'passives', 'acquisitions', 'milestones', 'filters') else
                 'samples' if page in ('memory', 'network', 'environment') else
                 'maps' if page in ('remaining', 'returns', 'pool') else 'intervals')

        return rows, basis

    @staticmethod
    def usable(page, row, exclusions, branched, clipped) -> bool:
        if page in ('trading', 'passives', 'acquisitions', 'milestones', 'memory', 'network', 'obstacles', 'filters'):
            return True

        if page == 'pool':
            return bool(row['area_id'])

        if page == 'environment':
            return row['complete_environment'] and bool(row['fields'].get('area') or
                                                       row['context'] and row['context']['area_id'] and
                                                       row['context']['level'] is not None)

        if page == 'remaining':
            return row['state'] == 'recorded'

        if page == 'recovery':
            return row['state'] == 'observed'

        if page == 'trade_api':
            return row['state'] == 'matched'

        if page in ('mechanics', 'consistency'):
            return (not exclusions and row['seconds'] is not None and bool(row['area_id']) and
                    MapOutlierBuilder.level(row) is not None and (page != 'consistency' or bool(row['date'])))

        if page in ('focus', 'trade_api', 'presence', 'startup') and row['state'] != 'matched':
            return False

        return not exclusions and (not branched and not clipped if page == 'rhythm' else True)
