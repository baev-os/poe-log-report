import shutil

from importlib import metadata
from pathlib import Path

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.request.ReportOutputs import ReportOutputs

from poe_log_analyze.runtime.JsonFiles import JsonFiles
from poe_log_analyze.runtime.RuntimeResources import RuntimeResources

from poe_log_analyze.stages.composition.ReportContent import ReportContent
from poe_log_analyze.stages.composition.localization.TranslationCatalogue import TranslationCatalogue
from poe_log_analyze.stages.rendering.BasicReportWriter import BasicReportWriter
from poe_log_analyze.stages.rendering.ExtendedReportWriter import ExtendedReportWriter
from poe_log_analyze.stages.rendering.HtmlPageWriter import HtmlPageWriter
from poe_log_analyze.stages.rendering.RenderedReport import RenderedReport


class RenderReport:
    """Assemble selected documents in one temporary workspace before joint verification."""

    def execute(self, output: Path, content: ReportContent, control: ExecutionContext,
                report_language: str, *, generate_pdf: bool = False,
                outputs: ReportOutputs | None = None, pdf_dark: bool = False) -> RenderedReport:

        if outputs is None:
            return ExtendedReportWriter().write(output, content, control, report_language, generate_pdf = generate_pdf, dark = pdf_dark)

        resources = RuntimeResources.resource_root()
        catalogue = TranslationCatalogue(report_language, resources)
        versions = {name: metadata.version(name) for name in ('Jinja2', 'MarkupSafe', 'Markdown')}
        children = []
        control.report('Build selected reports', force = True)

        if outputs.basic:
            control.report('Basic report: prepare HTML', force = True)
            BasicReportWriter().write(output / 'basic', content, catalogue, control,
                                     pdf_href = '../../pdf/basic/report.pdf' if outputs.basic_pdf else '', dark = pdf_dark)

        if outputs.extended:
            control.report('Extended report: prepare HTML', force = True)
            children.append(ExtendedReportWriter().write(output / 'extended', content, control,
                report_language, basic_block = True,
                pdf_href = '../../pdf/extended/report.pdf' if outputs.extended_pdf else '', dark = pdf_dark))

        for profile, enabled in (('basic', outputs.basic_pdf), ('extended', outputs.extended_pdf)):
            if not enabled:
                continue

            from poe_log_analyze.stages.rendering.pdf.PdfReportWriter import PdfReportWriter
            control.report('Build PDF: ' + catalogue.text('basic.' + profile), force = True)
            path = output / 'pdf' / profile / 'report.pdf'
            path.parent.mkdir(parents = True, exist_ok = True)
            PdfReportWriter(catalogue, control, dark = pdf_dark).write(path, content, profile = profile)
            versions['reportlab'] = metadata.version('reportlab')

        project = output / 'project'
        control.report('Prepare document selection page', force = True)
        (project / 'layouts/basic').mkdir(parents = True, exist_ok = True)
        (output / 'public').mkdir(parents = True, exist_ok = True)
        shutil.copyfile(resources / 'site/layouts/basic/selection.html', project / 'layouts/basic/selection.html')
        BasicReportWriter.copy_assets(output / 'public', resources, BasicReportWriter.STYLE_ASSETS, control)
        (project / 'data').mkdir(parents = True, exist_ok = True)
        JsonFiles.write_json(project / 'data/basic.json', content.views['basic'])
        options = {name: getattr(outputs, name) for name in ('basic', 'basic_pdf', 'extended', 'extended_pdf')}
        writer = HtmlPageWriter(resources, project, report_language,
                                {'basic': content.views['basic'], 'outputs': options}, catalogue, control)
        writer.write('index.html', 'reports/history.md', template = 'basic/selection.html',
                     title = catalogue.text('basic.selection'), root = './')
        control.check()

        return RenderedReport(output, content, report_language, versions, outputs = outputs,
                              children = tuple(children), pdf_dark = pdf_dark)
