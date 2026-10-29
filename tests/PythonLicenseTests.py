"""CPython license discovery preserves original notice bytes."""

import sys
import unittest

from pathlib import Path
from tempfile import TemporaryDirectory

from poe_log_analyze.tooling.PythonLicense import PythonLicense


class PythonLicenseTests(unittest.TestCase):
    """Exercise upstream and Debian layouts without system dependencies."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / "build/tmp")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_upstream_installed_notice_is_used_without_rewriting(self):
        path = self.root / "LICENSE.txt"
        original = b"Synthetic original CPython notice\r\n"
        path.write_bytes(original)

        self.assertEqual(PythonLicense.find(self.root), path)
        self.assertEqual(path.read_bytes(), original)

    def test_debian_version_specific_notice_is_found(self):
        version = f"python{sys.version_info.major}.{sys.version_info.minor}"
        path = self.root / "share/doc" / version / "copyright"
        path.parent.mkdir(parents = True)
        path.write_bytes(b"Synthetic Debian CPython notice\n")

        self.assertEqual(PythonLicense.find(self.root), path)

    def test_missing_empty_and_binary_notices_fail(self):
        with self.assertRaisesRegex(ValueError, "not found"):
            PythonLicense.find(self.root)

        for original in (b" \n", b"Synthetic\x00binary"):
            (self.root / "LICENSE").write_bytes(original)

            with self.assertRaisesRegex(ValueError, "empty or contains binary"):
                PythonLicense.find(self.root)
