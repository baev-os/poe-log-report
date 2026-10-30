"""Independent examples of time boundaries, line links, and selected events."""

import hashlib
import json
import unittest

from pathlib import Path
from tempfile import TemporaryDirectory

from poe_log_analyze.stages.parsing.LogAnalysisService import LogAnalysisService

from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from ReportFixture import ReportFixture

from poe_log_analyze.stages.composition.TimelineBuilder import TimelineBuilder
from poe_log_analyze.stages.composition.TimelineCalendarBuilder import TimelineCalendarBuilder

from TimelineFixture import TimelineFixture


class TimelineTests(unittest.TestCase):
    """Compare chronology with manually specified events rather than the generator's formula."""

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def make_analysis(self, text):
        source = self.root / "source.txt"
        source.write_text(text, encoding = "utf-8")
        result = self.root / "analysis"
        LogAnalysisService.analyze(source, result, timezone_name = "Asia/Almaty")
        manifest = json.loads((result / "manifest.json").read_text())
        timeline = TimelineBuilder.build_timeline(result / "lines.jsonl", "Asia/Almaty", manifest["artifacts_sha256"]["lines.jsonl"])

        return result, timeline

    def test_days_ties_clock_regression_and_untimed_lines(self):
        text = (
            TimelineFixture.message("2026/07/20 23:59:59", ": You have entered Test Beach.")
            + TimelineFixture.message("2026/07/20 23:59:59", ": Hero (Witch) is now level 5")
            + TimelineFixture.message("2026/07/21 00:00:00", ": Hero has been slain.")
            + "2026/07/20 20:00:00 ***** LOG FILE OPENING *****\n"
            + TimelineFixture.message("2026/07/21 00:00:01", ": You have died 7 times.")
            + TimelineFixture.message("2026/07/21 00:00:02", "PRIVATE_UNKNOWN")
            + TimelineFixture.message("2026/07/21 00:00:03", "Client couldn't execute a triggered action from the server.")
            + "action type id = 7\n\n"
            + TimelineFixture.message("2026/99/21 00:00:04", ": You have entered Invalid Time.")
            + TimelineFixture.message("2026/07/21 00:00:05", "@From Other: PRIVATE_CHAT")
        )
        _, timeline = self.make_analysis(text)

        self.assertEqual(timeline["total_lines"], 11)
        self.assertEqual(timeline["dated_lines"], 8)
        self.assertEqual(timeline["undated_lines"], 3)
        self.assertEqual(timeline["undated_statuses"], {"recognized": 2, "unknown": 0, "error": 1})
        self.assertEqual(timeline["clock_regressions"], 1)
        self.assertEqual(timeline["event_count"], 5)
        self.assertEqual([e["line_number"] for e in timeline["by_date"]["2026-07-20"]["events"]], [4, 1, 2])
        self.assertEqual([e["line_number"] for e in timeline["by_date"]["2026-07-21"]["events"]], [3, 5])
        self.assertEqual(timeline["by_date"]["2026-07-21"]["unknown"], 1)
        self.assertEqual(timeline["first"], "2026-07-20T20:00:00+05:00")
        self.assertEqual(timeline["last"], "2026-07-21T00:00:05+05:00")
        self.assertNotIn("PRIVATE", json.dumps(timeline))
        self.assertNotIn("raw_base64", json.dumps(timeline))

    def test_different_offsets_sort_by_instant_and_group_in_analysis_zone(self):
        ledger = self.root / "lines.jsonl"
        rows = [
            {"line_number": 1, "record_id": 1, "type": "log.open", "status": "recognized", "fields": {}, "timestamp": "2026-07-20T23:45:00+05:00"},
            {"line_number": 2, "record_id": 2, "type": "log.open", "status": "recognized", "fields": {}, "timestamp": "2026-07-21T00:30:00+06:00"},
        ]
        ledger.write_text("".join(json.dumps(row) + "\n" for row in rows))

        timeline = TimelineBuilder.build_timeline(ledger, "Asia/Almaty", hashlib.sha256(ledger.read_bytes()).hexdigest())

        self.assertEqual(len(timeline["days"]), 1)
        self.assertEqual([e["line_number"] for e in timeline["by_date"]["2026-07-20"]["events"]], [2, 1])

    def test_no_events_and_missing_dates_remain_explicit(self):
        _, timeline = self.make_analysis("\nundated\n" + TimelineFixture.message("2026/07/21 01:00:00", "unknown"))

        self.assertEqual(timeline["event_count"], 0)
        self.assertEqual(timeline["undated_lines"], 2)
        self.assertEqual(timeline["days"][0]["lines"], 1)
        self.assertEqual(timeline["by_date"]["2026-07-21"]["events"], [])

    def test_empty_ledger(self):
        _, timeline = self.make_analysis("")

        self.assertEqual(timeline["days"], [])
        self.assertEqual(timeline["event_count"], 0)
        self.assertIsNone(timeline["first"])
        self.assertEqual(TimelineCalendarBuilder.build(timeline, ExecutionContext())["months"], [])

    def test_calendar_year_boundary_empty_month_and_leap_day(self):
        _, timeline = self.make_analysis(
            TimelineFixture.message("2027/12/31 23:59:59", ": You have entered Test Beach.")
            + TimelineFixture.message("2028/02/29 00:00:00", "UNKNOWN")
        )
        months = TimelineCalendarBuilder.build(timeline, ExecutionContext())["months"]

        self.assertEqual([month["id"] for month in months], ["2027-12", "2028-01", "2028-02"])

        february = months[2]["weeks"]

        self.assertEqual(february[0][0]["date"], "2028-01-31")
        self.assertFalse(february[0][0]["current"])

        current = {day["date"]: day for month in months for week in month["weeks"]
                   for day in week if day["current"]}

        self.assertIsNone(current["2028-01-15"]["summary"])
        self.assertEqual(current["2028-02-29"]["summary"]["event_count"], 0)
        self.assertEqual(current["2028-02-29"]["summary"]["unknown"], 1)

        with self.assertRaises(GenerationCancelled):
            TimelineCalendarBuilder.build(timeline, ExecutionContext(cancelled = lambda: True))

    def test_tampering_and_cancellation(self):
        result, _ = self.make_analysis("\n")
        ledger = result / "lines.jsonl"

        with self.assertRaisesRegex(ValueError, "changed"):
            TimelineBuilder.build_timeline(ledger, "Asia/Almaty", "0" * 64)

        with self.assertRaises(GenerationCancelled):
            TimelineBuilder.build_timeline(ledger, "Asia/Almaty", "0" * 64, ExecutionContext(cancelled = lambda: True))

    def test_html_day_navigation_anchors_and_escaping(self):
        result, _ = self.make_analysis(
            TimelineFixture.message("2026/07/20 23:59:59", ": You have entered <script>alert(1)</script>.")
            + TimelineFixture.message("2026/07/21 00:00:00", "Abnormal disconnect: An unexpected disconnection occurred.")
            + TimelineFixture.message("2026/07/22 00:00:00", "PRIVATE_UNKNOWN")
        )

        entry = ReportFixture.export_report(result, self.root / "report")
        day = entry.parent / "technical/timeline/2026-07-20/index.html"
        html = day.read_text()

        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertIn('id="line-1"', html)
        self.assertIn('href="#line-1"', html)
        self.assertIn("23:59:59", html)
        self.assertIn("2026-07-21/index.html", html)
        self.assertIn("Исходное сообщение", html)
        self.assertIn("You have entered &lt;script&gt;", html)
        self.assertIn('<table class="timeline-rows">', html)
        self.assertIn('<tr id="line-1">', html)
        self.assertIn('href="../index.html#day-2026-07-20"', html)
        self.assertNotIn('<ol class="timeline">', html)

        overview = (entry.parent / "technical/timeline/index.html").read_text()

        self.assertIn("Июль 2026", overview)
        self.assertEqual(overview.count('id="day-2026-07-20"'), 1)
        self.assertIn('href="./2026-07-22/index.html"', overview)
        self.assertNotIn('href="./2026-07-19/index.html"', overview)

        last = (entry.parent / "technical/timeline/2026-07-22/index.html").read_text()

        self.assertIn("нет выбранных типов событий", last)
        self.assertNotIn("PRIVATE_UNKNOWN", last)

        second = ReportFixture.export_report(result, self.root / "second")

        for path in entry.parent.rglob("*.html"):
            self.assertEqual(path.read_bytes(), (second.parent / path.relative_to(entry.parent)).read_bytes())

        info = json.loads((self.root / "report/report-manifest.json").read_text())

        self.assertEqual(info["timeline_version"], "3")
        self.assertIn("technical/timeline/2026-07-20/index.html", info["public_sha256"])

        english = ReportFixture.export_report(result, self.root / "english", report_language = "en")
        english_calendar = (english.parent / "technical/timeline/index.html").read_text()

        self.assertIn("July 2026", english_calendar)
        self.assertIn("Events: 0", english_calendar)
        self.assertIn("Unknown: 1", english_calendar)

    def test_history_boundary_does_not_report_a_clock_regression(self):
        from poe_log_analyze.stages.composition.TimelineBuilder import TimelineBuilder
        import hashlib
        import json

        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as temporary:
            path = Path(temporary)/'lines.jsonl'
            rows = [{'line_number': n, 'record_id': n, 'status': 'recognized', 'type': 'blank',
                     'timestamp': stamp, 'history_boundary': boundary}
                    for n,(stamp,boundary) in enumerate([
                        ('2026-09-02T00:00:00+00:00', True),
                        ('2026-09-01T00:00:00+00:00', True),
                        ('2026-08-31T00:00:00+00:00', False)], 1)]
            path.write_bytes(b''.join(json.dumps(row).encode()+b'\n' for row in rows))

            model = TimelineBuilder.build_timeline(path, 'UTC', hashlib.sha256(path.read_bytes()).hexdigest())

            self.assertEqual(model['clock_regressions'], 1)
            self.assertEqual(model['total_lines'], 3)
