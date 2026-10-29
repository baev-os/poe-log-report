from datetime import datetime
from zoneinfo import ZoneInfo

from poe_log_analyze.runtime.DurationFormatter import DurationFormatter

from poe_log_analyze.stages.composition.CharacterDeathBuilder import CharacterDeathBuilder

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod


class CharacterProgressionBuilder:
    """Observed level-ups by exact name from the merged history."""

    @staticmethod
    def build(timeline: dict, control: ExecutionContext, *, period: ReportPeriod = ReportPeriod(),
              deaths: dict | None = None) -> dict:

        grouped = {}
        deaths = deaths or {}
        control.check()

        for day in timeline['days']:
            for event in timeline['by_date'][day['date']]['events']:
                control.check()

                if event['type'] != 'screen.level_up':
                    continue

                fields = event['message']['fields']
                moment = datetime.fromisoformat(event['timestamp'])
                grouped.setdefault(fields['character'], []).append({
                    'line': event['line_number'], 'timestamp': event['timestamp'],
                    'instant': moment.timestamp(), 'date': moment.date().isoformat(),
                    'label': moment.strftime('%d.%m.%Y %H:%M:%S'),
                    'class': fields['class'], 'level': int(fields['level']),
                })

        characters = []

        for number, name in enumerate(sorted(grouped.keys() | deaths.keys(), key = lambda name: (name.casefold(), name)), 1):
            control.check()
            events = sorted(grouped.get(name, []), key = lambda event: (event['instant'], event['line']))
            history = deaths.get(name, CharacterDeathBuilder.summary([]))
            previous = None

            for event in events:
                event.update(delta_seconds = None, delta_duration = '—', delta_from_level = None)

                if previous is not None and event['level'] > previous['level']:
                    delta = event['instant'] - previous['instant']
                    event.update(delta_seconds = delta, delta_duration = DurationFormatter.duration_label(delta),
                                 delta_from_level = previous['level'])

                if previous is None or event['level'] != previous['level']:
                    previous = event

            events = [event for event in events if period.contains(event['timestamp'], timeline['timezone'])]

            if not events and not history['count']:
                continue

            first, last = (events[0], events[-1]) if events else (None, None)
            high = max((event['level'] for event in events), default = 0)
            charts = ([CharacterProgressionBuilder.chart([e for e in events if e['level'] <= 90], 'before_90', timeline['timezone']),
                       CharacterProgressionBuilder.chart([e for e in events if e['level'] >= 90], 'after_90', timeline['timezone'])]
                      if high > 90 else [CharacterProgressionBuilder.chart(events, 'all', timeline['timezone'])])

            for chart in charts:
                chart['deaths'] = CharacterDeathBuilder.markers(chart, history['rows'])

            for event in events:
                control.check()
                del event['instant']

            characters.append({'id': str(number), 'name': name, 'events': events,
                               'classes': sorted({event['class'] for event in events}),
                               'first': first, 'last': last, 'count': len(events),
                               'charts': charts, 'deaths': history})

        return {'version': '4', 'timezone': timeline['timezone'], 'characters': characters,
                'death_count': sum(item['deaths']['count'] for item in characters),
                'count': len(characters), 'event_count': sum(item['count'] for item in characters)}

    @staticmethod
    def chart(events: list[dict], kind: str, timezone_name: str = 'Asia/Almaty') -> dict:
        if not events:
            return {'kind': kind, 'events': []}

        start, end = events[0]['instant'], events[-1]['instant']
        low = 90 if kind == 'after_90' else min(event['level'] for event in events)
        high = 100 if kind == 'after_90' else 90 if kind == 'before_90' else max(event['level'] for event in events)
        points = []

        for event in events:
            point = {key: value for key, value in event.items() if key != 'instant'}
            point['x'] = round(60 + 880 * (event['instant'] - start) / (end - start), 2) if end != start else 500
            point['y'] = round(210 - 180 * (event['level'] - low) / (high - low), 2) if high != low else 120
            points.append(point)

        zone = ZoneInfo(timezone_name)
        count = 1 if start == end else 6
        time_ticks = []

        for index in range(count):
            fraction = index / (count - 1) if count > 1 else .5
            moment = datetime.fromtimestamp(start + fraction * (end - start), zone)
            time_ticks.append({'x': 60 + 880 * fraction, 'date': moment.strftime('%d.%m.%Y'),
                               'time': moment.strftime('%H:%M:%S')})

        step = max(1, (high - low + 5) // 6)
        levels = sorted({low, high, *range(low, high + 1, step)})

        return {'kind': kind, 'events': points, 'start': start, 'end': end,
                'time_ticks': time_ticks,
                'ticks': [{'level': level, 'y': 210 - 180 * (level - low) / (high - low)} for level in levels]
                if high != low else [{'level': low, 'y': 120}],
                'segments': [{'start': a, 'end': b} for a, b in zip(points, points[1:])]}
