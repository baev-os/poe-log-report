from html import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph

from poe_log_analyze.stages.rendering.pdf.BasicPdfCharts import BasicPdfCharts


class BasicPdfChapter:
    """The same five basic-site sections without raw lines or diagnostics."""

    def __init__(self, writer):
        self.writer = writer
        self.tr = writer.catalogue.text

    def compose(self, content) -> None:
        writer, tr = self.writer, self.tr
        model, views = content.views['basic'], content.views
        writer.text(tr('basic.basic'), 'title')
        writer.text(model['period']['label'] + ' · ' + model['timezone'])
        writer.heading('basic.graphs')
        writer.text(tr('basic.total_time') + ': ' + model['duration'], 'subheading')
        writer.text(tr('basic.time_note'))
        balance = model['time_balance']
        writer.text(tr('afk.marked') + ': ' + balance['afk_duration'] + ' · ' + balance['afk_percentage'])
        writer.story.append(BasicPdfCharts.time_balance(balance, writer.control, writer.palette))
        writer.table(['afk.category', 'basic.time', 'basic.share'],
                     ((tr('afk.' + row['code']), row['duration'], row['percentage']) for row in balance['categories']),
                     [290, 110, 110])

        if model['daily']:
            writer.heading('basic.cumulative')
            writer.story.append(BasicPdfCharts.cumulative(model['daily'], writer.control, writer.palette))
            writer.text(tr('basic.hours_axis'))
            writer.heading('basic.daily_time')
            writer.text(tr('basic.full_period'), 'subheading')
            writer.story.append(BasicPdfCharts.daily(model['daily'], writer.catalogue, writer.control, writer.palette, overview = True))

            if len(model['daily']) > 14:
                for offset in range(0, len(model['daily']), 14):
                    rows = model['daily'][offset:offset + 14]
                    writer.text(rows[0]['date'] + ' — ' + rows[-1]['date'], 'subheading')
                    writer.story.append(BasicPdfCharts.daily(rows, writer.catalogue, writer.control, writer.palette))

        writer.weekly_intensity(model['weekly_intensity'])
        self.activities(model['activities'])
        writer.new_page('portrait')
        writer.heading('basic.combinations')
        writer.text(tr('basic.mechanics_note'))
        writer.table(['basic.combinations', 'basic.share'],
                     ((row['label'], row['percentage']) for row in model['mechanics']), [400, 110])
        self.characters(model['characters'])
        writer.heading('basic.maps', page = True)
        writer.text(tr('basic.maps_note'))

        if model['map_pie']:
            writer.text(tr('basic.map_shares'), 'subheading')
            writer.story.append(BasicPdfCharts.map_shares(model['map_pie'], writer.control, writer.palette))

        writer.table(['stats.map_type', 'stats.map_count', 'basic.share', 'basic.time'],
                     ((Paragraph(f'<font color="{row["color"]}">■</font> ' + escape(row['name']), writer.styles['cell']),
                       row['count'], row['percentage'], row['duration']) for row in model['maps']), [240, 85, 80, 105])

        if model['map_unknown']:
            writer.text(tr('basic.unknown_maps', count = model['map_unknown']))

        writer.heading('basic.calendar', page = True)

        for month in model['calendar']:
            writer.text(month['label'], 'subheading')
            rows = []

            for week in month['weeks']:
                rows.append(['\n'.join([str(cell['number']), cell['duration'],
                            tr('basic.map_count', count = cell['maps']) if cell['maps'] else '']).strip()
                             if cell['current'] else '' for cell in week])

            writer.table(['basic.' + key for key in ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')],
                         rows, [510 / 7] * 7)

        if not model['calendar']:
            writer.text(tr('basic.empty'))

        for day in model['days']:
            writer.text(day['label'] + ' · ' + day['duration'], 'subheading')
            writer.table(['activities.zone', 'stats.visits', 'basic.time'],
                         ((row['name'], row['visits'], row['duration']) for row in day['zones']), [330, 70, 110])

        self.conversations(model['messages'])

    def activities(self, model) -> None:
        writer, tr = self.writer, self.tr

        if model['periods']:
            writer.new_page('landscape')
            writer.heading('basic.special_areas')
            writer.text(tr('basic.full_period') + ' · ' + model['timezone'], 'subheading')
            writer.story.append(writer.charts.activities(model, writer.charts.activity_overview(model)))

            for period in writer.charts.activity_periods(model):
                writer.new_page('landscape')
                writer.heading('basic.special_areas')
                writer.text(period['label'], 'subheading')
                writer.story.append(writer.charts.activities(model, period))

        writer.new_page('portrait')
        writer.heading('activities.group')
        groups = []

        for group in model['summary']:
            groups.append((tr('activities.' + group['code']), group['totals']['visits'], group['totals']['duration']))

            if len(group['children']) > 1:
                groups.extend(('↳ ' + tr('activities.' + child['code']), child['totals']['visits'], child['totals']['duration'])
                              for child in group['children'])

        writer.table(['activities.group', 'stats.visits', 'activities.duration'], groups, [330, 70, 110])
        writer.heading('activities.zones')
        rows = [(row['name'], row['visits'], row['duration']) for row in model['zones']]
        writer.table(['activities.zone', 'stats.visits', 'basic.time'], rows, [330, 70, 110])
        writer.text(tr('basic.area_note'))

    def characters(self, model) -> None:
        writer = self.writer
        writer.heading('basic.characters', page = True)
        writer.text(self.tr('basic.character_note'))

        if model['characters']:
            writer.table(['field.character', 'field.class', 'characters.first', 'characters.last',
                          'characters.level_count', 'characters.deaths'],
                         ((row['name'], ' / '.join(row['classes']) or '—',
                           row['first']['level'] if row['first'] else '—', row['last']['level'] if row['last'] else '—',
                           row['count'], row['deaths']['count']) for row in model['characters']), [110, 95, 80, 80, 75, 70])

        for character in model['characters']:
            writer.text(character['name'] + ' · ' + (', '.join(character['classes']) or '—'), 'subheading')

            for chart in character['charts']:
                if chart['kind'] != 'all':
                    writer.text(self.tr('characters.' + chart['kind']), 'subheading')

                if chart['events']:
                    writer.story.append(writer.charts.character(chart, deaths = True))
                else:
                    writer.text(self.tr('characters.range_empty'))

        if not model['characters']:
            writer.text(self.tr('basic.empty'))

    def conversations(self, messages) -> None:
        writer = self.writer
        writer.heading('basic.conversations', page = True)
        colors = ('#236879', '#725193', '#a04d45', '#526c29', '#296b9d', '#936017')

        if writer.palette.dark:
            colors = ('#7dd8e5', '#c3a5ed', '#f4a694', '#bad777', '#93c8f3', '#eac280')

        for index, color in enumerate(colors):
            writer.styles['chat-' + str(index)] = ParagraphStyle('chat-' + str(index),
                parent = writer.styles['cell'], textColor = HexColor(color))

        writer.table(['characters.date_time', 'field.character', 'basic.conversations'],
                     ((row['time'], writer.paragraph(row['direction'] + ' ' + row['character'], 'chat-' + str(row['color'])),
                       row['channel'] + ' · ' + row['conversation'] + '\n' + row['text']) for row in messages),
                     [105, 115, 290])
