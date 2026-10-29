"""Prevent silent omission of native libraries from notices."""

import hashlib
import xml.etree.ElementTree as ET
import unittest

from pathlib import Path
from tempfile import TemporaryDirectory

from poe_log_analyze.tooling.LicenseTextArchive import LicenseTextArchive
from poe_log_analyze.tooling.NativeLicenseCatalogue import NativeLicenseCatalogue


class NativeLicenseCatalogueTests(unittest.TestCase):
    """Synthetic binaries verify notice links to the actual build."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "licenses").mkdir()
        self.library = self.root / "libsynthetic.so.1"
        self.library.write_bytes(b"synthetic-library")
        archive = LicenseTextArchive(metadata = {"libraries": {self.library.name: {
            "notice": "native/synthetic/copyright", "original_sha256": hashlib.sha256(self.library.read_bytes()).hexdigest()}}})
        archive.add("native/synthetic/copyright", b"synthetic-notice")
        archive.write(self.root / "licenses/Native.txt", self.root / "licenses/Native.json")
        self.report = self.root / "report.xml"
        tree = ET.Element("report")
        ET.SubElement(tree, "included_dll", {"name": self.library.name, "dest_path": self.library.name,
                                            "source_path": str(self.library), "ignored": "no"})
        ET.ElementTree(tree).write(self.report)

    def test_actual_native_library_gets_its_original_notice(self):
        archive = LicenseTextArchive()
        NativeLicenseCatalogue.append(self.root, self.report, archive)

        self.assertEqual(archive.entries[0]["name"], "native/synthetic/copyright")
        self.assertIn(self.library.name, archive.metadata["native_libraries"])

    def test_changed_native_library_requires_review(self):
        self.library.write_bytes(b"changed")

        with self.assertRaisesRegex(ValueError, "changed"):
            NativeLicenseCatalogue.append(self.root, self.report, LicenseTextArchive())

    def test_unknown_native_library_is_not_ignored(self):
        tree = ET.parse(self.report)
        tree.getroot()[0].set("name", "libunknown.so")
        tree.write(self.report)

        with self.assertRaisesRegex(ValueError, "No validated"):
            NativeLicenseCatalogue.append(self.root, self.report, LicenseTextArchive())
