"""Atomic unified analysis run with mandatory HTML."""

import unittest

from pathlib import Path
from tempfile import TemporaryDirectory

from poe_log_analyze.Bootstrap import Bootstrap

from unittest.mock import patch

from poe_log_analyze.core.request.ReportRequest import ReportRequest
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.stages.verification.VerifyReport import VerifyReport


class PipelineTests(unittest.TestCase):
    """Export failure and cancellation leave no published partial run."""

    def setUp(self):
        build = Path(__file__).resolve().parents[1] / "build"
        build.mkdir(exist_ok = True)
        self.temp = TemporaryDirectory(dir = build)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.log"
        self.source.write_bytes(b"unknown\n")
        self.command = ReportRequest((self.source,), self.root / "runs/run-one")

    def test_failed_report_cleans_analysis_and_staging(self):
        with patch("poe_log_analyze.stages.rendering.RenderReport.RenderReport.execute", side_effect = RuntimeError("HTML")):
            with self.assertRaisesRegex(RuntimeError, "HTML"):
                Bootstrap.report_generator().generate(self.command, ExecutionContext())

        self.assertEqual(list((self.root / "runs").iterdir()), [])
        self.assertEqual(self.source.read_bytes(), b"unknown\n")

    def test_existing_run_is_preserved(self):
        self.command.output.mkdir(parents = True)
        marker = self.command.output / "keep"
        marker.write_text("existing")

        with self.assertRaises(FileExistsError):
            Bootstrap.report_generator().generate(self.command, ExecutionContext())

        self.assertEqual(marker.read_text(), "existing")

    def test_cancel_after_report_before_publication_cleans_both(self):
        self._cancelled = False
        self._original_operation = VerifyReport().execute

        with patch("poe_log_analyze.stages.verification.VerifyReport.VerifyReport.execute", side_effect = self._export_then_cancel):
            with self.assertRaises(GenerationCancelled):
                Bootstrap.report_generator().generate(self.command, ExecutionContext(cancelled = lambda: self._cancelled))

        self.assertEqual(list((self.root / "runs").iterdir()), [])

    def test_unknown_lines_still_produce_report(self):
        result = Bootstrap.report_generator().generate(self.command, ExecutionContext())

        self.assertTrue((result.directory / "lines.jsonl").is_file())
        self.assertTrue(result.report_path.is_file())
        self.assertEqual(list((self.root / "runs").iterdir()), [self.command.output])

    def _export_then_cancel(self, *args, **kwargs):
        result = self._original_operation(*args, **kwargs)
        self._cancelled = True

        return result
