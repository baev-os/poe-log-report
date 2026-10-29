from poe_log_analyze.stages.composition.MapPaceBuilder import MapPaceBuilder


class MapOutlierBuilder:
    """Compare map duration with other instances of the same type and level."""

    MINIMUM_PEERS = 5
    MINIMUM_EXCESS_SECONDS = 120
    FACTOR = 2

    @classmethod
    def build(cls, explorer: dict, areas: dict, gaps: dict, control) -> dict:
        control.check()
        visits = {}

        for area in areas['pages']:
            for day in area['days']:
                for visit in day['rows']:
                    control.check()
                    visits[visit['line']] = visit

        returns = {row['line']: row for row in gaps['rows'] if row['return']}
        contexts, modes = {}, {}

        for mode, field in (('all', 'seconds'), ('without_afk', 'remaining_seconds')):
            groups, excluded = {}, 0

            for row in explorer['rows']:
                control.check()
                level = cls.level(row)

                if row['excluded'] or not row['area_id'] or level is None or row.get(field) is None:
                    excluded += 1
                    continue

                groups.setdefault((row['area_id'], level), []).append(row)

            rows, samples, insufficient, compared = [], [], 0, 0

            for (area_id, level), group in sorted(groups.items()):
                control.check()
                ordered = sorted(group, key = lambda row: (row[field], row['line']))
                values = [row[field] for row in ordered]
                peers = len(group) - 1
                ready = peers >= cls.MINIMUM_PEERS
                samples.append({'area_id': area_id, 'level': level, 'count': len(group), 'peers': peers,
                                'ready': ready, 'name': ' / '.join(sorted({row['name'] for row in group})),
                                'href': group[0]['type']})

                if not ready:
                    insufficient += len(group)
                    continue

                compared += len(group)

                for index, row in enumerate(ordered):
                    control.check()
                    baseline = cls.peer_median(values, index)
                    excess = row[field] - baseline

                    if row[field] < cls.FACTOR * baseline or excess < cls.MINIMUM_EXCESS_SECONDS:
                        continue

                    line = row['line']

                    if line not in contexts:
                        contexts[line] = cls.context(row, visits, returns, control)

                    percent = excess * 100 / baseline if baseline else None
                    rows.append({**{key: row[key] for key in ('line', 'name', 'icon', 'area_id', 'type', 'entry',
                        'href', 'session_href', 'duration', 'afk_duration', 'remaining_duration', 'returns')},
                        'level': level, 'peers': peers, 'seconds': row[field],
                        'selected_duration': MapPaceBuilder.duration(row[field]),
                        'median_seconds': baseline, 'median_duration': MapPaceBuilder.duration(baseline),
                        'excess_seconds': excess, 'excess_duration': MapPaceBuilder.duration(excess),
                        'excess_percent': percent, 'percent_label': f'+{percent:.1f}%' if percent is not None else '—',
                        'context': contexts[line]})

            rows.sort(key = lambda row: (-row['excess_seconds'], row['line']))
            modes[mode] = {'rows': rows, 'groups': samples, 'count': len(rows), 'compared': compared,
                           'insufficient': insufficient, 'excluded': excluded, 'total': len(explorer['rows'])}

        return {'version': '1', 'minimum_peers': cls.MINIMUM_PEERS,
                'minimum_excess_seconds': cls.MINIMUM_EXCESS_SECONDS, 'factor': cls.FACTOR, 'modes': modes}

    @staticmethod
    def level(row: dict) -> int | None:
        levels = {visit['level'] for visit in row['visits']}
        return next(iter(levels)) if len(levels) == 1 and None not in levels else None

    @staticmethod
    def peer_median(values: list[float], omitted: int) -> float:
        """Median excluding the current row in O(1) after sorting the whole group."""

        count = len(values) - 1
        left, right = (count - 1) // 2, count // 2

        return (values[left + (left >= omitted)] + values[right + (right >= omitted)]) / 2

    @staticmethod
    def context(row: dict, visits: dict, returns: dict, control) -> dict:
        history, deaths, gaps = [], {}, []

        for item in row['visits']:
            control.check()
            visit = visits[item['line']]
            history.append({**{key: visit[key] for key in ('line', 'entry', 'day_label', 'duration',
                            'afk_duration', 'remaining_duration', 'href')}, 'visit_href': item['href']})

            for event in visit['death_messages']:
                deaths[event['line']] = event

            if item['line'] in returns:
                gaps.append(returns[item['line']])

        return {'visits': history, 'deaths': sorted(deaths.values(), key = lambda event: event['line']),
                'mechanics': row['evidence'], 'gaps': gaps}
