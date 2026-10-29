"""Checks use synthetic data without the user's original log."""

import hashlib
import json
import os
import unittest

from base64 import b64decode
from contextlib import redirect_stderr, redirect_stdout

from io import StringIO

from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import patch

from poe_log_analyze.cli.AnalysisCli import AnalysisCli

from poe_log_analyze.stages.parsing.LogAnalysisService import LogAnalysisService
from poe_log_analyze.stages.parsing.LogParser import LogParser

from AnalysisFixture import AnalysisFixture


class AnalysisTests(unittest.TestCase):
    """File-pipeline and interface checks."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / "build")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.input = self.root / "Client.txt"
        self.input.write_bytes(b"\n" + AnalysisFixture.message("[WINDOW] Lost focus") + b"unknown\n\xff")

    def test_previously_edited_input_is_valid_when_unchanged_during_analysis(self):
        raw = AnalysisFixture.message("[WINDOW] Lost focus")
        self.input.write_bytes(raw)
        os.utime(self.input, ns = (1_700_000_000_000_000_000, 1_700_000_000_000_000_000))

        coverage = LogAnalysisService.analyze(self.input, self.root / "edited")

        self.assertEqual(coverage["input_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(coverage["input_bytes"], len(raw))
        self.assertTrue(coverage["recognition_complete"])

    def test_accounting_manifest_and_repeatability(self):
        before = self.input.read_bytes()
        first, second = self.root / "first", self.root / "second"
        coverage = LogAnalysisService.analyze(self.input, first)
        LogAnalysisService.analyze(self.input, second)

        self.assertEqual(coverage["total_lines"], 4)
        self.assertEqual(coverage["recognized_lines"], 2)
        self.assertEqual(coverage["unknown_lines"], 1)
        self.assertEqual(coverage["error_lines"], 1)
        self.assertTrue(coverage["accounting_complete"])
        self.assertFalse(coverage["recognition_complete"])

        rows = [json.loads(line) for line in (first / "lines.jsonl").read_text().splitlines()]

        self.assertEqual(b"".join(b64decode(row["raw_base64"]) for row in rows), before)
        self.assertEqual(self.input.read_bytes(), before)

        manifest = json.loads((first / "manifest.json").read_text())

        self.assertEqual(manifest["input"]["sha256"], hashlib.sha256(before).hexdigest())
        self.assertTrue(manifest["code"]["files_sha256"])

        for filename, expected in manifest["artifacts_sha256"].items():
            self.assertEqual(hashlib.sha256((first / filename).read_bytes()).hexdigest(), expected)
            self.assertEqual((first / filename).read_bytes(), (second / filename).read_bytes())

        self.assertEqual(len((first / "diagnostics.jsonl").read_text().splitlines()), 2)

    def test_cli_strict_mode_preserves_diagnostics(self):
        output = self.root / "strict"

        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            code = AnalysisCli.main(["--input", str(self.input), "--output", str(output), "--require-complete"])

        self.assertEqual(code, 2)
        self.assertTrue((output / "coverage.md").is_file())

    def test_complete_and_empty_input(self):
        for i, raw in enumerate((b"", b"\n", AnalysisFixture.message("[WINDOW] Lost focus"))):
            self.input.write_bytes(raw)

            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                code = AnalysisCli.main(["--input", str(self.input), "--output", str(self.root / str(i)), "--require-complete"])

            self.assertEqual(code, 0)

        coverage = json.loads((self.root / "0/coverage.json").read_text())

        self.assertIsNone(coverage["recognized_fraction"])
        self.assertEqual(coverage["total_lines"], 0)

    def test_existing_output_is_untouched(self):
        output = self.root / "existing"
        output.mkdir()
        marker = output / "marker"
        marker.write_text("сохранить")

        with self.assertRaises(FileExistsError):
            LogAnalysisService.analyze(self.input, output)

        self.assertEqual(list(output.iterdir()), [marker])
        self.assertEqual(marker.read_text(), "сохранить")

    def test_input_cannot_be_inside_output(self):
        with self.assertRaises(ValueError):
            LogAnalysisService.analyze(self.input, self.root)

        self.assertTrue(self.input.exists())

    def test_changed_input_does_not_publish_results(self):
        self._original = LogParser.iter_records


        output = self.root / "changed"

        with patch("poe_log_analyze.stages.parsing.LogParser.LogParser.iter_records", self._changing), self.assertRaises(ValueError):
            LogAnalysisService.analyze(self.input, output)

        self.assertFalse(output.exists())
        self.assertEqual(list(self.root.glob(".analysis-*")), [])

    def test_broken_ledger_does_not_publish_results(self):
        self._original_operation = LogParser.iter_records

        output = self.root / "broken"

        with patch("poe_log_analyze.stages.parsing.LogParser.LogParser.iter_records", self._broken), self.assertRaises(ValueError):
            LogAnalysisService.analyze(self.input, output)

        self.assertFalse(output.exists())

    def test_cli_missing_input(self):
        with redirect_stderr(StringIO()):
            code = AnalysisCli.main(["--input", str(self.root / "missing"), "--output", str(self.root / "out")])

        self.assertEqual(code, 1)
        self.assertFalse((self.root / "out").exists())

    def _changing(self, source, zone):
        yield from self._original(source, zone)

        with self.input.open("ab") as file:
            file.write(b"changed")

    def _broken(self, source, zone):
        for row in self._original_operation(source, zone):
            row["byte_start"] += 1
            yield row

    @classmethod
    def setUpClass(cls):
        """Create a local directory for temporary test results."""

        (Path(__file__).resolve().parents[1] / "build").mkdir(exist_ok = True)
