import shutil

from pathlib import Path
from datetime import datetime
from typing import Any

from importlib import metadata

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.runtime.JsonFiles import JsonFiles
from poe_log_analyze.runtime.RuntimeResources import RuntimeResources

from poe_log_analyze.stages.composition.ReportContent import ReportContent
from poe_log_analyze.stages.composition.localization.TranslationCatalogue import TranslationCatalogue
from poe_log_analyze.stages.rendering.HtmlPageWriter import HtmlPageWriter
from poe_log_analyze.stages.rendering.LogHistoryReader import LogHistoryReader
from poe_log_analyze.stages.rendering.LogHistoryJsonWriter import LogHistoryJsonWriter
from poe_log_analyze.stages.rendering.RenderedReport import RenderedReport
from poe_log_analyze.stages.rendering.ReportTemplates import ReportTemplates
from poe_log_analyze.stages.rendering.SearchIndexWriter import SearchIndexWriter


class ExtendedReportWriter:
    """Render HTML with Jinja2 inside the workspace; verification and publication follow later."""

    def write(self, output: Path, content: ReportContent, control: ExecutionContext,
                report_language: str, *, generate_pdf: bool = False, basic_block: bool = False,
                pdf_href: str | None = None, dark: bool = False) -> RenderedReport:

        root = RuntimeResources.resource_root()
        catalogue = TranslationCatalogue(report_language, root)
        data = content.analysis
        timeline, maps, statistics = content.timeline, content.maps, content.statistics
        activity, flow = content.activity, content.flow
        download = pdf_href if pdf_href is not None else ('report.pdf' if generate_pdf else '')
        versions = {name: metadata.version(name) for name in ("Jinja2", "MarkupSafe", "Markdown")}
        target = output
        project, public = target / "project", target / "public"

        for folder in ("layouts", "data"):
            (project / folder).mkdir(parents = True, exist_ok = True)

        copies = {}
        copies.update({name: name.removeprefix("site/") for name in ReportTemplates.files() if name.startswith("site/")})

        control.report('Extended HTML: copy resources', total = len(copies), unit = 'resources', force = True)

        for number, (source, dest) in enumerate(copies.items(), 1):
            control.check()
            destination = public / dest.removeprefix("static/") if dest.startswith("static/") else project / dest
            destination.parent.mkdir(parents = True, exist_ok = True)
            shutil.copyfile(root / source, destination)
            control.report('Extended HTML: copy resources', number, len(copies), unit = 'resources')

        control.report('Extended HTML: copy resources', len(copies), len(copies), unit = 'resources', force = True)

        JsonFiles.write_json(project / "data" / "analysis.json", data)
        JsonFiles.write_json(project / "data" / "timeline.json", timeline)
        JsonFiles.write_json(project / "data" / "maps.json", maps)
        JsonFiles.write_json(project / "data" / "map_statistics.json", statistics)
        JsonFiles.write_json(project / "data" / "activity.json", activity)
        JsonFiles.write_json(project / "data" / "map_flow.json", flow)
        specification = catalogue.specification()
        JsonFiles.write_json(project / "data/log_specification.json", specification)

        for name, model in content.views.items():
            control.report('Save report data: ' + name, force = True)

            if name == 'events':
                LogHistoryJsonWriter.write(project / 'data/events.json', model, content.event_rows, control)
            else:
                JsonFiles.write_json(project / 'data' / (name+'.json'), model)

        models = {"analysis": data, "timeline": timeline, "maps": maps, "map_statistics": statistics,
                  "activity": activity, "map_flow": flow, "log_specification": specification,
                  **content.views, "pdf_enabled": bool(download), "pdf_href": download,
                  "basic_block": basic_block, "issue_rows": self.issue_rows(content.views['issues'])}
        writer = HtmlPageWriter(root, project, report_language, models, catalogue, control, label = 'Extended HTML')
        control.report('HTML rendering', force = True)
        writer.write("index.html", "reports/history.md", title = catalogue.text("page.playtime"),
                     template = "history/playtime.html", root = "./", menu = "playtime")

        if content.views['period_comparison']['enabled']:
            writer.write('comparison/index.html', 'reports/history.md', title = catalogue.text('comparison.title'),
                         template = 'statistics/comparison.html', root = '../', menu = 'comparison')

        for route, layout in (('pace', 'pace'), ('loading', 'loading'), ('activities', 'activities'), ('characters', 'characters'), ('conversations', 'conversations'), ('areas', 'areas'),
                              ('playtime', 'playtime'), ('technical/issues', 'issues')):
            writer.write(route+'/index.html', 'reports/history.md', title = catalogue.text("page." + layout),
                         template = 'history/' + layout + '.html', root = '../' * (route.count('/')+1), menu = layout)

        search = SearchIndexWriter(public, data['timezone'], {row['line'] for row in models['issue_rows']}, control)

        for page in LogHistoryReader.pages(content.event_rows, content.views['events'], control):
            control.check()
            search.add(page)
            writer.write('events/' + page['path'], 'reports/history.md', title = catalogue.text('page.events'),
                         template = 'history/events.html', root = '../', menu = 'events', page = page)
            del page

        search_model = search.result()
        JsonFiles.write_json(project / 'data/search-index.json', search_model)
        writer.write('search/index.html', 'reports/history.md', title = catalogue.text('search.title'),
                     template = 'history/search.html', root = '../', menu = 'search', search = search_model)

        writer.write('sessions/index.html', 'reports/history.md', title = catalogue.text('sessions.title'),
                     template = 'sessions/index.html', root = '../', menu = 'sessions')
        writer.write('sessions/compare/index.html', 'reports/history.md', title = catalogue.text('session_compare.title'),
                     template = 'sessions/compare.html', root = '../../', menu = 'sessions')
        writer.write('explore/index.html', 'reports/history.md', title = catalogue.text('explorer.title'),
                     template = 'history/map-explorer.html', root = '../', menu = 'explore')

        for page in content.views['analytics_navigation']['pages']:
            writer.write(page['path'], 'reports/history.md', title = catalogue.text(page['label_key']),
                         template = 'history/analytics.html', root = '../../', menu = 'analytics', analytics = page['id'])

        for panel in content.views['weekly_pace']['panels']:
            control.check()
            writer.write(panel['path'], 'reports/history.md', title = catalogue.text('weekly.title'),
                         template = 'history/weekly-pace.html', root = '../' * panel['path'].count('/'), menu = 'pace', panel = panel)

        for area in content.views['area_details']['pages']:
            control.check()
            writer.write(area['path'], 'reports/history.md', title = area['name'], template = 'history/area-detail.html',
                         root = '../../', menu = 'summary' if area['kind_code'] == 'map' else 'areas', area = area)

        writer.write('maps/compare/index.html', 'reports/history.md', title = catalogue.text('run_compare.title'),
                     template = 'history/map-run-comparison.html', root = '../../', menu = 'statistics')

        for run in content.views['map_run_details']['pages']:
            control.check()
            writer.write(run['path'], 'reports/history.md', title = run['name'], template = 'history/map-run.html',
                         root = '../../../', menu = 'statistics', run = run)

        for session in content.views['sessions']['rows']:
            control.check()
            writer.write(session['path'], 'reports/history.md', title = catalogue.text('sessions.detail'),
                         template = 'sessions/detail.html', root = '../../', menu = 'sessions', session = session)

        writer.write("maps/index.html", "reports/map-statistics.md", title = catalogue.text("page.maps"),
                template = "statistics/overview.html", root = "../", menu = "statistics")
        writer.write("statistics/index.html", "reports/history.md", title = catalogue.text("page.statistics"),
                template = "statistics/summary.html", root = "../", menu = "summary")

        for group in content.views['map_observations']['groups']:
            if group['count']:
                control.check()
                writer.write(f"statistics/observations/{group['code']}/index.html", 'reports/history.md',
                             title = catalogue.text('map_observations.detail_title', kind = catalogue.text(group['label_key'])),
                             template = 'statistics/observations.html', root = '../../../', menu = 'summary', observation = group)

        writer.write("flow/index.html", "reports/map-flow.md", title = catalogue.text("page.flow"),
                template = "statistics/flow.html", root = "../", menu = "flow")
        writer.write("technical/index.html", "reports/coverage.md", title = catalogue.text("page.coverage"),
                template = "technical/coverage.html", root = "../", menu = "coverage")
        writer.write("technical/specification/index.html", "reports/log-specification.md", title = catalogue.text("page.specification"),
                template = "technical/specification.html", root = "../../", menu = "specification")
        writer.write("technical/maps/index.html", "reports/maps.md", title = catalogue.text("page.map_details"),
                template = "maps/overview.html", root = "../../", menu = "maps")
        writer.write("technical/timeline/index.html", "reports/timeline.md", title = catalogue.text("page.timeline"),
                template = "timeline/overview.html", root = "../../", menu = "timeline")

        for day in content.views['daily_areas']['by_date'].values():
            control.check()
            writer.write(f"maps/{day['date']}/index.html", "reports/map-statistics-day.md", title = catalogue.text("page.day_statistics", day = day["label"]),
                    template = "statistics/day.html", day = day["date"], root = "../../", menu = "statistics")

        for index, day in enumerate(maps["days"]):
            control.check()
            label = catalogue.text("date.entry_unknown") if day["date"] == "undated" else day["date"]
            writer.write(f"technical/maps/{day['date']}/index.html", "reports/maps-day.md",
                         title = catalogue.text("page.map_day", day = label), template = "maps/day.html",
                         day = day["date"], root = "../../../", menu = "maps",
                         previous_day = maps["days"][index - 1]["date"] if index else None,
                         next_day = maps["days"][index + 1]["date"] if index + 1 < len(maps["days"]) else None)

        for day in timeline["days"]:
            control.check()
            writer.write(f"technical/timeline/{day['date']}/index.html", "reports/timeline-day.md",
                         title = catalogue.text("page.timeline_day", day = day["label"]), template = "timeline/day.html",
                         day = day["date"], root = "../../../", menu = "timeline")

        if basic_block:
            from poe_log_analyze.stages.rendering.BasicReportWriter import BasicReportWriter
            BasicReportWriter().write(target, content, catalogue, control, prefix = 'basic/', pdf_href = download, dark = dark)

        control.check()

        if generate_pdf:
            from poe_log_analyze.stages.rendering.pdf.PdfReportWriter import PdfReportWriter
            control.report('Build PDF', force = True)
            PdfReportWriter(catalogue, control, dark = dark).write(public / "report.pdf", content)
            versions["reportlab"] = metadata.version("reportlab")

        control.check()

        return RenderedReport(target, content, report_language, versions, pdf = generate_pdf, search = search_model, basic_block = basic_block, pdf_dark = dark)

    @staticmethod
    def issue_rows(issues: dict[str, Any]) -> list[dict[str, Any]]:
        """Flatten groups into the shared chronology; leave unknown times at the end."""

        rows = [dict(event, category = group['category'], code = group['code'], title = group['title'])
                for group in issues['groups'] for event in group['events']]
        rows.sort(key = lambda row: (not bool(row['timestamp']),
                  datetime.fromisoformat(row['timestamp']).timestamp() if row['timestamp'] else 0,
                  row['line']))

        return rows
