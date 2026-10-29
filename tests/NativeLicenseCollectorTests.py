"""Per-build native notices must trace back to actual installed package bytes."""

import base64
import hashlib
import unittest
import xml.etree.ElementTree as ET

from importlib import metadata
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from poe_log_analyze.tooling.LicenseTextArchive import LicenseTextArchive
from poe_log_analyze.tooling.NativeLicenseCatalogue import NativeLicenseCatalogue
from poe_log_analyze.tooling.NativeLicenseCollector import NativeLicenseCollector


class NativeLicenseCollectorTests(unittest.TestCase):
    """Synthetic libraries and original notices exercise ownership and tampering."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / "build/tmp")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.library = self.root / "libsynthetic.so.1"
        self.library.write_bytes(b"Synthetic native library")
        self.report = self.root / "compilation-report.xml"
        tree = ET.Element("report")
        ET.SubElement(tree, "included_dll", {"name": self.library.name, "source_path": str(self.library)})
        ET.ElementTree(tree).write(self.report)
        self.destination = self.root / "collected/Native.json"

    def test_debian_notices_preserve_bytes_and_common_license_references(self):
        documentation = self.root / "doc"
        copyright_path = documentation / "synthetic/copyright"
        copyright_path.parent.mkdir(parents = True)
        original = b"Synthetic copyright\r\nSee /usr/share/common-licenses/Synthetic.\r\n"
        copyright_path.write_bytes(original)
        common = self.root / "common"
        common.mkdir()
        (common / "Synthetic").write_bytes(b"Synthetic common license\n")

        with patch.object(NativeLicenseCollector, "debian_package", return_value = ("synthetic:amd64", "1.2.3")), \
                patch.object(NativeLicenseCollector, "DOCUMENTATION", documentation), \
                patch.object(NativeLicenseCollector, "COMMON_LICENSES", common):
            NativeLicenseCollector.collect(self.report, self.destination)

        archive = LicenseTextArchive.read(self.destination.with_suffix(".txt"), self.destination)
        library = archive.metadata["libraries"][self.library.name]

        self.assertEqual(library["supplier"], "dpkg")
        self.assertEqual(library["version"], "1.2.3")
        self.assertEqual(library["original_sha256"], hashlib.sha256(self.library.read_bytes()).hexdigest())
        self.assertIn(original, archive.texts.values())
        self.assertIn("native/common-licenses/Synthetic", library["notices"])

        staged = LicenseTextArchive()
        NativeLicenseCatalogue.append(self.root, self.report, staged, self.destination)

        self.assertEqual(staged.texts, archive.texts)
        self.library.write_bytes(b"Changed native library")

        with self.assertRaisesRegex(ValueError, "changed"):
            NativeLicenseCatalogue.append(self.root, self.report, LicenseTextArchive(), self.destination)

    def wheel(self, correct_record = True):
        relative = metadata.PackagePath(self.library.name)
        digest = base64.urlsafe_b64encode(hashlib.sha256(self.library.read_bytes()).digest()).decode().rstrip("=")
        relative.hash = SimpleNamespace(mode = "sha256", value = digest if correct_record else "wrong")
        license_path = metadata.PackagePath("example.dist-info/licenses/LICENSE")
        path = self.root / license_path
        path.parent.mkdir(parents = True)
        path.write_bytes(b"Synthetic bundled wheel library licenses\r\n")
        distribution = Mock(files = [relative, license_path], metadata = {"Name": "Example"}, version = "1.2.3")
        distribution.locate_file.side_effect = lambda file: self.root / file

        return distribution

    def test_wheel_record_and_original_bundled_license_identify_library(self):
        distribution = self.wheel()

        with patch.object(NativeLicenseCollector, "debian_package", return_value = None), \
                patch("importlib.metadata.distributions", return_value = [distribution]):
            NativeLicenseCollector.collect(self.report, self.destination)

        archive = LicenseTextArchive.read(self.destination.with_suffix(".txt"), self.destination)
        entry = archive.metadata["libraries"][self.library.name]

        self.assertEqual(entry["supplier"], "python-wheel")
        self.assertEqual(entry["package"], "Example")
        self.assertIn(b"Synthetic bundled wheel library licenses\r\n", archive.texts.values())

    def test_wheel_record_mismatch_and_unowned_library_are_rejected(self):
        distribution = self.wheel(False)

        with patch("importlib.metadata.distributions", return_value = [distribution]):
            with self.assertRaisesRegex(ValueError, "wheel RECORD"):
                NativeLicenseCollector.wheel_notices(self.library, LicenseTextArchive())

        with patch("importlib.metadata.distributions", return_value = []):
            with self.assertRaisesRegex(ValueError, "owns native library"):
                NativeLicenseCollector.wheel_notices(self.library, LicenseTextArchive())

        self.assertFalse(self.destination.exists())

    def test_installed_debian_package_identity_is_required(self):
        self.package_status = "installed"

        with patch("subprocess.check_output", side_effect = self.debian_query):
            self.assertEqual(NativeLicenseCollector.debian_package(self.library), ("synthetic:amd64", "1.2.3"))

        self.package_status = "not-installed"

        with patch("subprocess.check_output", side_effect = self.debian_query):
            with self.assertRaises(ValueError):
                NativeLicenseCollector.debian_package(self.library)

    def debian_query(self, arguments, **kwargs):
        return ("synthetic:amd64: " + str(self.library) + "\n" if "--search" in arguments
                else "synthetic:amd64\t1.2.3\t" + self.package_status)
