from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate

from poe_log_analyze.stages.rendering.ReportPalette import ReportPalette


class PdfDocument(BaseDocTemplate):
    """Check cancellation during layout and print localized page numbers."""

    def __init__(self, path, catalogue, control, *, progress_label = 'PDF', palette = None, **options):
        super().__init__(str(path), **options)

        self.palette = palette or ReportPalette()
        self.catalogue = catalogue
        self.control = control
        self.progress_label = progress_label
        templates = []

        for name, size in (('portrait', A4), ('landscape', landscape(A4))):
            frame = Frame(self.leftMargin, self.bottomMargin,
                          size[0] - self.leftMargin - self.rightMargin,
                          size[1] - self.topMargin - self.bottomMargin,
                          leftPadding = 0, rightPadding = 0, topPadding = 0, bottomPadding = 0)
            templates.append(PageTemplate(id = name, frames = [frame], pagesize = size, onPage = self.footer))

        self.addPageTemplates(templates)

    def beforePage(self):
        self.control.report(self.progress_label + ': page layout', processed = self.page - 1, unit = 'pages')

    def afterPage(self):
        self.control.report(self.progress_label + ': page layout', processed = self.page, unit = 'pages', force = True)

    def afterFlowable(self, flowable):
        self.control.check()

    def footer(self, canvas, document):
        self.control.check()
        canvas.saveState()
        canvas.setFillColor(HexColor(self.palette.background))
        canvas.rect(0, 0, *document.pageTemplate.pagesize, fill = 1, stroke = 0)
        canvas.setFont("ReportSans", 8)
        canvas.setFillColor(HexColor(self.palette.muted))
        canvas.drawString(self.leftMargin, 23, self.catalogue.text("pdf.title"))
        canvas.drawRightString(document.pageTemplate.pagesize[0] - self.rightMargin, 23,
                               self.catalogue.text("pdf.page", number = document.page))
        canvas.restoreState()
