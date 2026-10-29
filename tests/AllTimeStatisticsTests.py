"""Whole-history totals: map types, all areas, and unmeasured visits."""

import json
import unittest

from copy import deepcopy

from pathlib import Path
from tempfile import TemporaryDirectory

from CollectionFixture import CollectionFixture
from ReportFixture import ReportFixture

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled

from poe_log_analyze.stages.composition.AllTimeStatisticsBuilder import AllTimeStatisticsBuilder
from poe_log_analyze.stages.parsing.CollectionAnalysisService import CollectionAnalysisService


class AllTimeStatisticsTests(unittest.TestCase):
    """Independent-total and complete-export checks using synthetic logs."""

    @staticmethod
    def run_record(area_id, name, kind, *durations):
        return {"area_id": area_id, "name": name, "kind_code": kind,
                "visits": [{"bounded": seconds is not None, "seconds": seconds} for seconds in durations]}

    def test_totals_group_by_id_count_runs_and_keep_partial_measured_time(self):
        runs = [self.run_record("dunes", "Dunes", "map", 100, 50, None),
                self.run_record("dunes", "Dunes", "map", 200),
                self.run_record("square", "City Square", "map", 80),
                self.run_record("hideout", "Hideout", "hideout", 90000),
                self.run_record("town", "Town", "town", 10),
                self.run_record("arena", "Arena", "arena", 30),
                self.run_record("area", "Area", "area", None)]
        before = deepcopy(runs)

        summary = AllTimeStatisticsBuilder.build(runs, ExecutionContext())

        self.assertEqual(summary["maps"], {"count": 3, "visits": 5, "measured_visits": 4,
                                          "incomplete_visits": 1, "seconds": 430, "duration": "00:07:10"})
        self.assertEqual([(r["name"], r["count"], r["seconds"]) for r in summary["map_types"]],
                         [("Dunes", 2, 350), ("City Square", 1, 80)])
        self.assertEqual(summary["zone_totals"]["seconds"], 90470)
        self.assertEqual(summary["zone_totals"]["incomplete_visits"], 2)
        self.assertEqual(summary["zones"][0]["duration"], "25:00:00")
        self.assertEqual(summary["zones"][-1]["duration"], "—")
        self.assertEqual(runs, before)

    def test_names_do_not_merge_different_ids_and_aliases_do_not_split_one_id(self):
        runs = [self.run_record("a", "Same name", "map", 5),
                self.run_record("b", "Same name", "map", 3),
                self.run_record("a", "Another name", "map", 7)]

        summary = AllTimeStatisticsBuilder.build(runs, ExecutionContext())

        self.assertEqual(len(summary["map_types"]), 2)
        self.assertEqual(summary["map_types"][0]["seconds"], 12)
        self.assertEqual(summary["map_types"][0]["name"], "Another name / Same name")

    def test_unknown_zero_empty_and_cancellation(self):
        empty = AllTimeStatisticsBuilder.build([], ExecutionContext())

        self.assertEqual(empty["maps"]["count"], 0)
        self.assertEqual(empty["maps"]["duration"], "—")

        runs = [self.run_record("unknown", "Unknown", "map", None),
                self.run_record("zero", "Zero", "map", 0)]

        summary = AllTimeStatisticsBuilder.build(runs, ExecutionContext())

        self.assertEqual(summary["maps"]["duration"], "00:00:00")
        self.assertEqual({r["name"]: r["duration"] for r in summary["map_types"]},
                         {"Unknown": "—", "Zero": "00:00:00"})

        with self.assertRaises(GenerationCancelled):
            AllTimeStatisticsBuilder.build(runs, ExecutionContext(cancelled = lambda: True))

    def test_all_zones_and_map_types_export_in_both_languages_without_duplicate_logs(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            messages = [(0, 'Generating level 60 area "HideoutOssuary" with seed 1'),
                        (1, ': You have entered Hideout.'),
                        (11, 'Generating level 83 area "MapWorldsDunes" with seed 2'),
                        (12, ': You have entered Dunes.'),
                        (32, 'Generating level 80 area "MapWorldsCitySquare" with seed 3'),
                        (33, ': You have entered City Square.'),
                        (63, 'Generating level 82 area "MapWorldsDunes" with seed 4'),
                        (64, ': You have entered Dunes.'),
                        (104, 'Generating level 1 area "1_1_town" with seed 5'),
                        (105, ': You have entered Lioneye\'s Watch.'),
                        (110, 'Generating level 60 area "HideoutOssuary" with seed 6'),
                        (111, ': You have entered Hideout.'),
                        (121, ': Trade accepted.')]
            source = root / "one.txt"
            source.write_text(''.join(CollectionFixture.line(t, message) for t, message in messages))
            copy = root / "copy.txt"
            copy.write_bytes(source.read_bytes())
            analysis = root / "analysis"

            CollectionAnalysisService.analyze_collection([source, copy], analysis)

            for language in ("ru", "en"):
                report = root / language

                ReportFixture.export_report(analysis, report, report_language = language)
                summary = json.loads((report / "project/data/statistics_summary.json").read_text())

                self.assertEqual(summary["maps"]["count"], 3)
                self.assertEqual(summary["maps"]["seconds"], 90)
                self.assertEqual([(row["name"], row["count"], row["seconds"]) for row in summary["map_types"]],
                                 [("Dunes", 2, 60), ("City Square", 1, 30)])
                self.assertEqual(summary["zone_totals"]["seconds"], 105)
                self.assertEqual(summary["zone_totals"]["visits"], 6)

                hideout = next(row for row in summary["zones"] if row["kind_code"] == "hideout")

                self.assertEqual((hideout["seconds"], hideout["visits"], hideout["incomplete_visits"]), (10, 2, 1))

                public = report / "public"
                statistics = (public / "statistics/index.html").read_text()

                self.assertIn("00:01:30", statistics)
                self.assertIn("Dunes", statistics)
                self.assertIn("City Square", statistics)
                self.assertIn('areas/index.html#zone-totals', statistics)

                areas = (public / "areas/index.html").read_text()

                self.assertIn("00:01:45", areas)
                self.assertIn('data-kind="hideout"', areas)
                self.assertIn('data-kind="map"', areas)
                self.assertIn("Dunes", areas)
                self.assertIn('data-bs-theme="dark"', statistics)
                self.assertIn('data-theme-toggle', statistics)
                self.assertIn('width="64" height="64"', statistics)

                manifest = json.loads((report / "report-manifest.json").read_text())

                self.assertIn("statistics_summary", manifest["views_sha256"])
                self.assertIn("statistics/index.html", manifest["public_sha256"])
