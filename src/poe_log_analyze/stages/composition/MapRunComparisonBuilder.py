from datetime import datetime
from decimal import Decimal

from poe_log_analyze.stages.composition.MapOutlierBuilder import MapOutlierBuilder


class MapRunComparisonBuilder:
    """Independent A/B records from run cards without pairwise data multiplication."""

    METRICS = (('map', 'map_run.on_map', 'duration'), ('afk', 'map_run.map_afk', 'duration'),
               ('remaining', 'afk.remaining_duration', 'duration'), ('visits', 'run_compare.visits', 'number'),
               ('returns', 'comparison.map_returns', 'number'), ('gaps', 'map_run.gaps', 'duration'),
               ('gap_afk', 'run_compare.gap_afk', 'duration'), ('gap_count', 'run_compare.gap_count', 'number'),
               ('unknown_gaps', 'run_compare.unknown_gaps', 'number'),
               ('loading_count', 'comparison.loading_count', 'number'), ('loading', 'comparison.loading_seconds', 'duration'),
               ('deaths', 'session_compare.deaths', 'number'), ('issues', 'run_compare.issues', 'number'))

    @classmethod
    def build(cls, details: dict, control) -> dict:
        control.check()
        result = {}

        for page in details['pages']:
            control.check()
            groups = cls.events(page, control)
            known = not page['unknown_gaps']
            values = {'map': page['seconds'] if page['observed'] else None,
                'afk': page['afk_seconds'], 'remaining': page['remaining_seconds'],
                'visits': len(page['visits']), 'returns': page['returns'],
                'gaps': page['gap_balance']['seconds'] if known else None,
                'gap_afk': page['gap_balance']['afk_seconds'] if known else None,
                'gap_count': sum(gap['known'] for gap in page['gaps']), 'unknown_gaps': page['unknown_gaps'],
                'loading_count': len(page['loading']),
                'loading': float(sum((Decimal(row['seconds']) for row in page['loading']), Decimal(0))),
                'deaths': sum(len(group['rows']) for group in groups if group['code'].startswith('death_messages:')),
                'issues': len(page['issues'])}
            result[str(page['line'])] = {'id': str(page['line']), 'name': page['name'], 'path': page['path'],
                'entry': page['entry'], 'area_id': page['area_id'], 'level': MapOutlierBuilder.level(page),
                'levels': list(page['levels']), 'flags': list(page['excluded']),
                'metrics': [{'code': code, 'label_key': key, 'kind': kind, 'value': values[code]}
                            for code, key, kind in cls.METRICS],
                'groups': groups, 'timeline': cls.timeline(page, control), 'suggested': None}

        peers = {}

        for row in result.values():
            if row['area_id'] and row['level'] is not None:
                peers.setdefault((row['area_id'], row['level']), []).append(row['id'])

        ids = list(result)

        for row in result.values():
            control.check()
            candidates = peers.get((row['area_id'], row['level']), [])

            if len(candidates) < 2:
                candidates = ids

            row['suggested'] = next((identity for identity in candidates[:2] if identity != row['id']), None)

        return {'version': '1', 'timezone': details['timezone'], 'by_run': result}

    @staticmethod
    def events(page: dict, control) -> list[dict]:
        groups = {}

        for visit in page['visits']:
            for field, prefix in (('mechanics', 'mechanic.'), ('discoveries', 'discovery.'),
                                  ('mercenaries', 'flow.'), ('death_messages', 'event_title.')):
                for event in visit[field]:
                    control.check()
                    code = 'mercenaries' if field == 'mercenaries' else event['code']
                    group = groups.setdefault(field + ':' + code, {'label_key': prefix + code, 'rows': {}})
                    group['rows'][event['line']] = {key: event.get(key, '') for key in
                        ('line', 'href', 'time', 'character', 'speaker', 'utterance')}

        for issue in page['issues']:
            control.check()
            group = groups.setdefault('issues:' + issue['family'],
                                      {'label_key': 'stability.family.' + issue['family'], 'rows': {}})
            group['rows'][issue['line']] = {'line': issue['line'], 'href': issue['href'], 'time': issue['time'],
                'character': '', 'speaker': '', 'utterance': '',
                'detail_href': 'technical/issues/index.html#stability-record-' + str(issue['line'])}

        return [{'code': code, 'label_key': group['label_key'],
                 'rows': [group['rows'][line] for line in sorted(group['rows'])]} for code, group in sorted(groups.items())]

    @staticmethod
    def timeline(page: dict, control) -> dict | None:
        chart = page['timeline']

        if chart is None or page['timestamp'] is None:
            return None

        origin = datetime.fromisoformat(page['timestamp']).timestamp()
        span = chart['end'] - chart['start']
        offset = chart['start'] - origin
        tracks = []

        for track in chart['tracks']:
            control.check()
            tracks.append({**track, 'items': [{**item, 'relative_from': offset + item['from'] * span,
                                              'relative_to': offset + item['to'] * span} for item in track['items']]})

        return {'origin': page['timestamp'], 'min': min(0, offset), 'max': max(0, chart['end'] - origin),
                'height': chart['height'], 'tracks': tracks}
