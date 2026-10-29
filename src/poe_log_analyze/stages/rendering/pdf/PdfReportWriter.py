from html import escape
from pathlib import Path
from threading import Lock

from PIL import Image

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import LongTable, NextPageTemplate, PageBreak, Paragraph, Spacer, TableStyle, KeepTogether

from poe_log_analyze.runtime.RuntimeResources import RuntimeResources

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.stages.composition.ReportContent import ReportContent
from poe_log_analyze.stages.composition.localization.TranslationCatalogue import TranslationCatalogue
from poe_log_analyze.stages.rendering.ReportPalette import ReportPalette
from poe_log_analyze.stages.rendering.pdf.WeeklyIntensityChart import WeeklyIntensityChart
from poe_log_analyze.stages.rendering.pdf.PdfCharts import PdfCharts
from poe_log_analyze.stages.rendering.pdf.PdfDocument import PdfDocument


class PdfReportWriter:
    """Russian/English print summary from the same data as the HTML report."""

    FONT_LOCK = Lock()

    def __init__(self, catalogue: TranslationCatalogue, control: ExecutionContext, *, dark: bool = False) -> None:
        self.catalogue = catalogue
        self.control = control
        self.palette = ReportPalette(dark)
        self.profile = None
        self.charts = PdfCharts(catalogue, control, self.palette)
        self.styles = {
            'body': ParagraphStyle('body', fontName = 'ReportSans', fontSize = 9, leading = 13,
                                   textColor = HexColor('#243947'), spaceAfter = 7),
            'title': ParagraphStyle('title', fontName = 'ReportSansBold', fontSize = 23, leading = 29,
                                    textColor = HexColor('#18596b'), spaceAfter = 16),
            'heading': ParagraphStyle('heading', fontName = 'ReportSansBold', fontSize = 15, leading = 20,
                                      spaceBefore = 12, spaceAfter = 10, keepWithNext = True),
            'subheading': ParagraphStyle('subheading', fontName = 'ReportSansBold', fontSize = 11, leading = 15,
                                         spaceBefore = 8, spaceAfter = 6, keepWithNext = True),
            'cell': ParagraphStyle('cell', fontName = 'ReportSans', fontSize = 8, leading = 11),
            'header': ParagraphStyle('header', fontName = 'ReportSansBold', fontSize = 8, leading = 11, textColor = white),
        }

        for key, style in self.styles.items():
            style.textColor = HexColor(self.palette.accent if key == 'title' else self.palette.ink) if key != 'header' else white

        self.story = []
        self.icons = {}

    def write(self, path: Path, content: ReportContent, *, profile: str | None = None) -> None:
        self.profile = profile

        # ReportLab shares its font registry; one TTFont must not be used
        # concurrently by documents in different threads.
        while not self.FONT_LOCK.acquire(timeout = .1):
            self.control.check()

        try:
            self.control.check()
            fonts = RuntimeResources.resource_root() / 'reports/fonts'

            if 'ReportSans' not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont('ReportSans', str(fonts / 'DejaVuSans.ttf')))
                pdfmetrics.registerFont(TTFont('ReportSansBold', str(fonts / 'DejaVuSans-Bold.ttf')))

            if profile is not None:
                from poe_log_analyze.stages.rendering.pdf.BasicPdfChapter import BasicPdfChapter
                BasicPdfChapter(self).compose(content)

            if profile != 'basic':
                if profile == 'extended':
                    self.new_page('portrait')

                self.compose(content)

            document = PdfDocument(path, self.catalogue, self.control, pagesize = A4, palette = self.palette,
                                   progress_label = 'PDF: ' + self.catalogue.text('basic.' + profile) if profile else 'PDF',
                                   leftMargin = 42, rightMargin = 42, topMargin = 38, bottomMargin = 42,
                                   title = self.catalogue.text('pdf.title'), author = 'PoE Log Analyze',
                                   subject = self.catalogue.text('pdf.scope'), lang = self.catalogue.language,
                                   invariant = 1, pageCompression = 1)
            document.build(self.story)
            self.control.check()
        finally:
            self.FONT_LOCK.release()

    def paragraph(self, text, style = 'body'):
        self.control.check()
        # Never interpret log values as ReportLab markup.
        safe = escape(str(text), quote = False).replace('\n', '<br/>')

        return Paragraph(safe, self.styles[style])

    def text(self, value, style = 'body'):
        self.story.append(self.paragraph(value, style))

    def heading(self, key, page = False):
        self.control.report('PDF: prepare section · ' + self.catalogue.text(key), force = True)

        if page:
            self.new_page('portrait')

        self.text(self.catalogue.text(key), 'heading')

    def new_page(self, orientation):
        self.story.extend([NextPageTemplate(orientation), PageBreak()])

    def zone_name(self, row):
        """Fit the icon into a row with normal line spacing and table padding."""

        base = (RuntimeResources.resource_root() / 'site/static').resolve()
        icon = (base / row.get('icon', '')).resolve()
        name = escape(str(row['name']), quote = False)

        if icon.is_relative_to(base / 'images') and icon.is_file() and icon.suffix == '.png':
            markup = f'<img src="{escape(str(icon), quote=True)}" width="14" height="14" valign="middle"/> '
        else:
            markup = '◇ '

        paragraph = Paragraph(markup + name, self.styles['cell'])

        for fragment in paragraph.frags:
            definition = getattr(fragment, 'cbDefn', None)

            if definition is not None and definition.kind == 'img':
                definition.image = self.icon_image(icon)

        return paragraph

    def icon_image(self, path):
        """Contrasting in-memory background; leave game files and the temporary directory unchanged."""

        if path not in self.icons:
            with Image.open(path) as source:
                rgba = source.convert('RGBA')
                image = Image.new('RGB', rgba.size, '#203744')
                image.paste(rgba, mask = rgba.getchannel('A'))

            self.icons[path] = ImageReader(image)

        return self.icons[path]

    def table(self, headers, rows, widths, backgrounds = None):
        data = [[self.paragraph(self.catalogue.text(key), 'header') for key in headers]]

        for row in rows:
            self.control.check()
            data.append([value if isinstance(value, Paragraph) else self.paragraph(value, 'cell') for value in row])

        if len(data) == 1:
            self.text(self.catalogue.text('pdf.no_data'))
            return

        table = LongTable(data, colWidths = widths, repeatRows = 1, hAlign = 'LEFT', splitInRow = 1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor(self.palette.header)),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor(self.palette.background), HexColor(self.palette.surface)]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LINEBELOW', (0, 0), (-1, 0), .5, HexColor(self.palette.header)),
        ]))

        if backgrounds:
            table.setStyle(TableStyle([('BACKGROUND', (1, index), (1, index), color)
                                      for index, color in enumerate(backgrounds, 1)]))

        self.story.extend([table, Spacer(1, 10)])

    def zone_table(self, rows):
        self.table(['activities.zone', 'stats.visits', 'stats.measured_time', 'stats.unmeasured_visits'],
                   ((self.zone_name(r), r['visits'], r['duration'], r['incomplete_visits']) for r in rows),
                   [250, 60, 105, 95])

    def compose(self, content):
        data, views = content.analysis, content.views
        summary, observations = views['statistics_summary'], views['period_log_observations']
        tr = self.catalogue.text
        self.text(tr('pdf.title'), 'title')
        self.text(views['report_period']['label'] + ' · ' + data['timezone'])

        if views['report_period']['active']:
            self.text(tr('period.note'))

        self.text(data['state'] + ' · ' + str(data['percentage']))
        self.text(tr('pdf.scope'))
        self.text(tr('ui.total_observed_playtime') + ' ' + content.activity['duration'], 'heading')
        self.text(tr('ui.from_area_entry_to_disconnection_at_end_of_file_or_a_gap_over_30_minutes_time_is_coun'))
        self.text(tr('ui.incomplete_intervals') + ' ' + str(content.activity['incomplete']))
        self.text(tr('stats.map_count') + ': ' + str(summary['maps']['count']))
        self.text(tr('stats.measured_time') + ': ' + summary['maps']['duration'])
        self.text(tr('stats.unmeasured_visits') + ': ' + str(summary['maps']['incomplete_visits']))
        self.text(tr('observations.loading') + ': ' + observations['loading_duration'])
        self.text(tr('observations.identified') + ': ' + str(observations['items_identified']))
        self.text(tr('observations.note'))

        if views['period_comparison']['enabled']:
            self.comparison(views['period_comparison'])

        self.heading('stats.by_map_type', page = True)
        self.text(tr('stats.map_note'))
        self.table(['stats.map_type', 'stats.map_count', 'stats.visits', 'stats.measured_time', 'stats.unmeasured_visits'],
                   ((self.zone_name(r), r['count'], r['visits'], r['duration'], r['incomplete_visits'])
                    for r in summary['map_types']), [175, 85, 70, 90, 90])
        self.heading('map_observations.title')
        self.text(tr('map_observations.note'))
        self.text(tr('period.mechanics' if views['report_period']['active'] else 'map_observations.method'))
        self.table(['map_observations.kind', 'map_observations.map_count'],
                   ((tr(row['label_key']), row['count']) for row in views['map_observations']['rows']), [370, 140])
        self.heading('page.playtime', page = True)
        self.afk(views['afk']['summary'], views['map_pace']['summary'])
        daily = views['daily_playtime']

        if daily['days']:
            self.story.append(self.charts.playtime(daily))

        self.text(tr('pdf.heat_note'))
        self.story.append(self.charts.playtime_legend())
        self.table(['pdf.day', 'stats.measured_time', 'afk.marked', 'afk.remaining_duration'],
                   ((day['date'], day['duration'], views['afk']['by_date'][day['date']]['afk_duration'],
                     views['afk']['by_date'][day['date']]['remaining_duration']) for day in daily['days']), [120, 130, 110, 150],
                   backgrounds = [self.charts.day_color(day['seconds'], self.palette.dark) for day in daily['days']])

        if self.profile is None:
            self.weekly_intensity(views['weekly_intensity'])

        self.sessions(views['sessions'], views['afk'])
        self.loading(views['loading'])
        self.heading('stats.all_zones', page = True)
        self.text(tr('stats.zone_note'))
        self.text(tr('stats.time_note'))
        self.zone_table(summary['zones'])
        self.activities(views['activities'], views['report_period']['label'] if views['report_period']['active'] else None)
        self.characters(views['characters'], views['report_period']['active'])
        self.heading('stats.daily_zones', page = True)
        self.text(tr('stats.daily_zone_note'))

        for date, day in sorted(views['daily_areas']['by_date'].items()):
            self.control.check()

            if day['zones']:
                self.text(day['label'], 'subheading')
                self.zone_table(day['zones'])

    def loading(self, model):
        tr = self.catalogue.text
        self.heading('page.loading', page = True)
        self.text(tr('loading.note'))
        summary = model['summary']
        keys = ['count', 'total', 'mean', 'median', 'max']
        self.table(['loading.' + key for key in keys],
                   [[summary[key] for key in keys]], [90, 120, 100, 100, 100])
        self.text(tr('loading.pdf_note'))
        self.text(tr('loading.area_note'))
        self.table(['activities.zone', *['loading.' + key for key in keys]],
                   ((row['area'], *(row[key] for key in keys)) for row in model['areas'][:15]),
                   [160, 65, 85, 65, 65, 70])

    def afk(self, summary, pace):
        tr = self.catalogue.text
        self.heading('afk.title')
        self.text(tr('afk.note'))
        self.table(['afk.duration', 'afk.afk_duration', 'afk.remaining_duration'],
                   [[summary[key] for key in ('duration', 'afk_duration', 'remaining_duration')]], [170, 170, 170])
        self.table(['afk.category', 'stats.measured_time', 'afk.marked', 'afk.remaining_duration'],
                   ((tr('afk.' + row['code']), row['duration'], row['afk_duration'], row['remaining_duration'])
                    for row in summary['categories']), [170, 110, 100, 130])
        self.text(tr('afk.zone_note'))
        self.text(tr('pace.rate_label') + ': ' + pace['rate_label'] + ' · ' +
                  tr('afk.rate_without') + ': ' + pace['rate_without_afk_label'])
        self.text(tr('afk.rate_note'))

    def sessions(self, model, afk):
        tr = self.catalogue.text
        self.heading('sessions.title', page = True)
        self.text(tr('sessions.pdf_note'))
        self.text(tr('sessions.method'))
        self.text(tr('sessions.count') + ': ' + str(model['count']) + ' · ' + model['duration'])
        rows = []

        for session in model['rows']:
            self.control.check()
            status = session['ending_label']

            if session['clipped']:
                status += ' · ' + tr('sessions.clipped')

            if session['branched']:
                status += ' · ' + tr('sessions.branched')

            rows.append((session['start'] + '\n' + session['end'], session['duration'],
                         afk['by_session'][session['id']]['afk_duration'],
                         session['statistics']['maps']['count'], session['observations']['loading_duration'], status))

        self.table(['sessions.bounds', 'sessions.time', 'afk.marked', 'nav.maps', 'sessions.loading', 'field.status'],
                   rows, [125, 75, 60, 45, 70, 135])

        if any(session['branched'] for session in model['rows']):
            self.text(tr('sessions.branches_note'))

    def comparison(self, model):
        tr = self.catalogue.text
        self.heading('comparison.title', page = True)
        self.text(tr('comparison.a') + ': ' + model['a']['period']['label'])
        self.text(tr('comparison.b') + ': ' + model['b']['period']['label'] + ' · ' + model['timezone'])
        self.text(tr('comparison.intro'))

        if model['overlap']:
            self.text(tr('comparison.overlap'))

        self.text(tr('comparison.missing'))
        self.text(tr('comparison.method'))

        for section in model['sections']:
            self.control.check()
            self.text(section['title'], 'heading')
            self.text(tr('comparison.' + section['code'] + '_note'))

            if section['code'] == 'mechanics':
                self.text(tr('comparison.denominators', a = model['a']['observation_maps'], b = model['b']['observation_maps']))

            rows = []

            for row in section['rows']:
                a, b = row['a_text'], row['b_text']

                if section['code'] == 'mechanics':
                    a += f"\n{row['a_count']} / {model['a']['observation_maps']}"
                    b += f"\n{row['b_count']} / {model['b']['observation_maps']}"

                rows.append((row['label'], a, b, row['delta_text'], row['change_text']))

            self.table(['comparison.metric', 'comparison.column_a', 'comparison.column_b',
                        'comparison.delta', 'comparison.change'], rows, [180, 85, 85, 85, 75])

        self.text(tr('comparison.incomplete', a = model['a']['incomplete_play_intervals'], b = model['b']['incomplete_play_intervals'],
                     za = model['a']['incomplete_zone_visits'], zb = model['b']['incomplete_zone_visits']))

    def activities(self, model, period_label = None):
        tr = self.catalogue.text
        self.heading('page.activities', page = True)
        self.text(tr('activities.intro'))
        self.text(tr('activities.scope'))
        rows = []

        for group in model['groups']:
            total = group['totals']
            rows.append((tr('activities.' + group['code']), total['visits'], total['duration']))

            if len(group['children']) > 1:
                for child in group['children']:
                    total = child['totals']
                    rows.append(('↳ ' + tr('activities.' + child['code']), total['visits'], total['duration']))

        self.table(['activities.group', 'stats.visits', 'activities.duration'], rows, [330, 70, 110])

        if model['periods']:
            self.new_page('landscape')
            self.heading('activities.timeline')
            self.text((period_label or tr('activities.all_time')) + ' · ' + model['timezone'], 'subheading')
            self.text(tr('pdf.activity_overview_note'))
            self.story.append(self.charts.activities(model, self.charts.activity_overview(model)))

            for period in self.charts.activity_periods(model):
                self.control.check()
                self.new_page('landscape')
                self.heading('activities.timeline')
                self.text(period['label'] + ' · ' + model['timezone'], 'subheading')
                self.text(tr('pdf.activity_note'))
                self.story.append(self.charts.activities(model, period))
        else:
            self.text(tr('activities.empty'))

    def characters(self, model, limited = False):
        tr = self.catalogue.text
        characters = [character for character in model['characters'] if character['events']]
        self.heading('page.characters', page = True)
        self.text(tr('characters.note'))
        self.text(tr('characters.delta_note'))

        if limited:
            self.text(tr('period.delta'))

        if not characters:
            self.text(tr('characters.empty'))

        for character in characters:
            self.control.check()
            self.text(character['name'] + ' · ' + ', '.join(character['classes']), 'subheading')
            self.text(tr('pdf.character_note'))

            for chart in character['charts']:
                if chart['kind'] != 'all':
                    self.text(tr('characters.' + chart['kind']), 'subheading')

                if chart['events']:
                    self.story.append(self.charts.character(chart))
                else:
                    self.text(tr('characters.range_empty'))

            self.table(['characters.date_time', 'field.level', 'field.class', 'characters.delta'],
                       ((event['label'], event['level'], event['class'],
                         event['delta_duration'] + (' · ' + tr('characters.from_level', level = event['delta_from_level'])
                         if event['delta_from_level'] is not None else ''))
                        for event in character['events']), [145, 55, 135, 175])

    def weekly_intensity(self, model):
        first = len(self.story)
        self.heading('intensity.title')
        self.text(self.catalogue.text('intensity.note'))
        self.story.append(WeeklyIntensityChart(model, self.catalogue, self.control, self.palette))
        self.text(self.catalogue.text('intensity.scale', maximum = model['maximum_duration']))
        self.story[first:] = [KeepTogether(self.story[first:])]
