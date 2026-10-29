"""Fail closed when copied Windows DLLs lose their reviewed provenance."""

import hashlib
import platform
import shutil
import unittest
import xml.etree.ElementTree as ET

from pathlib import Path
from tempfile import TemporaryDirectory

from poe_log_analyze.tooling.LicenseTextArchive import LicenseTextArchive
from poe_log_analyze.tooling.WindowsNativeCatalogue import WindowsNativeCatalogue


class WindowsNativeCatalogueTests(unittest.TestCase):
    """Synthetic bytes exercise the source, notice, compiler, and shipped-file chain."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.python = self.root / "python"
        self.distribution = self.root / "application"
        self.python.mkdir()
        self.distribution.mkdir()
        (self.root / "licenses").mkdir()
        self.report = self.root / "report.xml"
        self.compilation = ET.Element("report", {"completion": "yes", "mode": "standalone"})
        self.catalogue = LicenseTextArchive(metadata = {
            "target": "Windows", "architecture": "x86_64", "python": platform.python_version(),
            "libraries": {},
        })
        self.catalogue.add("native/windows/synthetic/LICENSE", b"Original synthetic notice\r\n")

        for name, relative in (("python314.dll", "python314.dll"),
                               ("libsynthetic.dll", "DLLs/libsynthetic.dll")):
            source = self.python / relative
            source.parent.mkdir(parents = True, exist_ok = True)
            source.write_bytes(("Synthetic DLL: " + name).encode())
            shutil.copyfile(source, self.distribution / name)
            self.catalogue.metadata["libraries"][name] = {
                "component": name, "version": "1.0", "python_relative_path": relative,
                "original_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "notices": ["native/windows/synthetic/LICENSE"],
                "sources": ["https://example.org/synthetic-source"],
            }
            ET.SubElement(self.compilation, "included_dll", {
                "name": name, "dest_path": name,
                "source_path": "${sys.real_prefix}\\" + relative.replace("/", "\\"), "ignored": "no",
            })

        self.save()

    def save(self):
        self.catalogue.write(self.root / "licenses/WindowsNative.txt", self.root / "licenses/WindowsNative.json")
        ET.ElementTree(self.compilation).write(self.report)

    def append(self):
        archive = LicenseTextArchive()
        result = WindowsNativeCatalogue.append(self.root, self.report, archive, self.python, self.distribution)

        return result, archive

    def test_reviewed_inputs_and_shipped_copies_preserve_original_notice_and_scope(self):
        summary, archive = self.append()

        self.assertEqual(summary["libraries"], 2)
        self.assertEqual(summary["scope"], "included_dll")
        self.assertTrue(summary["verified"])
        self.assertEqual(archive.texts, self.catalogue.texts)
        self.assertEqual(len(archive.entries), 1)
        self.assertEqual(archive.metadata["windows_native_sources"]["python"], platform.python_version())
        self.assertEqual(archive.metadata["windows_compilation_report_sha256"], hashlib.sha256(self.report.read_bytes()).hexdigest())
        self.assertEqual(set(archive.metadata["native_libraries"]), {"python314.dll", "libsynthetic.dll"})
        self.assertEqual(WindowsNativeCatalogue.verify_distribution(self.distribution, archive), summary)

    def test_modified_original_and_shipped_copy_are_independently_rejected(self):
        for path in (self.python / "python314.dll", self.distribution / "python314.dll"):
            original = path.read_bytes()
            path.write_bytes(b"Changed synthetic DLL")

            with self.subTest(path = path), self.assertRaisesRegex(ValueError, "changed"):
                self.append()

            path.write_bytes(original)

    def test_unknown_and_duplicate_compiler_libraries_are_rejected(self):
        node = self.compilation[0]
        original = node.attrib["name"]
        node.set("name", "unknown.dll")
        self.save()

        with self.assertRaisesRegex(ValueError, "Unknown or duplicate"):
            self.append()

        node.set("name", original)
        ET.SubElement(self.compilation, "included_dll", dict(node.attrib, name = original.upper()))
        self.save()

        with self.assertRaisesRegex(ValueError, "Unknown or duplicate"):
            self.append()

    def test_unreported_and_missing_shipped_dlls_are_rejected(self):
        unexpected = self.distribution / "unexpected.dll"
        unexpected.write_bytes(b"Synthetic unreported DLL")

        with self.assertRaisesRegex(ValueError, "inventory"):
            self.append()

        unexpected.unlink()
        (self.distribution / "python314.dll").unlink()

        with self.assertRaisesRegex(ValueError, "inventory"):
            self.append()

    def test_duplicate_and_unsafe_destinations_are_rejected(self):
        for destination in ("PYTHON314.DLL", "../escape.dll", "/absolute.dll", "C:/drive.dll"):
            self.compilation[1].set("dest_path", destination)
            self.save()

            with self.subTest(destination = destination), self.assertRaises(ValueError):
                self.append()

    def test_source_outside_python_is_rejected_even_with_identical_bytes(self):
        source = self.root / "python314.dll"
        shutil.copyfile(self.python / source.name, source)
        self.compilation[0].set("source_path", str(source))
        self.save()

        with self.assertRaisesRegex(ValueError, "outside its reviewed Python source"):
            self.append()

    def test_wrong_python_and_missing_notice_or_source_are_rejected(self):
        self.catalogue.metadata["python"] = "0.0.0"
        self.save()

        with self.assertRaisesRegex(ValueError, "installed Python"):
            self.append()

        self.catalogue.metadata["python"] = platform.python_version()
        entry = self.catalogue.metadata["libraries"]["python314.dll"]

        for field, value in (("notices", ["missing"]), ("sources", []), ("version", "")):
            original = entry[field]
            entry[field] = value
            self.save()

            with self.subTest(field = field), self.assertRaisesRegex(ValueError, "incomplete provenance"):
                self.append()

            entry[field] = original

    def test_tampered_original_notice_archive_is_rejected(self):
        with (self.root / "licenses/WindowsNative.txt").open("ab") as stream:
            stream.write(b"Changed notice archive")

        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.append()

    def test_incomplete_and_empty_compiler_reports_are_rejected(self):
        self.compilation.set("completion", "no")
        self.save()

        with self.assertRaisesRegex(ValueError, "complete standalone"):
            self.append()

        self.compilation.set("completion", "yes")

        for node in self.compilation:
            node.set("ignored", "yes")

        self.save()

        with self.assertRaisesRegex(ValueError, "no reviewed Windows"):
            self.append()

    def test_changed_shipped_dll_is_rejected_on_later_verification(self):
        _, archive = self.append()
        (self.distribution / "python314.dll").write_bytes(b"Changed after staging")

        with self.assertRaisesRegex(ValueError, "Shipped Windows native library changed"):
            WindowsNativeCatalogue.verify_distribution(self.distribution, archive)

    def test_missing_notice_and_misleading_scope_are_rejected_on_later_verification(self):
        summary, archive = self.append()
        archive.metadata["windows_native_provenance"] = dict(summary, scope = "all_native_code")

        with self.assertRaisesRegex(ValueError, "provenance is required"):
            WindowsNativeCatalogue.verify_distribution(self.distribution, archive)

        archive.metadata["windows_native_provenance"] = summary
        archive.entries.clear()

        with self.assertRaisesRegex(ValueError, "native notices"):
            WindowsNativeCatalogue.verify_distribution(self.distribution, archive)
