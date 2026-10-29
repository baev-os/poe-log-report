"""Cancellation, import, and storage-query checks using synthetic data."""

import unittest

from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from poe_log_analyze.stages.parsing.LogAnalysisService import LogAnalysisService

from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext


class ControlTests(unittest.TestCase):
    """Cancellation publishes no partial result and leaves input unchanged."""

    def test_cancel_before_and_during_analysis(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "log.txt"
            raw = b"\nunknown\n" * 100
            source.write_bytes(raw)
            event = Event()

            for initial in (True, False):
                event.set() if initial else event.clear()
                control = ExecutionContext(cancelled = event.is_set, progress = lambda _: event.set())

                with self.assertRaises(GenerationCancelled):
                    LogAnalysisService.analyze(source, root / "result", control = control)

                self.assertFalse((root / "result").exists())
                self.assertEqual(list(root.glob(".analysis-*")), [])
                self.assertEqual(source.read_bytes(), raw)
