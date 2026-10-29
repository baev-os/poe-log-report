from pathlib import Path

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.runtime.CodeProvenance import CodeProvenance
from poe_log_analyze.runtime.JsonFiles import JsonFiles
from poe_log_analyze.runtime.RuntimeResources import RuntimeResources

from poe_log_analyze.stages.composition.MapStatisticsBuilder import MapStatisticsBuilder
from poe_log_analyze.stages.composition.TimelineBuilder import TimelineBuilder
from poe_log_analyze.stages.composition.localization.TranslationCatalogue import TranslationCatalogue
from poe_log_analyze.stages.merging.SharedHistory import SharedHistory
from poe_log_analyze.stages.preparation.AnalysisValidator import AnalysisValidator
from poe_log_analyze.stages.reconstruction.MapActivityBuilder import MapActivityBuilder
from poe_log_analyze.stages.reconstruction.SourceHistory import SourceHistory
from poe_log_analyze.stages.rendering.RenderedReport import RenderedReport
from poe_log_analyze.stages.rendering.ReportTemplates import ReportTemplates
from poe_log_analyze.stages.verification.LocalHTML import LocalHTML
from poe_log_analyze.stages.verification.LocalResources import LocalResources
from poe_log_analyze.stages.verification.SearchIndexVerifier import SearchIndexVerifier


