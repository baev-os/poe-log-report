import shutil

from pathlib import Path

from poe_log_analyze.runtime.RuntimeResources import RuntimeResources
from poe_log_analyze.stages.rendering.HtmlPageWriter import HtmlPageWriter
from poe_log_analyze.stages.rendering.ActivityOverviewImage import ActivityOverviewImage


class BasicReportWriter:
    """Five simple pages; shared basic section for standalone and complete sites."""

    PAGES = ('index.html', 'characters/index.html', 'maps/index.html',
             'calendar/index.html', 'conversations/index.html')
    STYLE_ASSETS = ('vendor/bootstrap.min.css', 'style.css', 'BasicReport.css', 'ReportTheme.js')
    ASSETS = STYLE_ASSETS + ('BasicReport.js', 'ChartTooltip.css', 'ChartTooltip.js')
    TEMPLATES = ('base', 'graphs', 'characters', 'maps', 'calendar', 'conversations', 'weekly-intensity')

    def write(self, target, content, catalogue, control, *, prefix = '', pdf_href = '', dark = False) -> None:
        resources = RuntimeResources.resource_root()
        project, public = target / 'project', target / 'public'

        for name in self.TEMPLATES:
            destination = project / 'layouts/basic' / (name + '.html')
            destination.parent.mkdir(parents = True, exist_ok = True)
            shutil.copyfile(resources / 'site/layouts/basic' / (name + '.html'), destination)

        self.copy_assets(public, resources, self.ASSETS, control)
        control.report('Complete special-area chart: high-resolution image', force = True)
        ActivityOverviewImage.write(public / prefix / 'images/activity-overview.png', content.views['basic']['activities'], catalogue, control, dark = dark)
        data = {'basic': content.views['basic'], 'basic_block': bool(prefix), 'pdf_href': pdf_href}
        writer = HtmlPageWriter(resources, project, catalogue.language, data, catalogue, control,
                                label = 'Basic section of extended HTML' if prefix else 'Basic HTML')

        for page, kind in zip(self.PAGES, ('graphs', 'characters', 'maps', 'calendar', 'conversations')):
            control.check()
            writer.write(prefix + page, 'reports/history.md', template = 'basic/' + kind + '.html',
                         title = catalogue.text('basic.' + kind), kind = kind,
                         root = '../' * (prefix + page).count('/'),
                         basic_root = './' if page == 'index.html' else '../')

    @staticmethod
    def copy_assets(public, resources, names, control) -> None:
        for name in names:
            control.check()
            destination = public / name
            destination.parent.mkdir(parents = True, exist_ok = True)
            shutil.copyfile(resources / 'site/static' / name, destination)
