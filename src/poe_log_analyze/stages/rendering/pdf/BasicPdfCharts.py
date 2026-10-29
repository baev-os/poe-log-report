from reportlab.graphics.shapes import Drawing, Line, Rect
from reportlab.graphics.charts.piecharts import Pie
from reportlab.lib.colors import HexColor

from poe_log_analyze.stages.rendering.pdf.PdfCharts import PdfCharts


class BasicPdfCharts:
    """Readable time labels and a shared cumulative chart for print."""

    @staticmethod
    def map_shares(rows, control, palette = None):
        drawing = Drawing(510, 210)
        pie = Pie()
        pie.x, pie.y, pie.width, pie.height = 155, 10, 190, 190
        pie.data = [row['count'] for row in rows]
        pie.startAngle = 90
        pie.direction = 'clockwise'

        for index, row in enumerate(rows):
            control.check()
            pie.slices[index].fillColor = HexColor(row['color'])
            pie.slices[index].strokeColor = HexColor(palette.background if palette else '#ffffff')
            pie.slices[index].strokeWidth = .7

        drawing.add(pie)
        return PdfCharts.themed(drawing, palette)

    @staticmethod
    def daily(rows, catalogue, control, palette = None, *, overview = False):
        drawing = Drawing(510, 220)
        maximum = max(3600, max((row['seconds'] for row in rows), default = 0))
        ticks = {round(index * (len(rows) - 1) / 5) for index in range(6)}

        for tick in range(5):
            y = 40 + tick * 40
            drawing.add(Line(35, y, 505, y, strokeColor = PdfCharts.GRID))
            PdfCharts.label(drawing, 30, y - 2, round(maximum * tick / 4 / 3600, 1), textAnchor = 'end')

        PdfCharts.label(drawing, 0, 212, catalogue.text('pdf.hours'))

        for index, row in enumerate(rows):
            control.check()
            spacing = 470 / len(rows)
            x = 35 + index * spacing
            height = row['seconds'] / maximum * 160
            drawing.add(Rect(x, 40, spacing * .7, max(.5, height), fillColor = PdfCharts.ACCENT, strokeColor = None))
            seconds = int(round(row['seconds']))

            if not overview or len(rows) <= 14:
                PdfCharts.label(drawing, x + spacing * .35, 44 + height,
                                f'{seconds // 3600}:{seconds % 3600 // 60:02}', textAnchor = 'middle')

            if not overview or index in ticks:
                anchor = 'start' if overview and index == 0 else 'end' if overview and index == len(rows) - 1 else 'middle'
                PdfCharts.label(drawing, x + spacing * .35, 26, row['date'] if overview else row['date'][5:], textAnchor = anchor)

        return PdfCharts.themed(drawing, palette)

    @staticmethod
    def time_balance(model, control, palette = None):
        drawing = Drawing(510, 26)

        for row in model['categories']:
            control.check()

            if row['seconds']:
                drawing.add(Rect(row['offset'] * 5.1, 2, row['share'] * 5.1, 22,
                                 fillColor = HexColor(row['color']), strokeColor = None))

        return PdfCharts.themed(drawing, palette)

    @staticmethod
    def cumulative(rows, control, palette = None):
        drawing = Drawing(510, 205)
        maximum = max(3600, rows[-1]['cumulative_seconds'])
        previous = (35, 35)

        for tick in range(5):
            y = 35 + tick * 37
            drawing.add(Line(35, y, 505, y, strokeColor = PdfCharts.GRID))
            PdfCharts.label(drawing, 30, y, round(maximum * tick / 4 / 3600, 1), textAnchor = 'end')

        for index, row in enumerate(rows):
            control.check()
            point = (35 + index * 470 / max(1, len(rows) - 1), 35 + row['cumulative_seconds'] / maximum * 148)
            drawing.add(Line(*previous, *point, strokeColor = PdfCharts.ACCENT, strokeWidth = 1.5))
            previous = point

        PdfCharts.label(drawing, 35, 14, rows[0]['date'])
        PdfCharts.label(drawing, 505, 14, rows[-1]['date'], textAnchor = 'end')

        return PdfCharts.themed(drawing, palette)
