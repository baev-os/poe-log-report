from poe_log_analyze.stages.composition.AfkMeasurements import AfkMeasurements
from poe_log_analyze.stages.composition.MapOutlierBuilder import MapOutlierBuilder
from poe_log_analyze.stages.composition.MapPaceBuilder import MapPaceBuilder
from poe_log_analyze.stages.composition.MapRunMetrics import MapRunMetrics


class SessionComparisonBuilder:
    """Prepare independent session samples for A/B selection without regenerating the report."""

    METRICS = (
        ('play', 'comparison.play_seconds', 'duration'),
        ('afk', 'afk.afk_duration', 'duration'),
        ('remaining', 'afk.remaining_duration', 'duration'),
        ('map', 'comparison.map_seconds', 'duration'),
        ('hideout', 'afk.hideout', 'duration'),
        ('other', 'afk.other', 'duration'),
        ('unallocated', 'afk.unallocated', 'duration'),
        ('new', 'comparison.new_maps', 'number'),
        ('returns', 'comparison.map_returns', 'number'),
        ('rate', 'session_compare.rate', 'number'),
        ('median', 'session_compare.median', 'duration'),
        ('complete', 'pace.complete', 'number'),
        ('excluded', 'pace.excluded', 'number'),
        ('gap_count', 'session_compare.gap_count', 'number'),
        ('gap', 'session_compare.gap', 'duration'),
        ('loading_count', 'comparison.loading_count', 'number'),
        ('loading', 'comparison.loading_seconds', 'duration'),
        ('deaths', 'session_compare.deaths', 'number'),
        ('outliers', 'pace.outliers', 'number'),
    )

    @classmethod
    def build(cls, views: dict, membership, runs: list[dict], control) -> dict:
        control.check()
        visits = {visit['entry_line']: visit for run in runs for visit in run['visits']}
        maps, gaps, flagged = {}, {}, {'all': {}, 'without_afk': {}}
        owners = {}

        for row in views['map_explorer']['rows']:
            control.check()
            grouped = {}

            for visit in row['visits']:
                first = membership.session(visit['line'])

                if first is not None:
                    grouped.setdefault(str(first), []).append(visit)

            for key, parts in grouped.items():
                balance = AfkMeasurements.combine(parts)
                returns = sum(visit['line'] != row['line'] and membership.selection.period.contains(
                    visits[visit['line']].get('entered_at'), membership.selection.zone_name) for visit in parts)
                maps.setdefault(key, []).append({**row, **balance, 'visits': parts,
                    'new': row['new'] if row['session_id'] == key else 0, 'returns': returns})

            owners[row['line']] = row['session_id']

        for row in views['map_pace']['gaps']['rows']:
            control.check()
            gaps.setdefault(row['session_id'], []).append(row)

        for mode, result in views['map_outliers']['modes'].items():
            for row in result['rows']:
                control.check()
                flagged[mode].setdefault(owners[row['line']], []).append({
                    'name': row['name'], 'href': f"pace/index.html#outlier-{mode}-{row['line']}"})

        result = {}
        mechanics = {item['code']: item['label_key'] for session in views['sessions']['rows']
                     for item in session['mechanics']}

        for session in views['sessions']['rows']:
            control.check()
            key = session['id']
            rows = maps.get(key, [])
            pauses = gaps.get(key, [])
            balance = views['afk']['by_session'][key]
            deaths = [item for item in session['events'] if item['event']['type'] in ('screen.slain', 'screen.suicide')]
            modes = {}

            for mode, field in (('all', 'seconds'), ('without_afk', 'remaining_seconds')):
                denominator = balance[field]
                stats = MapRunMetrics.statistics(rows, denominator, duration_field = field)
                gap = sum(row[field] for row in pauses) if all(row[field] is not None for row in pauses) else None
                values = {'play': session['seconds'], 'afk': balance['afk_seconds'],
                    'remaining': balance['remaining_seconds'],
                    **{row['code']: row['seconds'] for row in balance['categories']},
                    'new': stats['new'], 'returns': stats['returns'], 'rate': stats['rate'],
                    'median': stats['median_seconds'], 'complete': stats['complete'], 'excluded': stats['excluded'],
                    'gap_count': len(pauses), 'gap': gap,
                    'loading_count': session['observations']['loading_count'],
                    'loading': float(session['observations']['loading_seconds']), 'deaths': len(deaths),
                    'outliers': len(flagged[mode].get(key, []))}
                types, ungrouped = cls.types(rows, field, control)
                modes[mode] = {'metrics': [{'code': code, 'label_key': label, 'kind': kind, 'value': values[code]}
                                          for code, label, kind in cls.METRICS],
                               'types': types, 'ungrouped': ungrouped, 'outliers': flagged[mode].get(key, [])}
                counts = {item['code']: item['count'] for item in session['mechanics']}

                for code, label in sorted(mechanics.items()):
                    modes[mode]['metrics'].append({'code': 'mechanic:' + code, 'label_key': label,
                                                   'kind': 'number', 'value': counts.get(code, 0)})

            result[key] = {'modes': modes, 'gaps': pauses, 'deaths': deaths}

        return {'version': '1', 'by_session': result}

    @staticmethod
    def types(rows: list[dict], field: str, control) -> tuple[list[dict], int]:
        grouped, ungrouped = {}, 0

        for row in rows:
            control.check()
            level = MapOutlierBuilder.level(row)

            if not row['area_id'] or level is None:
                ungrouped += 1
                continue

            grouped.setdefault((row['area_id'], level), []).append(row)

        result = []

        for (area_id, level), group in sorted(grouped.items()):
            control.check()
            stats = MapRunMetrics.statistics(group, duration_field = field)
            result.append({'area_id': area_id, 'level': level, 'name': ' / '.join(sorted({row['name'] for row in group})),
                'href': group[0]['type'], 'median': MapPaceBuilder.duration(stats['median_seconds']),
                'median_seconds': stats['median_seconds'], 'complete': stats['complete'], 'excluded': stats['excluded'],
                'visits': [visit for row in group for visit in row['visits']]})

        return result, ungrouped
