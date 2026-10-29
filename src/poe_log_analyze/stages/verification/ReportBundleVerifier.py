from dataclasses import asdict
from pathlib import Path

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.runtime.JsonFiles import JsonFiles
from poe_log_analyze.runtime.RuntimeResources import RuntimeResources
from poe_log_analyze.runtime.CodeProvenance import CodeProvenance

from poe_log_analyze.stages.preparation.AnalysisValidator import AnalysisValidator
from poe_log_analyze.stages.rendering.BasicReportWriter import BasicReportWriter
from poe_log_analyze.stages.rendering.ReportTemplates import ReportTemplates
from poe_log_analyze.stages.rendering.RenderedReport import RenderedReport
from poe_log_analyze.stages.verification.LocalHTML import LocalHTML
from poe_log_analyze.stages.verification.LocalResources import LocalResources


class ReportBundleVerifier:
    """Verify all selected outputs and shared local links before replacement."""

    @staticmethod
    def verify(rendered: RenderedReport, control: ExecutionContext) -> Path:
        root = rendered.directory
        outputs = rendered.outputs
        expected_roots = {'public', 'project'}

        for profile in ('basic', 'extended'):
            if getattr(outputs, profile):
                expected_roots.add(profile)

        if outputs.basic_pdf or outputs.extended_pdf:
            expected_roots.add('pdf')

        if {path.name for path in root.iterdir()} != expected_roots:
            raise ValueError('Invalid selected-report inventory')

        if outputs.basic:
            public = root / 'basic/public'
            expected = set(BasicReportWriter.PAGES) | set(BasicReportWriter.ASSETS) | {'images/activity-overview.png'}
            actual = {path.relative_to(public).as_posix() for path in public.rglob('*') if path.is_file()}

            if actual != expected:
                raise ValueError('Invalid basic-report inventory')

        pdfs = {}

        for profile in ('basic', 'extended'):
            if not getattr(outputs, profile + '_pdf'):
                continue

            control.report('Verify PDF: ' + ('basic' if profile == 'basic' else 'extended'), force = True)
            pdf = root / 'pdf' / profile / 'report.pdf'

            with pdf.open('rb') as stream:
                header = stream.read(8)
                stream.seek(max(0, pdf.stat().st_size - 32))
                ending = stream.read()

            if not header.startswith(b'%PDF-') or not ending.rstrip().endswith(b'%%EOF'):
                raise ValueError('The PDF report is incomplete')

            pdfs[profile] = {'path': pdf.relative_to(root).as_posix(), 'content_version': '14', 'theme': 'dark' if rendered.pdf_dark else 'light',
                             'sha256': AnalysisValidator.file_hash(pdf, control)}

        resources = LocalResources(root)
        script_roots = tuple(root / profile / 'public' for profile in ('', 'basic', 'extended'))
        pages = [root / 'public/index.html']

        for profile in ('basic', 'extended'):
            if getattr(outputs, profile):
                pages.extend((root / profile / 'public').rglob('*.html'))

        checkers = {}

        for number, page in enumerate(pages):
            control.report('Verify HTML: ' + page.relative_to(root).as_posix(), number, len(pages),
                           unit = 'pages', force = True)
            html = page.read_text(encoding = 'utf-8')

            if f'lang="{rendered.language}"' not in html or '[i18n]' in html:
                raise ValueError('Invalid selected-report language')

            checker = LocalHTML(resources, page, script_roots = script_roots)
            checker.feed(html)
            checker.close()
            checkers[checker.page] = checker

        control.report('Verify selected-report links', force = True)

        for checker in checkers.values():
            for path, anchor in checker.anchors:
                control.check()

                if path not in checkers or anchor not in checkers[path].ids:
                    raise ValueError('The link does not match the selected report page')

        build = RuntimeResources.build_metadata()
        artifacts = {}
        files = sorted(path for path in root.rglob('*') if path.is_file())

        for number, path in enumerate(files):
            name = path.relative_to(root).as_posix()
            control.report('Checksum: ' + name, number, len(files), unit = 'files')
            artifacts[name] = AnalysisValidator.file_hash(path, control)

        control.report('Checksums verified', len(files), len(files), unit = 'files', force = True)
        resources_root = RuntimeResources.resource_root()
        JsonFiles.write_json(root / 'report-manifest.json', {
            'report_schema_version': '40', 'image_theme': 'dark' if rendered.pdf_dark else 'light', 'report_language': rendered.language,
            'report_period': rendered.content.views['report_period'], 'outputs': asdict(outputs), 'pdfs': pdfs,
            'comparison_period': rendered.content.views['period_comparison'].get('a', {}).get('period'),
            'sources': rendered.content.analysis.get('sources', []),
            'input_sha256': rendered.content.analysis['input_sha256'],
            'renderer': {'name': 'Jinja2', 'versions': rendered.renderer_versions},
            'generator_files_sha256': build['code']['files_sha256'] if build else CodeProvenance.source_hashes(),
            'templates_sha256': {name: AnalysisValidator.file_hash(resources_root / name, control) for name in ReportTemplates.files()},
            'artifacts_sha256': artifacts,
        })
        control.check()

        return root / 'public/index.html'
