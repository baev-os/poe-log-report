from datetime import datetime
from decimal import Decimal

from poe_log_analyze.stages.composition.VisitMeasurements import VisitMeasurements
from poe_log_analyze.stages.composition.sessions.SessionTimelineBuilder import SessionTimelineBuilder


class MapRunTimelineBuilder:
    """Instance timeline: measurements, gaps, and messages linked by evidence."""

    @classmethod
    def build(cls, page: dict, run: dict, selection) -> dict | None:
        tracks = {'areas': [], 'afk': [], 'loading': [], 'events': []}

        for visit in run['visits']:
            selection.control.check()

            for part in VisitMeasurements.drawable(visit):
                cls.append(tracks['areas'], part.get('entered_at') or part.get('ended_at'), part.get('ended_at'),
                           page['path'] + '#visit-' + str(visit['entry_line']), visit['entry_line'],
                           'map', 'map_run.on_map', run['name'], part.get('seconds'))

        for afk in page['afk_rows']:
            cls.append(tracks['afk'], afk['entered_at'], afk['ended_at'], afk['href'], afk['line'],
                       'afk', 'afk.marked', afk['name'], afk['seconds'])

        for gap in page['gaps']:
            if not gap['known']:
                continue

            cls.append(tracks['areas'], gap['started_at'], gap['ended_at'], page['path'] + '#' + gap['anchor'],
                       gap['line'], 'gap', 'map_run.gap', '', gap['seconds'])

            for afk in gap['afk']:
                cls.append(tracks['afk'], afk['entered_at'], afk['ended_at'], afk['href'], afk['line'],
                           'afk', 'afk.marked', afk['name'], afk['seconds'])

        for load in page['loading']:
            if load['timestamp']:
                end = datetime.fromisoformat(load['timestamp']).timestamp()
                seconds = float(Decimal(load['seconds']))
                tracks['loading'].append({'left': end - seconds, 'right': end, 'line': load['line'],
                    'href': load['href'], 'category': 'loading', 'label_key': 'sessions.loading',
                    'name': load['area'], 'seconds': seconds})

        events = {}

        for visit in page['visits']:
            for field, prefix in (('mechanics', 'mechanic.'), ('discoveries', 'discovery.'),
                                  ('mercenaries', 'flow.'), ('death_messages', 'event_title.')):
                for event in visit[field]:
                    key = prefix + ('mercenaries' if field == 'mercenaries' else event['code'])
                    events[event['line']] = (event['timestamp'], event['href'], key, event.get('character', event.get('speaker', '')))

        for issue in page['issues']:
            events[issue['line']] = (issue['event']['timestamp'], issue['href'], 'stability.family.' + issue['family'], '')

        for line, (stamp, href, key, name) in events.items():
            cls.append(tracks['events'], stamp, None, href, line, 'event', key, name, None)

        items = [item for track in tracks.values() for item in track]

        if not items:
            return None

        start = min(item['left'] for item in items)
        end = max(item['right'] if item['right'] is not None else item['left'] for item in items)
        result, y = [], 55

        for code, rows in tracks.items():
            selection.control.check()
            prepared = [SessionTimelineBuilder.item(start, end, row['left'], row['right'], selection,
                        **{key: value for key, value in row.items() if key not in ('left', 'right')}) for row in rows]
            height = max(1, SessionTimelineBuilder.lanes(prepared)) * 22 + 35
            result.append({'code': code, 'y': y, 'height': height, 'items': prepared})
            y += height

        return {'start': start, 'end': end, 'height': y + 10, 'tracks': result,
                'ticks': [{'x': 70 + 860 * i / 6, 'label': SessionTimelineBuilder.label(start + (end - start) * i / 6, selection)}
                          for i in range(7)]}

    @staticmethod
    def append(rows: list[dict], start: str | None, end: str | None, href: str, line: int,
               category: str, label_key: str, name: str, seconds: float | None) -> None:

        if start:
            rows.append({'left': datetime.fromisoformat(start).timestamp(),
                         'right': datetime.fromisoformat(end).timestamp() if end else None,
                         'href': href, 'line': line, 'category': category, 'label_key': label_key,
                         'name': name, 'seconds': seconds})
