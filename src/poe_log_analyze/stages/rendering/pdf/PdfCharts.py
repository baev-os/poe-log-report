from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String
from reportlab.lib.colors import HexColor

from poe_log_analyze.stages.rendering.ReportPalette import ReportPalette


class PdfCharts:
    """Vector charts use prepared projection coordinates rather than HTML screenshots."""

    INK = HexColor("#243947")
    ACCENT = HexColor("#24788b")
    GRID = HexColor("#dce4e8")

    def __init__(self, catalogue, control, palette = None):
        self.palette = palette or ReportPalette()
        self.catalogue = catalogue
        self.control = control

    @classmethod
    def label(cls, drawing, x, y, text, **options):
        drawing.add(String(x, y, str(text), fontName = "ReportSans", fontSize = 7,
                           fillColor = cls.INK, **options))

    def playtime(self, model):
        drawing = Drawing(510, 205)

        for tick in model['ticks']:
            y = 35 + (320 - tick['y']) * .5
            drawing.add(Line(35, y, 505, y, strokeColor = self.GRID))
            self.label(drawing, 30, y - 2, tick['hours'], textAnchor = "end")

        for i, day in enumerate(model['days']):
            self.control.check()
            x = 35 + i * 470 / len(model['days'])
            drawing.add(Rect(x, 35, max(.3, 400 / len(model['days'])), day['height'] * .5,
                             fillColor = self.day_color(day['seconds'], self.palette.dark), strokeColor = self.ACCENT, strokeWidth = .3))

            if day['tick']:
                last = i == len(model['days']) - 1
                self.label(drawing, 505 if last else x, 10 if last else 22, day['label'],
                           textAnchor = 'end' if last else 'start')

        self.label(drawing, 0, 192, self.catalogue.text("pdf.hours"))

        return self.themed(drawing, self.palette)

    @staticmethod
    def day_color(seconds, dark = False):
        palette = ['#f0f3f5', '#dcefe9', '#a6d5ce', '#8ab5d5', '#b2a1d3']

        if dark:
            palette = ['#243441', '#204c48', '#2c6460', '#2c4c66', '#514264']

        index = 0 if seconds == 0 else 1 if seconds < 7200 else 2 if seconds < 14400 else 3 if seconds < 28800 else 4

        return HexColor(palette[index])

    def playtime_legend(self):
        drawing = Drawing(510, 24)

        for index, (seconds, label) in enumerate(((0, '0'), (1, '< 2'), (7200, '2–4'), (14400, '4–8'), (28800, '8+'))):
            drawing.add(Rect(index * 102, 5, 14, 10, fillColor = self.day_color(seconds, self.palette.dark), strokeColor = self.GRID))
            self.label(drawing, index * 102 + 20, 7, label + ' ' + self.catalogue.text('pdf.hours'))

        return self.themed(drawing, self.palette)

    def activity_overview(self, model):
        """The entire observed period on one scale, including gaps between weeks."""

        overall = model['periods'][0]
        zone = ZoneInfo(model['timezone'])
        ticks = []

        for index in range(5):
            instant = overall['start'] + (overall['end'] - overall['start']) * index / 4
            ticks.append({'instant': instant,
                          'label': datetime.fromtimestamp(instant, zone).strftime('%d.%m.%Y %H:%M'),
                          'major': True})

        return {'id': 'all', 'start': overall['start'], 'end': overall['end'], 'ticks': ticks,
                'label': self.catalogue.text('activities.all_time')}

    def activity_periods(self, model):
        zone = ZoneInfo(model['timezone'])
        overall = model['periods'][0]
        first = datetime.fromtimestamp(overall['start'], zone).date()
        cursor = first - timedelta(days = first.weekday())
        last = datetime.fromtimestamp(overall['end'], zone).date()

        while cursor <= last:
            self.control.check()
            stop = cursor + timedelta(days = 7)
            start = datetime.combine(cursor, time(), zone).timestamp()
            end = datetime.combine(stop, time(), zone).timestamp()
            active = any(visit['start'] is not None and visit['start'] < end
                         and (visit['end'] > start or visit['start'] == visit['end'] >= start)
                         for group in model['groups'] for child in group['children'] for visit in child['visits'])

            if active:
                ticks = []

                for day in range(8):
                    stamp = datetime.combine(cursor + timedelta(days = day), time(), zone)
                    ticks.append({'instant': stamp.timestamp(), 'label': stamp.strftime('%d.%m'), 'major': True})

                    if day < 7:
                        for hour in (6, 12, 18):
                            ticks.append({'instant': stamp.replace(hour = hour).timestamp(), 'label': str(hour), 'major': False})

                yield {'start': start, 'end': end, 'ticks': ticks,
                       'label': cursor.isoformat() + ' — ' + (stop - timedelta(days = 1)).isoformat()}

            cursor = stop

    def activities(self, model, period):
        # Reserve the bottom 40 points for the axis regardless of area-row count.
        scale = min(.36, 380 / (model['height'] - 60))
        height = (model['height'] - 60) * scale + 40
        drawing = Drawing(750, height)
        left, width = 175, 570
        span = period['end'] - period['start']

        for tick in period['ticks']:
            x = left + width * (tick['instant'] - period['start']) / span
            drawing.add(Line(x, 32, x, height - 10, strokeColor = self.GRID,
                             strokeWidth = .7 if tick['major'] else .25))
            anchor = 'start' if x == left else 'end' if x >= left + width else 'middle'
            self.label(drawing, x, 19 if tick['major'] else 7, tick['label'], textAnchor = anchor)

        for group in model['groups']:
            self.control.check()

            if len(group['children']) > 1:
                self.label(drawing, 0, height - group['heading_y'] * scale,
                           self.catalogue.text('activities.' + group['code']))

            for child in group['children']:
                y = height - child['y'] * scale
                self.label(drawing, 6 if len(group['children']) > 1 else 0, y - 3,
                           self.catalogue.text('activities.' + child['code']))
                drawing.add(Line(left, y - 7, left + width, y - 7, strokeColor = self.GRID))

                for visit in child['visits']:
                    self.control.check()

                    if visit['start'] is None:
                        continue

                    point = visit['start'] == visit['end']
                    final_point = point and visit['start'] == period['end'] and period.get('id') == 'all'

                    if visit['start'] >= period['end'] and not final_point:
                        continue

                    if (point and visit['start'] < period['start']) or (not point and visit['end'] <= period['start']):
                        continue

                    start = max(visit['start'], period['start'])
                    end = min(visit['end'], period['end'])
                    x = min(left + width - .6, left + width * (start - period['start']) / span)
                    drawing.add(Rect(x, y - 4, min(left + width - x, max(.6, width * (end - start) / span)), 8,
                                     fillColor = HexColor(group['color']), strokeColor = None,
                                     fillOpacity = 1 if visit['measured'] else .3))

        return self.themed(drawing, self.palette)

    def character(self, chart, *, deaths = False):
        drawing = Drawing(510, 150)

        for tick in chart['ticks']:
            y = 25 + (210 - tick['y']) * .6
            drawing.add(Line(35, y, 495, y, strokeColor = self.GRID))
            self.label(drawing, 28, y - 2, tick['level'], textAnchor = "end")

        previous = None

        for event in chart['events']:
            self.control.check()
            x, y = 35 + (event['x'] - 60) * 460 / 880, 25 + (210 - event['y']) * .6

            if previous is not None:
                drawing.add(Line(*previous, x, y, strokeColor = self.ACCENT, strokeDashArray = [3, 2]))

            drawing.add(Circle(x, y, 2, fillColor = self.ACCENT, strokeColor = None))
            previous = (x, y)

        if deaths:
            for death in chart['deaths']:
                x = 35 + (death['x'] - 60) * 460 / 880
                color = HexColor('#aa4455')
                drawing.add(Line(x - 3, 17, x + 3, 23, strokeColor = color))
                drawing.add(Line(x - 3, 23, x + 3, 17, strokeColor = color))

        for index, tick in enumerate(chart['time_ticks']):
            x = 35 + (tick['x'] - 60) * 460 / 880
            drawing.add(Line(x, 25, x, 133, strokeColor = self.GRID, strokeWidth = .4))
            anchor = 'start' if index == 0 else 'end' if index == len(chart['time_ticks']) - 1 else 'middle'
            self.label(drawing, x, 13, tick['date'], textAnchor = anchor)
            self.label(drawing, x, 3, tick['time'], textAnchor = anchor)

        return self.themed(drawing, self.palette)

    @staticmethod
    def themed(drawing, palette = None):
        if palette is None or not palette.dark:
            return drawing

        pending = [drawing]

        while pending:
            shape = pending.pop()
            pending.extend(getattr(shape, 'contents', ()))

            for name in ('fillColor', 'strokeColor'):
                value = getattr(shape, name, None)

                if value is not None and hasattr(value, 'hexval'):
                    original = '#' + value.hexval()[2:]
                    replacement = palette.replace(original)

                    if replacement != original:
                        setattr(shape, name, HexColor(replacement))

        return drawing
