from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

from poe_log_analyze.runtime.RuntimeResources import RuntimeResources

from poe_log_analyze.stages.rendering.ReportPalette import ReportPalette


class ActivityOverviewImage:
    """Large image of the entire timeline without a browser or screenshots."""

    @staticmethod
    def write(path, model, catalogue, control, *, dark = False) -> None:
        control.check()
        palette = ReportPalette(dark)
        scale = 4
        width, height = 4800, max(640, int(model['height'] * scale))
        image = Image.new('RGB', (width, height), palette.replace('#f7fafc'))
        draw = ImageDraw.Draw(image)
        fonts = RuntimeResources.resource_root() / 'reports/fonts'
        font = ImageFont.truetype(str(fonts / 'DejaVuSans.ttf'), 48)
        small = ImageFont.truetype(str(fonts / 'DejaVuSans.ttf'), 42)
        draw.text((40, 14), catalogue.text('basic.special_areas') + ' · ' + model['timezone'], font = font, fill = palette.replace('#203744'))

        if not model['periods']:
            draw.text((40, 100), catalogue.text('basic.empty'), font = font, fill = palette.replace('#203744'))
        else:
            period = model['periods'][0]
            span = period['end'] - period['start']
            left, right = 1050, width - 70

            for index in range(5):
                x = left + (right - left) * index / 4
                instant = period['start'] + span * index / 4
                label = datetime.fromtimestamp(instant, ZoneInfo(model['timezone'])).strftime('%d.%m.%Y %H:%M')
                draw.line((x, 100, x, height - 110), fill = palette.replace('#d6e0e6'), width = 2)
                draw.text((x, height - 80), label, font = small, fill = palette.replace('#203744'), anchor = 'rt' if index == 4 else 'lt')

            for group in model['groups']:
                control.check()

                if len(group['children']) > 1:
                    draw.text((30, group['heading_y'] * scale), catalogue.text('activities.' + group['code']), font = font, fill = palette.replace('#203744'))

                for child in group['children']:
                    y = child['y'] * scale
                    draw.text((50, y), catalogue.text('activities.' + child['code']), font = small, fill = palette.replace('#203744'), anchor = 'lm')
                    draw.line((left, y + 32, right, y + 32), fill = palette.replace('#d6e0e6'), width = 2)

                    for visit in child['visits']:
                        control.check()

                        if visit['start'] is None:
                            continue

                        x = min(right - 3, left + (right - left) * (visit['start'] - period['start']) / span)
                        stop = min(right, max(x + 3, left + (right - left) * (visit['end'] - period['start']) / span))
                        draw.rectangle((x, y - 20, stop, y + 20), fill = group['color'],
                                       outline = palette.replace('#203744') if not visit['measured'] else None, width = 2)

        control.check()
        path.parent.mkdir(parents = True, exist_ok = True)
        image.save(path, format = 'PNG', dpi = (300, 300))
        image.close()
        control.check()
