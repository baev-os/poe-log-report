"""Application commands and requests without creating a GUI window."""

import unittest

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.ProgressUpdate import ProgressUpdate


class ApplicationTests(unittest.TestCase):
    """Application progress contract without creating a GUI window."""

    def test_progress_is_typed_and_keeps_callback_contract(self):
        updates = []

        ExecutionContext(progress = updates.append).report("Разбор", 10, 20, 2, force = True)

        self.assertEqual(updates, [ProgressUpdate("Разбор", 10, 20, 2)])