class VerifyReport:
    """Verify HTML, links, provenance, and unchanged input artifacts."""

    def execute(self, rendered: RenderedReport, sources: tuple[SourceHistory, ...],
                require_complete: bool, control: ExecutionContext) -> Path:

        if rendered.outputs is None:
            return self._extended(rendered, sources, require_complete, control)

        from poe_log_analyze.stages.verification.ReportBundleVerifier import ReportBundleVerifier

        for number, source in enumerate(sources, 1):
            control.report(f'Verify input analysis {number} of {len(sources)}', force = True)

            if AnalysisValidator.file_hash(source.directory / 'manifest.json', control) != source.manifest_sha256:
                raise ValueError('The analysis manifest changed during generation')

            for name, digest in source.manifest['artifacts_sha256'].items():
                path = (source.directory / name).resolve(strict = True)

                if not path.is_relative_to(source.directory) or AnalysisValidator.file_hash(path, control) != digest:
                    raise ValueError('Analysis artifacts changed during generation')

        for child in rendered.children:
            self._extended(child, sources, require_complete, control, bundle_root = rendered.directory)

        return ReportBundleVerifier.verify(rendered, control)

    def _extended(self, rendered: RenderedReport, sources: tuple[SourceHistory, ...],
                require_complete: bool, control: ExecutionContext, *, bundle_root: Path | None = None) -> Path:

        target, content, report_language = rendered.directory, rendered.content, rendered.language
        root = RuntimeResources.resource_root()
        project, public = target / 'project', target / 'public'
        data, manifest = content.analysis, content.manifest
        timeline, maps, statistics = content.timeline, content.maps, content.statistics
        flow, activity = content.flow, content.activity
        catalogue = TranslationCatalogue(report_language, root)
        specification = catalogue.specification()
        result_dir = sources[0].directory if len(sources) == 1 else None

        for number, source in enumerate(sources, 1):
            control.report(f'Verify input analysis {number} of {len(sources)}', force = True)

            if AnalysisValidator.file_hash(source.directory / 'manifest.json', control) != source.manifest_sha256:
                raise ValueError('The analysis manifest changed during generation')

            for name, digest in source.manifest['artifacts_sha256'].items():
                path = (source.directory / name).resolve(strict = True)

                if not path.is_relative_to(source.directory) or AnalysisValidator.file_hash(path, control) != digest:
                    raise ValueError('Analysis artifacts changed during generation')

        actual = {p.relative_to(public).as_posix() for p in public.rglob("*") if p.is_file()}
        expected = {name.removeprefix("site/static/") for name in ReportTemplates.files() if name.startswith("site/static/")} | {
                    "pace/index.html", "loading/index.html", "activities/index.html", "characters/index.html", "statistics/index.html", "events/index.html", "areas/index.html", "conversations/index.html", "playtime/index.html", "technical/issues/index.html","flow/index.html", "index.html", "style.css", "maps/index.html", "technical/index.html",
                    "technical/timeline/index.html", "technical/maps/index.html", "technical/specification/index.html", "sessions/index.html"} | {
            session['path'] for session in content.views['sessions']['rows']} | {
            f"technical/timeline/{day['date']}/index.html" for day in timeline["days"]} | {
            f"technical/maps/{day['date']}/index.html" for day in maps["days"]} | {
            f"maps/{date}/index.html" for date in content.views['daily_areas']['by_date']} | {
            'events/' + page['path'] for page in content.views['events']['pages']} | {
            f"statistics/observations/{group['code']}/index.html"
            for group in content.views['map_observations']['groups'] if group['count']}

        comparison = content.views['period_comparison']
        expected.add('search/index.html')
        expected.add('explore/index.html')
        expected.add('maps/compare/index.html')
        expected.add('sessions/compare/index.html')
        expected.update(page['path'] for page in content.views['analytics_navigation']['pages'])
        expected.update(area['path'] for area in content.views['area_details']['pages'])
        expected.update(run['path'] for run in content.views['map_run_details']['pages'])
        expected.update(panel['path'] for panel in content.views['weekly_pace']['panels'])
        expected.update('search/' + part['path'] for part in rendered.search['parts'])

        if rendered.basic_block:
            from poe_log_analyze.stages.rendering.BasicReportWriter import BasicReportWriter
            expected.update('basic/' + path for path in BasicReportWriter.PAGES)
            expected.add('basic/images/activity-overview.png')

        if comparison['enabled']:
            expected.add('comparison/index.html')

        if rendered.pdf:
            expected.add("report.pdf")
            pdf = public / "report.pdf"

            if not pdf.is_file():
                raise ValueError('The requested PDF report was not created')

            with pdf.open("rb") as stream:
                header = stream.read(8)
                stream.seek(max(0, pdf.stat().st_size - 32))
                ending = stream.read()

            if not header.startswith(b"%PDF-") or not ending.rstrip().endswith(b"%%EOF"):
                raise ValueError('The PDF report is incomplete')

        if actual != expected:
            raise ValueError(f"Unexpected HTML-report files inventory: extra {sorted(actual-expected)}, missing {sorted(expected-actual)}")

        checkers = {}
        resources = LocalResources(bundle_root or public)

        html_pages = sorted(name for name in actual if name.endswith('.html'))

        for number, name in enumerate(html_pages):
            control.report('Verify HTML: ' + name, number, len(html_pages), unit = 'pages', force = True)
            page = public / name
            html = page.read_text(encoding = "utf-8")

            if f'lang="{report_language}"' not in html or "[i18n]" in html:
                raise ValueError('HTML has an invalid language or a missing translation')

            checker = LocalHTML(resources, page, script_roots = (public,))
            checker.feed(html)
            checker.close()
            checkers[checker.page] = checker
            source_identity = name in ("technical/index.html", "technical/specification/index.html",
                                       "technical/issues/index.html")

            if not name.startswith(("sources/", "basic/")) and (data["state"] not in html or (source_identity and data["input_sha256"] not in html)):
                raise ValueError('HTML is missing the source identifier or coverage status')

        control.report('Verify links between pages', force = True)

        for checker in checkers.values():
            control.check()

            for path, anchor in checker.anchors:
                if path not in checkers or anchor not in checkers[path].ids:
                    raise ValueError('The event link does not match its HTML identifier')

        control.report('Verify search index', force = True)
        SearchIndexVerifier.verify(public, rendered.search, content.views['events'], checkers, control)
        control.report('Verify data and resource checksums', force = True)
        build = RuntimeResources.build_metadata()
        code_hashes = build["code"]["files_sha256"] if build else CodeProvenance.source_hashes()
        JsonFiles.write_json(target / "report-manifest.json", {
            "report_schema_version": "40" if rendered.basic_block else "39",
            "search": {"version": rendered.search['version'], "count": rendered.search['count'],
                       "index_sha256": AnalysisValidator.file_hash(project / 'data/search-index.json', control)},
            "report_period": content.views['report_period'],
            "comparison_period": comparison['a']['period'] if comparison['enabled'] else None,
            "pdf": {"enabled": rendered.pdf, "path": "report.pdf" if rendered.pdf else None,
                    "content_version": "12" if rendered.pdf else None,
                    "theme": "dark" if rendered.pdf_dark else "light"},
            "report_language": report_language, "translation_version": catalogue.VERSION,
            "translations_sha256": catalogue.hashes,
            "views_sha256": {name: AnalysisValidator.file_hash(project / 'data' / (name+'.json'), control) for name in content.views},
            "assets_manifest_sha256": AnalysisValidator.file_hash(root/'docs/report-assets.json', control),
            "specification_version": specification["version"],
            "specification_rules_version": specification["rules_version"],
            "specification_sha256": AnalysisValidator.file_hash(project / "data/log_specification.json", control),
            "overlap_policy": SharedHistory.OVERLAP_POLICY if data.get("collection") else "single_source",
            "overlap": data.get("overlap"), "sources": data.get("sources", []),
            "flow_version": flow["version"], "activity_version": activity["version"],
            "activity_sha256": AnalysisValidator.file_hash(project / "data" / "activity.json", control),
            "flow_sha256": AnalysisValidator.file_hash(project / "data" / "map_flow.json", control), "input_sha256": data["input_sha256"],
            "statistics_version": MapStatisticsBuilder.STATISTICS_VERSION,
            "statistics_sha256": AnalysisValidator.file_hash(project / "data" / "map_statistics.json", control),
            "maps_version": MapActivityBuilder.MAPS_VERSION,
            "maps_sha256": AnalysisValidator.file_hash(project / "data" / "maps.json", control),
            "timeline_version": TimelineBuilder.TIMELINE_VERSION, "generator_files_sha256": code_hashes,
            "timeline_sha256": AnalysisValidator.file_hash(project / "data" / "timeline.json", control),
            "rules_version": data["rules_version"],
            "renderer": {"name": "Jinja2", "versions": rendered.renderer_versions},
            "require_complete": require_complete,
            "analysis_manifest_sha256": AnalysisValidator.file_hash(result_dir / "manifest.json", control) if result_dir else None,
            "analysis_artifacts_sha256": {key: manifest["artifacts_sha256"][key]
                                          for key in ("coverage.json", "lines.jsonl", "diagnostic_summary.json")
                                          if key in manifest["artifacts_sha256"]},
            "templates_sha256": {name: AnalysisValidator.file_hash(root / name, control) for name in ReportTemplates.files()},
            "public_sha256": {name: AnalysisValidator.file_hash(public / name, control) for name in sorted(actual)},
        })
        control.report('Extended HTML verification complete', len(html_pages), len(html_pages),
                       unit = 'pages', force = True)

        return public / "index.html"
