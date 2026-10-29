from datetime import date, datetime, timedelta
from math import cos, pi, sin

from poe_log_analyze.runtime.DurationFormatter import DurationFormatter


class BasicReportBuilder:
    """Compact views without raw lines or technical evidence."""

    MAP_COLORS = ('#17697d', '#a16a23', '#725193', '#b84c5d', '#427536', '#316fa2', '#926349', '#567c80')
    TIME_COLORS = {'map': '#55a9bf', 'hideout': '#d89b56', 'other': '#9582cb', 'unallocated': '#87929b'}

    @classmethod
    def build(cls, content, catalogue, control) -> dict:
        views = content.views
        daily = [{key: day[key] for key in ('date', 'seconds', 'duration', 'label', 'x', 'y', 'width', 'height')}
                 for day in views['daily_playtime']['days']]
        ticks = {round(index * (len(daily) - 1) / 5) for index in range(6)}

        for index, day in enumerate(daily):
            day['tick'] = index in ticks

        weeks = {}
        cumulative = 0

        for day in daily:
            control.check()
            stamp = date.fromisoformat(day['date'])
            week = (stamp - timedelta(days = stamp.weekday())).isoformat()
            row = weeks.setdefault(week, {'date': week, 'end': day['date'], 'seconds': 0})
            row['end'] = day['date']
            row['seconds'] += day['seconds']
            cumulative += day['seconds']
            day['cumulative_seconds'] = cumulative
            day['cumulative_duration'] = DurationFormatter.duration_label(cumulative)

        for week in weeks.values():
            week['duration'] = DurationFormatter.duration_label(week['seconds'])

        types = {row['area_id']: row for row in views['statistics_summary']['map_types']}
        maps = []

        for row in views['map_pool']['summary']['types']:
            control.check()
            summary = types.get(row['area_id'], {})
            maps.append({key: row[key] for key in ('name', 'count', 'share')} | {
                'duration': summary.get('duration', '—'),
                'color': cls.MAP_COLORS[len(maps) % len(cls.MAP_COLORS)],
                'percentage': cls.percent(row['share'], catalogue)})

        mechanics = [{'label': ' + '.join(catalogue.text('mechanic.' + code) for code in row['codes'])
                      if row['codes'] else catalogue.text('basic.no_mechanics'),
                      'percentage': cls.percent(row['share'], catalogue)}
                     for row in views['mechanic_combinations']['sets']]
        messages = []
        period = views['report_period']
        start = datetime.fromisoformat(period['start_inclusive']) if period['start_inclusive'] else None
        end = datetime.fromisoformat(period['end_exclusive']) if period['end_exclusive'] else None

        for group in views['conversations']['groups']:
            for message in group['messages']:
                control.check()
                stamp = datetime.fromisoformat(message['timestamp']) if message['timestamp'] else None

                if period['active'] and (stamp is None or (start and stamp < start) or (end and stamp >= end)):
                    continue

                messages.append({key: message[key] for key in ('timestamp', 'time', 'utc', 'character', 'direction', 'text')} | {
                    'conversation': group['title'], 'channel': group['kind'] if group['kind_code'] == 'whisper' else group['title']})

        messages.sort(key = lambda row: (not bool(row['utc']), row['utc']))
        palette = {name: index % 6 for index, name in enumerate(sorted({row['character'] for row in messages}))}

        for row in messages:
            row['color'] = palette[row['character']]
            row['day'] = row['timestamp'][:10] if row['timestamp'] else catalogue.text('ui.unknown_2')

        playtime = {row['date']: row for row in daily}
        calendar = []

        for month in views['calendar']['months']:
            weeks_model = []

            for week in month['weeks']:
                weeks_model.append([{
                    'date': cell['date'], 'number': cell['number'], 'current': cell['current'],
                    'duration': playtime.get(cell['date'], {}).get('duration', ''),
                    'seconds': playtime.get(cell['date'], {}).get('seconds', 0),
                    'maps': cell['maps']['count'] if cell['maps'] else 0,
                } for cell in week])

            calendar.append({'id': month['id'], 'label': month['label'], 'weeks': weeks_model})

        days = []

        for key, day in sorted(views['daily_areas']['by_date'].items()):
            control.check()
            days.append({'date': key, 'label': day['label'],
                         'duration': playtime.get(key, {}).get('duration', '—'),
                         'zones': cls.zones(day['zones'], control)})

        return {'version': '2', 'weekly_intensity': views['weekly_intensity'], 'period': period, 'timezone': content.analysis['timezone'],
                'duration': content.activity['duration'], 'seconds': content.activity['seconds'],
                'daily': daily, 'weekly': list(weeks.values()), 'maps': maps,
                'daily_ticks': views['daily_playtime']['ticks'],
                'time_balance': cls.time_balance(views['afk']['summary'], catalogue, control),
                'map_pie': cls.map_pie(maps, control),
                'map_unknown': views['map_pool']['summary']['unknown'], 'mechanics': mechanics,
                'calendar': calendar, 'days': days, 'messages': messages,
                'activities': cls.activities(views['activities'], control),
                'characters': cls.characters(views['characters'], control)}

    @classmethod
    def activities(cls, model, control) -> dict:
        groups = []
        summary = []
        zones = []
        cursor = 30

        for group in model['groups']:
            control.check()
            summary.append({'code': group['code'], 'color': group['color'],
                            'totals': {key: group['totals'][key] for key in ('visits', 'duration')},
                            'linked': bool(model['periods'] and group['totals']['visits']),
                            'children': [{'code': child['code'],
                                          'totals': {key: child['totals'][key] for key in ('visits', 'duration')},
                                          'linked': bool(model['periods'] and child['totals']['visits'])}
                                         for child in group['children']]})
            children = [child for child in group['children'] if child['totals']['visits']]

            if not children:
                continue

            heading = cursor + 14

            if len(children) > 1:
                cursor += 28

            compact = []

            for child in children:
                visits = []
                zones.extend(child['zones'])

                for visit in child['visits']:
                    control.check()
                    visits.append({key: value for key, value in visit.items()
                                   if key in ('name', 'entry', 'exit', 'start', 'end', 'measured', 'duration', 'x', 'width')})

                compact.append({'code': child['code'], 'y': cursor + 20,
                                'totals': {key: child['totals'][key] for key in ('visits', 'duration')},
                                'zones': cls.zones(child['zones'], control),
                                'visits': visits})
                cursor += 42

            groups.append({'code': group['code'], 'color': group['color'], 'heading_y': heading,
                           'totals': {key: group['totals'][key] for key in ('visits', 'duration')},
                           'children': compact})
            cursor += 12

        return {'version': '1', 'timezone': model['timezone'], 'periods': model['periods'],
                'height': cursor + 60, 'groups': groups, 'summary': summary, 'zones': cls.zones(zones, control)}

    @classmethod
    def time_balance(cls, model, catalogue, control) -> dict:
        categories = []
        offset = 0

        for row in model['categories']:
            control.check()
            categories.append({key: row[key] for key in ('code', 'seconds', 'duration', 'share')} | {
                'percentage': cls.percent(row['share'] if model['seconds'] else None, catalogue),
                'color': cls.TIME_COLORS[row['code']], 'offset': offset})
            offset += row['share']

        return {key: model[key] for key in ('seconds', 'duration', 'afk_duration')} | {
            'afk_percentage': cls.percent(model['afk_share'] if model['seconds'] else None, catalogue),
            'categories': categories}

    @staticmethod
    def zones(rows, control) -> list[dict]:
        """One name per simple table row; unknown time must not become zero."""

        merged = {}

        for row in rows:
            control.check()
            item = merged.setdefault(row['name'], {'name': row['name'], 'visits': 0, 'seconds': 0, 'known': False})
            item['visits'] += row['visits']
            item['seconds'] += row['seconds']
            item['known'] |= bool(row['measured_visits'] or row['seconds'])

        ordered = sorted(merged.values(), key = lambda row: (-row['seconds'], -row['visits'], row['name']))
        return [{'name': row['name'], 'visits': row['visits'],
                 'duration': DurationFormatter.duration_label(row['seconds']) if row['known'] else '—'} for row in ordered]

    @classmethod
    def map_pie(cls, rows, control) -> list[dict]:
        """Shares use the same known-new-map denominator as the table."""

        total = sum(row['count'] for row in rows)
        slices = []
        angle = -pi / 2

        for index, row in enumerate(rows):
            control.check()

            if not total or not row['count']:
                continue

            end = angle + 2 * pi * row['count'] / total
            start_x, start_y = 120 + 100 * cos(angle), 120 + 100 * sin(angle)
            end_x, end_y = 120 + 100 * cos(end), 120 + 100 * sin(end)

            if row['count'] == total:
                path = 'M 120,20 A 100,100 0 1,1 120,220 A 100,100 0 1,1 120,20 Z'
            else:
                path = (f'M 120,120 L {start_x:.6f},{start_y:.6f} A 100,100 0 '
                        f'{int(end - angle > pi)},1 {end_x:.6f},{end_y:.6f} Z')

            slices.append({key: row[key] for key in ('name', 'count', 'percentage')} | {
                'color': row.get('color', cls.MAP_COLORS[index % len(cls.MAP_COLORS)]), 'path': path})
            angle = end

        return slices

    @staticmethod
    def characters(model, control) -> dict:
        characters = []

        for character in model['characters']:
            control.check()
            charts = []

            for chart in character['charts']:
                charts.append({'kind': chart['kind'], 'ticks': chart.get('ticks', []), 'time_ticks': chart.get('time_ticks', []),
                               'events': [{key: event[key] for key in ('x', 'y', 'label', 'level', 'class')}
                                          for event in chart['events']],
                               'deaths': [{key: death[key] for key in ('x', 'time', 'count')} for death in chart['deaths']],
                               'segments': [{side: {key: segment[side][key] for key in ('x', 'y')}
                                             for side in ('start', 'end')} for segment in chart.get('segments', [])]})

            characters.append({'id': character['id'], 'name': character['name'], 'classes': character['classes'],
                               'first': {'level': character['first']['level']} if character['first'] else None,
                               'last': {'level': character['last']['level']} if character['last'] else None,
                               'count': character['count'], 'deaths': {'count': character['deaths']['count']},
                               'charts': charts})

        return {'characters': characters}

    @staticmethod
    def percent(value, catalogue) -> str:
        if value is None:
            return '—'

        text = f'{value:.1f}'

        if catalogue.language == 'ru':
            text = text.replace('.', ',')

        return text + ' %'
