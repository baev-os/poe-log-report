"""Check local HTML, source links, and atomic export."""

import hashlib
import json
import unittest

from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import patch

from poe_log_analyze.stages.parsing.LogAnalysisService import LogAnalysisService

from poe_log_analyze.runtime.JsonFiles import JsonFiles

from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from ReportFixture import ReportFixture

from poe_log_analyze.stages.preparation.AnalysisValidator import AnalysisValidator


class ReportTests(unittest.TestCase):
    """Use synthetic data, including HTML in the source label."""

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "Лог дома.txt"
        self.source.write_bytes(b"PRIVATE_CHAT_MARKER\n\n")
        self.result = self.root / "analysis"
        self.output = self.root / "report"
        LogAnalysisService.analyze(self.source, self.result, source_label = '<script>alert("test")</script>')

    def test_tampered_coverage_is_rejected(self):
        (self.result / "coverage.json").write_text("{}", encoding = "utf-8")

        with self.assertRaisesRegex(ValueError, "[Hh]ash"):
            ReportFixture.export_report(self.result, self.output)

        self.assertFalse(self.output.exists())

    def test_wrong_source_and_strict_mode_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "incomplete"):
            ReportFixture.export_report(self.result, self.output, require_complete = True)

        manifest_file = self.result / "manifest.json"
        manifest = json.loads(manifest_file.read_text())
        manifest["input"]["sha256"] = "0" * 64
        JsonFiles.write_json(manifest_file, manifest)

        with self.assertRaisesRegex(ValueError, "disagree"):
            ReportFixture.export_report(self.result, self.output)

        self.assertFalse(self.output.exists())

    def test_diagnostics_validation_and_older_results(self):
        data, manifest = AnalysisValidator.report_data(self.result, ExecutionContext())

        self.assertEqual(data["diagnostic_categories"], [{
            "category": "Строка без распознанного заголовка или продолжения", "count": 1}])

        path = self.result / "diagnostic_summary.json"
        summary = json.loads(path.read_text())
        summary["categories"]["unframed"] = 2
        JsonFiles.write_json(path, summary)

        with self.assertRaisesRegex(ValueError, "[Hh]ash"):
            AnalysisValidator.report_data(self.result, ExecutionContext())

        manifest["artifacts_sha256"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        JsonFiles.write_json(self.result / "manifest.json", manifest)

        with self.assertRaisesRegex(ValueError, "disagrees"):
            AnalysisValidator.report_data(self.result, ExecutionContext())

        del manifest["artifacts_sha256"][path.name]
        JsonFiles.write_json(self.result / "manifest.json", manifest)
        path.unlink()

        self.assertEqual(AnalysisValidator.report_data(self.result, ExecutionContext())[0]["diagnostic_categories"], [])

    def test_legacy_analysis_with_database_exports_jsonl_and_checks_all_hashes(self):
        """Validate the legacy optional artifact as bytes without a database engine."""

        self.source.unlink()
        database = self.result / "analysis.duckdb"
        database.write_bytes(b"synthetic legacy artifact, not a database")
        manifest = json.loads((self.result / "manifest.json").read_text())
        manifest["parameters"]["database"] = True
        manifest["environment"]["dependencies"] = [{"name": "duckdb", "version": "synthetic"}]
        manifest["artifacts_sha256"][database.name] = hashlib.sha256(database.read_bytes()).hexdigest()
        JsonFiles.write_json(self.result / "manifest.json", manifest)
        before = {p.name: p.read_bytes() for p in self.result.iterdir()}

        entry = ReportFixture.export_report(self.result, self.output)

        self.assertTrue(entry.is_file())
        self.assertEqual({p.name: p.read_bytes() for p in self.result.iterdir()}, before)
        self.assertFalse(list(self.output.rglob("*.duckdb")))

        database.write_bytes(b"changed synthetic artifact")
        rejected = self.root / "rejected"

        with self.assertRaisesRegex(ValueError, "Analysis artifacts changed"):
            ReportFixture.export_report(self.result, rejected)

        self.assertFalse(rejected.exists())

    def test_html_unifies_title_includes_diagnostics_and_is_reproducible(self):
        self.source.unlink()

        entry = ReportFixture.export_report(self.result, self.output)
        html = (entry.parent / "technical/index.html").read_text(encoding = "utf-8")

        self.assertIn("Распознавание не завершено", html)
        self.assertNotIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertIn("<pre>PRIVATE_CHAT_MARKER</pre>", html)
        self.assertIn('<details class="diagnostic-category">', html)
        self.assertIn("Требуют разбора", html)
        self.assertNotIn("PRIVATE_CHAT_MARKER", (self.output / "project/data/analysis.json").read_text())
        self.assertNotIn(str(self.result), html)
        self.assertIn("Europe/London", html)
        self.assertEqual({p.name for p in entry.parent.iterdir()}, {"index.html", "style.css", "technical", "maps", "statistics", "flow", "events", "characters", "activities", "areas", "conversations", "playtime", "sessions", "loading", "pace", "search", "ReportSearch.js", "MapExplorer.js", "SessionComparison.js", "ComparisonDisplay.js", "MapRunComparison.js", "explore", "analytics", "vendor", "images", "ReportInteractions.js", "BasicReport.css", "BasicReport.js", "ChartTooltip.css", "ChartTooltip.js", "ReportTheme.js"})

        second = ReportFixture.export_report(self.result, self.root / "second")

        self.assertEqual(entry.read_bytes(), second.read_bytes())
        self.assertEqual((entry.parent / "technical/timeline/index.html").read_bytes(),
                         (second.parent / "technical/timeline/index.html").read_bytes())

        info = json.loads((self.output / "report-manifest.json").read_text())

        self.assertEqual(info["public_sha256"]["index.html"], hashlib.sha256(entry.read_bytes()).hexdigest())

        specification = self.output / "project/data/log_specification.json"
        catalogue = json.loads(specification.read_text())

        self.assertEqual(info["specification_sha256"], hashlib.sha256(specification.read_bytes()).hexdigest())

        page = entry.parent / "technical/specification/index.html"
        spec_html = page.read_text()

        self.assertIn('technical/specification/index.html', html)
        self.assertNotIn("PRIVATE_CHAT_MARKER", spec_html)
        self.assertNotIn(str(self.result), spec_html)
        self.assertEqual(page.read_bytes(), (second.parent / "technical/specification/index.html").read_bytes())

        codes = [rule["rule_id"] for group in catalogue["families"] for rule in group["rules"]]
        codes += [rule["rule_id"] for rule in catalogue["framing"] + catalogue["continuations"]]

        groups = catalogue['groups']

        self.assertEqual(catalogue['version'], '4')
        self.assertEqual([group['code'] for group in groups], sorted(group['code'] for group in groups))

        block_positions = [spec_html.index(f'id="family-{group["code"]}"') for group in groups]

        self.assertEqual(block_positions, sorted(block_positions))

        ordered_codes = [rule['rule_id'] for group in groups for rule in group['rules']]
        detailed_positions = [spec_html.index(f'id="rule-{code}"') for code in ordered_codes]
        compact_positions = [spec_html.index(f'href="#rule-{code}"') for code in ordered_codes]

        self.assertEqual(detailed_positions, sorted(detailed_positions))
        self.assertEqual(compact_positions, sorted(compact_positions))
        self.assertEqual(spec_html.count('data-group'), len(groups))

        for code in codes:
            self.assertEqual(spec_html.count(f'id="rule-{code}"'), 1, code)

        self.assertIn("&lt;", spec_html)

        with self.assertRaises(FileExistsError):
            ReportFixture.export_report(self.result, self.output)

    def test_maps_from_parser_without_source_and_reproducible_export(self):
        source = self.root / "map.txt"
        source.write_text(
            self._message(0, "Client-Safe Instance ID = 123")
            + self._message(0, 'Generating level 83 area "MapWorldsBeach" with seed 456')
            + self._message(2, ": You have entered <script>Beach</script>.")
            + self._message(12, 'Generating level 60 area "HideoutOssuary" with seed 789')
            + self._message(14, ": You have entered Test Hideout."))
        result = self.root / "map-analysis"
        LogAnalysisService.analyze(source, result)
        source.unlink()

        entry = ReportFixture.export_report(result, self.output)
        maps = self.output / "project/data/maps.json"

        self.assertEqual(json.loads(maps.read_text())["seconds"], 10)

        html = (entry.parent / "technical/maps/2026-07-20/index.html").read_text()

        self.assertIn("&lt;script&gt;Beach&lt;/script&gt;", html)
        self.assertNotIn("<script>", html)

        info = json.loads((self.output / "report-manifest.json").read_text())

        self.assertEqual(info["maps_sha256"], hashlib.sha256(maps.read_bytes()).hexdigest())
        self.assertEqual(info["report_schema_version"], "39")
        self.assertEqual(info["renderer"]["name"], "Jinja2")
        self.assertEqual(set(info["renderer"]["versions"]), {"Jinja2", "MarkupSafe", "Markdown"})
        self.assertNotIn("hugo_sha256", info)
        self.assertFalse((self.output / "hugo.log").exists())
        self.assertIn("stages/reconstruction/MapActivityBuilder.py", info["generator_files_sha256"])

        simple = (entry.parent / "maps/2026-07-20/index.html").read_text()

        for text in ("Игровая статистика", "Технические данные", "Длительность",
                     "Время захода", "Время выхода", "00:00:10", "21:00:02", "21:00:12"):
            self.assertIn(text, simple)

        for text in ("SHA-256", "Seed", "MapWorldsBeach", "Строка", "raw_base64"):
            self.assertNotIn(text, simple)

        self.assertIn("&lt;script&gt;Beach&lt;/script&gt;", simple)

        map_table = simple.split('<table class="map-statistics">', 1)[1].split('</table>', 1)[0]

        self.assertEqual(map_table.count('<th scope="col">'), 4)
        self.assertIn("Игровая статистика", entry.read_text())
        self.assertIn("statistics_sha256", info)

        second = ReportFixture.export_report(result, self.root / "map-second")

        for path in entry.parent.rglob("*"):
            if path.is_file():
                self.assertEqual(path.read_bytes(), (second.parent / path.relative_to(entry.parent)).read_bytes())

    def test_unknown_entry_is_rendered_without_fabricated_time(self):
        from poe_log_analyze.stages.reconstruction.MapActivityBuilder import MapActivityBuilder
        source = self.root / "map.txt"
        source.write_text(
            '2026/07/20 21:00:00 123 abcd [INFO Client 42] Generating level 83 area "MapWorldsBeach" with seed 456\n'
            '2026/07/20 21:00:02 123 abcd [INFO Client 42] : You have entered Beach.\n'
            '2026/07/20 21:00:12 123 abcd [INFO Client 42] Connecting to instance server at 127.0.0.1:1234\n')
        result = self.root / "map-analysis"
        LogAnalysisService.analyze(source, result, timezone_name = "Asia/Almaty")
        manifest = json.loads((result / "manifest.json").read_text())

        maps = MapActivityBuilder.build_map_activity(result / "lines.jsonl", "Asia/Almaty", manifest["artifacts_sha256"]["lines.jsonl"])
        day = maps["by_date"].pop("2026-07-20")
        run = day["runs"][0]
        run.update(started_at = None, date = "undated", unbounded_visits = 1, seconds = 0)
        run["visits"][0].update(entered_at = None, seconds = None, bounded = False)
        day.update(date = "undated", seconds = 0)
        maps["by_date"]["undated"] = day
        maps["days"] = [{"date": "undated", "count": 1, "seconds": 0}]
        maps.update(seconds = 0, unbounded_visits = 1)

        with patch("poe_log_analyze.stages.reconstruction.MapActivityBuilder.MapActivityBuilder.build_map_activity", return_value = maps):
            entry = ReportFixture.export_report(result, self.output)

        html = (entry.parent / "maps/undated/index.html").read_text()

        self.assertIn("Дата входа неизвестна", html)
        self.assertIn("Время входа неизвестно", html)
        self.assertNotIn('datetime=""', html)
        self.assertNotIn('datetime="2026-07-20T21:00:02+05:00"', html)

        flow = json.loads((self.output / "project/data/map_flow.json").read_text())

        self.assertEqual(flow["count"], 1)
        self.assertIsNone(flow["rows"][0]["entered_at"])
        self.assertEqual(flow["rows"][0]["duration"], "—")

    def test_failure_and_cancellation_publish_nothing(self):
        with patch("poe_log_analyze.stages.rendering.HtmlPageWriter.HtmlPageWriter.write", side_effect = OSError("Ошибка запуска")):
            with self.assertRaises(OSError):
                ReportFixture.export_report(self.result, self.output)

        self._state = {"cancel": False}
        control = ExecutionContext(cancelled = lambda: self._state["cancel"], progress = self._progress)

        with self.assertRaises(GenerationCancelled):
            ReportFixture.export_report(self.result, self.output, control = control)

        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob(".report-*")))

    def test_empty_source_allows_strict_report(self):
        empty = self.root / "empty.txt"
        empty.write_bytes(b"")
        LogAnalysisService.analyze(empty, self.root / "empty")

        entry = ReportFixture.export_report(self.root / "empty", self.output, require_complete = True)
        html = (entry.parent / "technical/index.html").read_text()

        self.assertIn("пустой файл", html)
        self.assertIn("Распознавание завершено", html)

    def _message(self, second, text):
        return f"2026/07/20 21:00:{second:02d} 123 abcd [INFO Client 42] {text}\n"

    def _progress(self, value):
        if value.stage == 'HTML rendering':
            self._state["cancel"] = True
