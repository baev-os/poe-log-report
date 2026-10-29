"""JSON compatibility and memory usage when writing large projections."""

import json
import tracemalloc
import unittest

from pathlib import Path
from tempfile import TemporaryDirectory

from poe_log_analyze.runtime.JsonFiles import JsonFiles


class JsonFilesTests(unittest.TestCase):
    """Preserve format bytes without a complete serialized model copy."""

    def test_bytes_match_existing_format(self):
        cases = [
            {},
            {"я": "Область 🗺️", "a": [None, True, False, 0, -3, 1.25, -0.0, 1e30],
             "nested": {"z": [], "a": {"text": '<tag>\n\r\t"\\\u0000'}},
             "empty": "", "unicode": "é漢字\u2028"},
            {"rows": [{"z": 2, "a": 1}] * 3},
        ]

        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "view.json"

            for value in cases:
                with self.subTest(value = value):
                    expected = (json.dumps(value, ensure_ascii = False, sort_keys = True, indent = 2) + "\n").encode("utf-8")
                    path.write_bytes(b"old contents" * 1000)
                    JsonFiles.write_json(path, value)

                    self.assertEqual(path.read_bytes(), expected)
                    self.assertEqual(json.loads(path.read_bytes()), value)

    def test_large_projection_has_no_full_serialized_copy_in_memory(self):
        # Create the model before measuring: constrain only additional writer memory.
        value = {"rows": [{"line": number, "message": "Область 🗺️" * 32} for number in range(8000)]}

        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "events.json"
            tracemalloc.start()

            try:
                JsonFiles.write_json(path, value)
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()

            self.assertGreater(path.stat().st_size, 4 * 1024 * 1024)
            self.assertLess(peak, 1024 * 1024)
            self.assertEqual(json.loads(path.read_bytes()), value)
