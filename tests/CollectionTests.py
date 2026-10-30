"""Collections preserve duplicates, provenance, complete duration, and atomicity."""

import hashlib
import json
import unittest

from pathlib import Path
from tempfile import TemporaryDirectory

from poe_log_analyze.stages.reconstruction.PlaytimeBuilder import PlaytimeBuilder
from poe_log_analyze.stages.preparation.ResultDirectories import ResultDirectories
from poe_log_analyze.stages.parsing.CollectionAnalysisService import CollectionAnalysisService

from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from ReportFixture import ReportFixture

from CollectionFixture import CollectionFixture


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "Дом.txt"
        self.source.write_text(
            CollectionFixture.line(0, ": You have entered Town.")
            + CollectionFixture.line(10, "Client-Safe Instance ID = 123")
            + CollectionFixture.line(10, 'Generating level 83 area "MapWorldsBeach" with seed 456')
            + CollectionFixture.line(12, ": You have entered Beach.")
            + CollectionFixture.line(22, 'Generating level 60 area "HideoutOssuary" with seed 789')
            + CollectionFixture.line(24, ": You have entered Hideout.")
            + CollectionFixture.line(40, "Abnormal disconnect: An unexpected disconnection occurred."))

    def test_copied_history_counts_once_and_reopens_without_logs(self):
        result = self.root / "collection"

        CollectionAnalysisService.analyze_collection([self.source, self.source], result,
                                                     timezone_name = "Asia/Almaty")
        self.source.unlink()
        children = ResultDirectories.result_directories(result)

        self.assertEqual(len(children), 2)
        self.assertEqual((children[0] / "lines.jsonl").read_bytes(), (children[1] / "lines.jsonl").read_bytes())

        self._copied_report = self.root / "report"

        ReportFixture.export_report(result, self._copied_report)

        self.assertEqual(self._copied_read("activity")["seconds"], 40)
        self.assertEqual(self._copied_read("analysis")["timezone"], "Asia/Almaty")
        self.assertEqual(self._copied_read("timeline")["timezone"], "Asia/Almaty")
        self.assertEqual(self._copied_read("timeline")["first"], "2026-09-01T00:00:00+05:00")
        self.assertEqual(self._copied_read("activity")["incomplete"], 0)
        self.assertEqual(self._copied_read("map_flow")["seconds"], 10)
        self.assertEqual(self._copied_read("map_flow")["count"], 1)
        self.assertEqual(self._copied_read("map_statistics")["count"], 1)
        self.assertEqual(len({row["source"] for row in self._copied_read("map_flow")["rows"]}), 1)

        overlap = self._copied_read("analysis")["overlap"]

        self.assertEqual(overlap["removed_maps"], 1)
        self.assertEqual(overlap["removed_play_seconds"], 40)
        self.assertEqual(len(self._copied_read("activity")["intervals"][0]["origins"]), 2)
        self.assertFalse((self._copied_report / "source-reports").exists())
        self.assertFalse((self._copied_report / "public/sources").exists())
        self.assertEqual(self._copied_read("analysis")["total_lines"], 7)
        self.assertEqual(self._copied_read("timeline")["total_lines"], 7)
        self.assertTrue((self._copied_report / "public/technical/specification/index.html").is_file())
        self.assertIn("Карты потоком", (self._copied_report / "public/index.html").read_text())

        second = self.root / "second"

        ReportFixture.export_report(result, second)

        for path in (self._copied_report / "public").rglob("*"):
            if path.is_file():
                self.assertEqual(path.read_bytes(), (second / "public" / path.relative_to(self._copied_report / "public")).read_bytes())

    def test_collection_defaults_to_london_for_every_source(self):
        result = self.root / "london-collection"

        CollectionAnalysisService.analyze_collection([self.source, self.source], result)

        for directory in ResultDirectories.result_directories(result):
            with self.subTest(source = directory.name):
                manifest = json.loads((directory / "manifest.json").read_text())
                row = json.loads((directory / "lines.jsonl").read_text().splitlines()[0])

                self.assertEqual(manifest["parameters"]["timezone"], "Europe/London")
                self.assertEqual(row["timestamp"], "2026-09-01T00:00:00+01:00")

    def test_common_prefix_keeps_new_events_and_three_copies_count_once(self):
        extended = self.root / "Работа.txt"
        extended.write_text(self.source.read_text()
                            + CollectionFixture.line(100, 'Generating level 83 area "MapWorldsBeach" with seed 789')
                            + CollectionFixture.line(102, ": You have entered Beach.")
                            + CollectionFixture.line(112, 'Generating level 60 area "HideoutOssuary" with seed 999')
                            + CollectionFixture.line(114, ": You have entered Hideout.")
                            + CollectionFixture.line(140, "Abnormal disconnect: An unexpected disconnection occurred."))
        result = self.root / "collection"

        CollectionAnalysisService.analyze_collection([self.source, extended, self.source], result)
        self._merged_report = self.root / "report"

        ReportFixture.export_report(result, self._merged_report)

        self.assertEqual(self._merged_read("map_statistics")["count"], 2)
        self.assertEqual(self._merged_read("map_flow")["seconds"], 20)
        self.assertEqual(self._merged_read("activity")["seconds"], 78)
        self.assertEqual(self._merged_read("analysis")["overlap"]["removed_maps"], 2)
        self.assertEqual(len(self._merged_read("activity")["intervals"][0]["origins"]), 3)

    def test_matching_maps_after_different_history_are_not_removed(self):
        other = self.root / "Другой.txt"
        other.write_text("different history\n" + self.source.read_text())
        result = self.root / "collection"

        CollectionAnalysisService.analyze_collection([self.source, other], result)
        report = self.root / "report"

        ReportFixture.export_report(result, report)
        flow = json.loads((report / "project/data/map_flow.json").read_text())

        self.assertEqual(flow["count"], 2)
        self.assertEqual(flow["seconds"], 20)

        data = json.loads((report / "project/data/analysis.json").read_text())

        self.assertEqual(data["overlap"]["removed_runs"], 0)

    def test_overlap_rejects_changed_ledger_and_does_not_remove_internal_repeats(self):
        from poe_log_analyze.stages.merging.SharedHistory import SharedHistory
        from poe_log_analyze.stages.merging.SharedIntervals import SharedIntervals
        result = self.root / "collection"

        CollectionAnalysisService.analyze_collection([self.source], result)
        directory = ResultDirectories.result_directories(result)[0]
        manifest = json.loads((directory / "manifest.json").read_text())
        ledger = directory / "lines.jsonl"
        history = SharedHistory()
        # Even identical analytical intervals within one source are not excluded.
        interval = {"first_line": 1, "last_line": 2, "started_at": "2026-09-01T00:00:00+05:00",
                    "ended_at": "2026-09-01T00:00:10+05:00", "seconds": 10, 'incomplete': False,
                    'origin': {'source': '1', 'first_line': 1, 'last_line': 2}}
        history.register(ledger, manifest["artifacts_sha256"]["lines.jsonl"], manifest["input"]["sha256"], '1')
        selected = SharedIntervals(history).activity([dict(interval), dict(interval)])

        self.assertEqual(len(selected), 2)

        with self.assertRaisesRegex(ValueError, "[Hh]ash"):
            history.register(ledger, "0" * 64, manifest["input"]["sha256"], '2')

    def test_cancel_second_file_publishes_nothing(self):
        self._cancelled = False
        control = ExecutionContext(cancelled = lambda: self._cancelled, progress = self._progress)

        with self.assertRaises(GenerationCancelled):
            CollectionAnalysisService.analyze_collection([self.source, self.source], self.root / "cancelled", control = control)

        self.assertFalse((self.root / "cancelled").exists())
        self.assertFalse(list(self.root.glob(".collection-*")))

    def test_collection_rejects_path_escape(self):
        directory = self.root / "collection"
        directory.mkdir()
        (directory / "collection.json").write_text(json.dumps({"collection_version": "1", "overlap_policy": "keep_all",
                                                             "sources": [{"path": ".."}]}))

        with self.assertRaises(ValueError):
            ResultDirectories.result_directories(directory)

    def test_activity_breaks_eof_clock_and_missing_time(self):
        # Time sequence: 10 seconds, gap, 5 seconds, rollback, 3 seconds.
        rows = []

        for n, (stamp, kind) in enumerate([
            ("2026-09-01T00:00:00+00:00", "area.enter"),
            ("2026-09-01T00:00:10+00:00", "chat.local"),
            ("2026-09-01T02:00:00+00:00", "area.enter"),
            ("2026-09-01T02:00:05+00:00", "chat.local"),
            ("2026-09-01T01:00:00+00:00", "area.enter"),
            ("2026-09-01T01:00:03+00:00", "chat.local"),
            (None, "area.enter"),
            ("2026-09-01T01:00:10+00:00", "area.enter"),
            ("2026-09-01T01:00:12+00:00", "chat.local"),
        ], 1):
            rows.append({"line_number": n, "record_id": n, "status": "recognized", "type": kind, "timestamp": stamp})

        ledger = self.root / "lines.jsonl"
        ledger.write_bytes(b"".join(json.dumps(row).encode() + b"\n" for row in rows))

        model = PlaytimeBuilder.build_activity(ledger, hashlib.sha256(ledger.read_bytes()).hexdigest())

        self.assertEqual(model["seconds"], 20)
        self.assertEqual([i["reason"] for i in model["intervals"]], ["gap", "clock", "missing_time", "eof"])
        self.assertEqual(model["incomplete"], 4)

        with self.assertRaises(ValueError):
            PlaytimeBuilder.build_activity(ledger, "0" * 64)

    def _copied_read(self, name):
        return json.loads((self._copied_report / "project/data" / f"{name}.json").read_text())

    def _merged_read(self, name):
        return json.loads((self._merged_report / "project/data" / f"{name}.json").read_text())

    def _progress(self, value):
        if value.stage.startswith("File 2 of"):
            self._cancelled = True
