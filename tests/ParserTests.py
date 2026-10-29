"""Checks use synthetic data without the user's original log."""

import unittest

from base64 import b64decode
from io import BytesIO
from pathlib import Path

from zoneinfo import ZoneInfo

from poe_log_analyze.stages.parsing.LogParser import LogParser

from AnalysisFixture import AnalysisFixture


class ParserTests(unittest.TestCase):
    """Boundary, recognition, and continuation-link checks."""

    def records(self, raw: bytes) -> list[dict]:
        return list(LogParser.iter_records(BytesIO(raw), ZoneInfo("Asia/Almaty")))

    def test_line_boundaries_and_lossless_bytes(self):
        raw = b"\r\nabc\rdef\x0bghi\n\xff\nlast\r"
        rows = self.records(raw)

        self.assertEqual([(r["byte_start"], r["byte_end"]) for r in rows],
                         [(0, 2), (2, 14), (14, 16), (16, 21)])
        self.assertEqual([r["line_ending"] for r in rows], ["CRLF", "LF", "LF", "none"])
        self.assertEqual([r["status"] for r in rows], ["recognized", "unknown", "error", "unknown"])
        self.assertEqual(b"".join(b64decode(r["raw_base64"]) for r in rows), raw)
        self.assertNotIn("text", rows[2])

    def test_empty_and_final_lf(self):
        self.assertEqual(self.records(b""), [])
        self.assertEqual(len(self.records(b"\n")), 1)
        self.assertEqual(len(self.records(b"x\n")), 1)
        self.assertEqual(len(self.records(b"x")), 1)
        self.assertEqual(len(self.records(b"x\n\n")), 2)

    def test_header_is_not_recognition(self):
        row = self.records(AnalysisFixture.message("Неизвестное сообщение"))[0]

        self.assertEqual(row["status"], "unknown")
        self.assertEqual(row["type"], "message.unknown")
        self.assertEqual(row["header"]["pid"], "42")
        self.assertEqual(row["timestamp"], "2026-09-01T10:00:00+05:00")

    def test_exact_message_and_fields(self):
        valid = 'Generating level 70 area "SyntheticArea" with seed 123'
        rows = self.records(AnalysisFixture.message(valid) + AnalysisFixture.message(valid + " extra"))

        self.assertEqual(rows[0]["fields"], {"level": "70", "area": "SyntheticArea", "seed": "123"})
        self.assertEqual(rows[0]["type"], "area.generate")
        self.assertEqual(rows[1]["status"], "unknown")

    def test_all_message_rules(self):
        samples = {
            "[WINDOW] Lost focus": "window.focus",
            "Got Instance Details from login server": "instance.details",
            "Client-Safe Instance ID = 123": "instance.id",
            "Tile hash: 234": "area.tile_hash",
            "Doodad hash: 345": "area.doodad_hash",
            ": You have entered Synthetic Town.": "area.enter",
            "[SCENE] Static Walkability Texture: 4 x 8": "scene.walkability",
            "ALTERNATE TREE JEWEL: Applying modifications for jewel with alternate tree "
            "version = 1, seed = 2, and keystone selection = 3": "jewel.alternate_tree",
        }

        for text, kind in samples.items():
            with self.subTest(kind = kind):
                self.assertEqual(self.records(AnalysisFixture.message(text))[0]["type"], kind)

    def test_opening_and_invalid_timestamp(self):
        rows = self.records(b"2026/09/01 10:00:00 ***** LOG FILE OPENING *****\r\n"
                            + AnalysisFixture.message("[WINDOW] Lost focus", "2026/02/30 10:00:00"))

        self.assertEqual(rows[0]["type"], "log.open")
        self.assertEqual(rows[1]["status"], "error")
        self.assertEqual(rows[1]["type"], "timestamp.error")

    def test_multiline_and_orphans(self):
        raw = (AnalysisFixture.message("Client couldn't execute a triggered action from the server.")
               + b"action type id = 12\n"
               + AnalysisFixture.message("Instant/Triggered actionwas serialized to the client, but the client failed to execute the action.")
               + b"skill_instance_id: 1\naction_id: 2\nobject_id: 3\ntarget_id: 4\nflags: 5\n"
               + b"flags: 6\n")
        rows = self.records(raw)

        self.assertEqual([r["record_id"] for r in rows], [1, 1, 3, 3, 3, 3, 3, 3, None])
        self.assertTrue(all(r["status"] == "recognized" for r in rows[:-1]))
        self.assertEqual(rows[-1]["status"], "unknown")

    def test_interrupted_continuation_is_not_attached(self):
        header = AnalysisFixture.message("Client couldn't execute a triggered action from the server.")

        for middle in (b"\n", b"unknown\n", b"\xff\n", AnalysisFixture.message("[WINDOW] Gained focus")):
            with self.subTest(middle = middle):
                rows = self.records(header + middle + b"action type id = 12\n")

                self.assertEqual(rows[-1]["status"], "unknown")
                self.assertIsNone(rows[-1]["record_id"])

    def test_ambiguous_and_nonexistent_time(self):
        for stamp in ("2026/10/25 02:30:00", "2026/03/29 02:30:00"):
            rows = list(LogParser.iter_records(BytesIO(AnalysisFixture.message("[WINDOW] Lost focus", stamp)), ZoneInfo("Europe/Berlin")))

            self.assertEqual(rows[0]["status"], "error")

    @classmethod
    def setUpClass(cls):
        """Create a local directory for temporary test results."""

        (Path(__file__).resolve().parents[1] / "build").mkdir(exist_ok = True)
