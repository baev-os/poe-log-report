"""Recorded-observation analytics based on existing instance measurements."""

from poe_log_analyze.stages.composition.MapOutlierBuilder import MapOutlierBuilder
from poe_log_analyze.stages.composition.MapPaceBuilder import MapPaceBuilder


class MapObservationAnalyticsBuilder:
    """Compare groups with one ID/level while preserving shared methodological exclusions."""

    MINIMUM_SAMPLE = 5

    @classmethod
    def build(cls, observations: dict, explorer: dict, details: dict, control) -> dict:
        control.check()
        rows = {(row['area_id'], row['line']): row for row in explorer['rows']}
        rows = list(rows.values())
        pages = {page['line']: page for page in details['pages']}
        records, types = {}, {}

        for row in rows:
            control.check()
            level = MapOutlierBuilder.level(row)
            deaths = {event['line']: event for visit in pages[row['line']]['visits']
                      for event in visit['death_messages']}
            records[str(row['line'])] = {
                'line': row['line'], 'level': level, 'returns': row['returns'],
                'name': row['name'], 'path': pages[row['line']]['path'], 'entry': row['entry'],
                'duration': MapPaceBuilder.duration(row['seconds'] if row['observed'] else None),
                'afk_duration': row['afk_duration'], 'remaining_duration': row['remaining_duration'],
                'remaining_seconds': row['remaining_seconds'],
                'excluded': list(row['excluded']),
                'deaths': [dict(deaths[line]) for line in sorted(deaths)],
            }

            if row['area_id'] and level is not None:
                types.setdefault((row['area_id'], level), []).append(row)

        total = observations['map_count']

        if len(rows) != total:
            raise ValueError('Analytics instance count disagrees with the observation summary')

        by_code = {}

        for group in observations['groups']:
            control.check()
            members = {row['line'] for month in group['months'] for day in month['days'] for row in day['rows']}
            members.update(row['line'] for row in group['undated'])
            selected = [row for row in rows if row['line'] in members]

            if len(selected) != group['count']:
                raise ValueError('Not all observed instances were found in map measurements')

            counts = {day['date']: len(day['rows']) for month in group['months'] for day in month['days']}
            days = [cls.share(counts.get(day['date'], 0), day['map_count'], date = day['date'])
                    for month in observations['months'] for day in month['days']]
            modes = {}

            for mode, field in (('all', 'seconds'), ('without_afk', 'remaining_seconds')):
                control.check()
                comparisons = []

                for (area_id, level), candidates in sorted(types.items()):
                    control.check()
                    marked = [row for row in candidates if row['line'] in members]

                    if not marked:
                        continue

                    unmarked = [row for row in candidates if row['line'] not in members]
                    observed = MapPaceBuilder.statistics(marked, duration_field = field)
                    unobserved = MapPaceBuilder.statistics(unmarked, duration_field = field)
                    ready = min(observed['complete'], unobserved['complete']) >= cls.MINIMUM_SAMPLE
                    difference = observed['median_seconds'] - unobserved['median_seconds'] if ready else None
                    baseline = unobserved['median_seconds']
                    comparisons.append({
                        'area_id': area_id, 'level': level,
                        'name': ' / '.join(sorted({row['name'] for row in candidates})),
                        'href': candidates[0]['type'], 'observed': observed, 'unobserved': unobserved,
                        'observed_lines': [row['line'] for row in marked],
                        'unobserved_lines': [row['line'] for row in unmarked],
                        'ready': ready, 'difference_seconds': difference,
                        'change_percent': difference * 100 / baseline if ready and baseline else None,
                    })

                modes[mode] = {'summary': MapPaceBuilder.statistics(selected, duration_field = field),
                               'groups': comparisons, 'ready_groups': sum(row['ready'] for row in comparisons)}

            deaths = {event['line'] for row in selected for event in records[str(row['line'])]['deaths']}
            by_code[group['code']] = {
                **cls.share(group['count'], total), 'days': days,
                'undated': cls.share(len(group['undated']), observations['undated']['map_count']),
                'death_messages': len(deaths),
                'maps_with_death_messages': sum(bool(records[str(row['line'])]['deaths']) for row in selected),
                'unmatched_maps': sum(not row['area_id'] or MapOutlierBuilder.level(row) is None for row in selected),
                'modes': modes,
            }

        return {'version': '1', 'minimum_sample': cls.MINIMUM_SAMPLE,
                'map_count': total, 'by_code': by_code, 'records': records}

    @staticmethod
    def share(count: int, total: int, **fields) -> dict:
        return {**fields, 'count': count, 'total': total, 'share': count * 100 / total if total else None}
