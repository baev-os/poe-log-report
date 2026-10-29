from statistics import median


class RemainingMonstersBuilder:
    """The last recorded /remaining value does not prove subsequent map completion."""

    @classmethod
    def build(cls, index, explorer) -> dict:
        events = index.selected({'screen.monsters_remaining'})
        maps = {row['line']: row for row in explorer['rows']}
        grouped, unassigned = {}, []

        for row in events:
            index.selection.control.check()
            fields, context = row['fields'], row['context']
            row['count'] = 1 if fields.get('single') is not None else int(fields['count'])

            if context is None or context['kind'] != 'map' or context['run_line'] not in maps:
                unassigned.append(row)
                continue

            grouped.setdefault(context['run_line'], []).append(row)

        rows, types = [], {}

        for line, source in maps.items():
            index.selection.control.check()
            observations = sorted(grouped.get(line, []), key = lambda row: row['line'])
            ambiguous = any(row['context']['branched'] for row in observations)
            last = observations[-1] if observations and not ambiguous else None
            rows.append({'line': line, 'name': source['name'], 'href': f'maps/runs/{line}/index.html',
                         'state': 'ambiguous' if ambiguous else 'recorded' if last else 'unobserved',
                         'last': last, 'observations': observations})

            if last is not None:
                context = last['context']

                if context['area_id'] and context['level'] is not None:
                    key = context['area_id'], context['level']
                    types.setdefault(key, []).append(last)

        observed = [row['last'] for row in rows if row['last'] is not None]
        bins = []

        for code, low, high in (('zero', 0, 0), ('few', 1, 10), ('some', 11, 50), ('many', 51, None)):
            count = sum(low <= row['count'] and (high is None or row['count'] <= high) for row in observed)
            bins.append({'code': code, 'count': count, 'share': count * 100 / len(observed) if observed else None})

        return {'version': '1', 'map_count': len(maps), 'observed_count': len(observed),
                'unobserved_count': sum(row['state'] == 'unobserved' for row in rows),
                'ambiguous_count': sum(row['state'] == 'ambiguous' for row in rows),
                'message_count': len(events), 'unassigned': unassigned, 'rows': rows, 'bins': bins,
                'groups': [{'area_id': area, 'level': level, 'name': values[0]['context']['name'],
                            'count': len(values), 'zero_count': sum(row['count'] == 0 for row in values),
                            'median_count': median(row['count'] for row in values)}
                           for (area, level), values in sorted(types.items())]}
