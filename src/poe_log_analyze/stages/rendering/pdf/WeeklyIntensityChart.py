from reportlab.lib.colors import HexColor
from reportlab.platypus import Flowable


class WeeklyIntensityChart(Flowable):
    """Native continuous PDF gradients with a shared weekly scale."""

    def __init__(self, model, catalogue, control, palette):
        super().__init__()

        self.model = model
        self.catalogue = catalogue
        self.control = control
        self.palette = palette
        self.width, self.height = 510, 260

    def draw(self):
        canvas = self.canv
        left, width = 38, 395
        canvas.saveState()
        canvas.setFont('ReportSans', 8)

        for index, row in enumerate(self.model['rows']):
            self.control.check()
            y = 225 - index * 29
            canvas.setFillColor(HexColor(self.palette.ink))
            canvas.drawString(0, y + 7, self.catalogue.text('basic.' + ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')[index]))
            canvas.drawRightString(510, y + 7, row['duration'])
            canvas.saveState()
            path = canvas.beginPath()
            path.rect(left, y, width, 22)
            canvas.clipPath(path, stroke = 0)
            colors = [HexColor(self.palette.blend(point['color'], point['opacity'])) for point in row['points']]
            canvas.linearGradient(left, y, left + width, y, colors,
                                  positions = [point['second'] / 86400 for point in row['points']])
            canvas.restoreState()

        canvas.setFillColor(HexColor(self.palette.muted))

        for hour in (0, 6, 12, 18, 24):
            x = left + width * hour / 24
            canvas.drawCentredString(x, 20, f'{hour:02}:00')

        canvas.drawCentredString(left + width / 2, 4, self.catalogue.text('intensity.time_axis'))
        canvas.restoreState()
