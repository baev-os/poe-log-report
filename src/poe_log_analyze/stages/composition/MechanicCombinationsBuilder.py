from itertools import combinations

from poe_log_analyze.stages.composition.MapObservationAnalyticsBuilder import MapObservationAnalyticsBuilder
from poe_log_analyze.stages.composition.MapOutlierBuilder import MapOutlierBuilder
from poe_log_analyze.stages.composition.MapPaceBuilder import MapPaceBuilder


class MechanicCombinationsBuilder:
    """Co-occurring markers and exact mechanic sets without inferring completion."""

    MINIMUM_SAMPLE = MapObservationAnalyticsBuilder.MINIMUM_SAMPLE

    @classmethod
    def build(cls, explorer, control, *, extended: bool = True) -> dict:
        rows = list({(row['area_id'], row['line']): row for row in explorer['rows']}.values())
        sets, pairs, types = {}, {}, {}

        for row in rows:
            control.check()
            codes = tuple(sorted(set(row['mechanics'])))
            sets.setdefault(codes, []).append(row)

        summary = [{'codes': list(codes), 'count': len(values), 'lines': [row['line'] for row in values],
                    'share': len(values) * 100 / len(rows) if rows else None}
                   for codes, values in sorted(sets.items(), key = lambda item: (-len(item[1]), item[0]))]

        if not extended:
            return {'sets': summary}

        for row in rows:
            control.check()
            codes = tuple(sorted(set(row['mechanics'])))

            for pair in combinations(codes, 2):
                pairs.setdefault(pair, []).append(row['line'])

            level = MapOutlierBuilder.level(row)

            if row['area_id'] and level is not None:
                types.setdefault((row['area_id'], level), {}).setdefault(codes, []).append(row)

        modes = {}

        for mode, field in (('all', 'seconds'), ('without_afk', 'remaining_seconds')):
            groups = []

            for (area_id, level), candidates in sorted(types.items()):
                control.check()
                samples = [{'codes': list(codes), 'lines': [row['line'] for row in values],
                            **MapPaceBuilder.statistics(values, duration_field = field)}
                           for codes, values in sorted(candidates.items())]
                baseline = min(samples, key = lambda row: (-row['complete'], row['codes']))

                for sample in samples:
                    ready = min(sample['complete'], baseline['complete']) >= cls.MINIMUM_SAMPLE
                    sample.update(ready = ready, reference = sample is baseline,
                                  difference_seconds = sample['median_seconds'] - baseline['median_seconds'] if ready else None)

                first = next(iter(candidates.values()))[0]
                groups.append({'area_id': area_id, 'level': level, 'name': first['name'], 'href': first['type'],
                               'samples': samples, 'reference_codes': baseline['codes']})

            modes[mode] = {'groups': groups}

        return {'version': '1', 'map_count': len(rows), 'minimum_sample': cls.MINIMUM_SAMPLE,
                'multiple_count': sum(len(values) for codes, values in sets.items() if len(codes) > 1),
                'sets': summary,
                'pairs': [{'codes': list(codes), 'count': len(lines), 'lines': lines,
                           'share': len(lines) * 100 / len(rows) if rows else None}
                          for codes, lines in sorted(pairs.items(), key = lambda item: (-len(item[1]), item[0]))],
                'unmatched_maps': sum(not row['area_id'] or MapOutlierBuilder.level(row) is None for row in rows),
                'modes': modes}
