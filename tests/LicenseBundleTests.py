"""Complete notices and exclusion of the previous GUI from the new distribution."""

import hashlib
import json
import platform
import unittest
import xml.etree.ElementTree as ET

from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import Mock, patch

from poe_log_analyze.tooling.LicenseBundleWriter import LicenseBundleWriter
from poe_log_analyze.tooling.LicenseTextArchive import LicenseTextArchive


class LicenseBundleTests(unittest.TestCase):
    """Synthetic texts verify byte preservation and required files."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

        for name in ("LICENSE", "THIRD_PARTY_NOTICES.md", "licenses/README.md", "licenses/GAME_DATA.md",
                     "licenses/Exile-UI.txt", "site/static/vendor/bootstrap-LICENSE.txt", "reports/fonts/LICENSE.txt",
                     "licenses/WINDOWS_RUNTIME.md", "python.txt", "dependency/LICENSE"):
            self.write(name, b"Synthetic notice\r\n")

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents = True, exist_ok = True)
        path.write_bytes(content)

    def stage(self, dependencies = ("example",), system = "Linux"):
        options = {}

        if system == "Windows":
            source = self.root / "DLLs/synthetic.dll"
            self.write("DLLs/synthetic.dll", b"Synthetic native library")
            self.write("compiled/synthetic.dll", source.read_bytes())
            catalogue = LicenseTextArchive(metadata = {
                "target": "Windows", "architecture": "x86_64", "python": platform.python_version(),
                "libraries": {"synthetic.dll": {
                    "component": "synthetic", "version": "1.0", "python_relative_path": "DLLs/synthetic.dll",
                    "original_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    "notices": ["native/windows/synthetic/LICENSE"], "sources": ["https://example.org/synthetic"],
                }},
            })
            catalogue.add("native/windows/synthetic/LICENSE", b"Synthetic original native notice\r\n")
            catalogue.write(self.root / "licenses/WindowsNative.txt", self.root / "licenses/WindowsNative.json")
            compilation = ET.Element("report", {"completion": "yes", "mode": "standalone"})
            ET.SubElement(compilation, "included_dll", {
                "name": source.name, "source_path": str(source), "dest_path": source.name, "ignored": "no",
            })
            report = self.root / "report.xml"
            ET.ElementTree(compilation).write(report)
            options = {"native_report": report, "distribution": self.root / "compiled"}

        return LicenseBundleWriter.stage(self.root, self.root / "bundle", dependencies,
                                         self.root / "python.txt", system = system, **options)

    def test_notices_and_manifest_include_actual_copied_bytes(self):
        distribution = Mock(files = [Path("example.dist-info/licenses/LICENSE")])
        distribution.locate_file.return_value = self.root / "dependency/LICENSE"

        with patch("importlib.metadata.version", return_value = "1"), patch("importlib.metadata.distribution", return_value = distribution):
            result = self.stage()

        for name, digest in result["files_sha256"].items():
            self.assertEqual(hashlib.sha256((self.root / "bundle" / name).read_bytes()).hexdigest(), digest)

        archive = LicenseTextArchive.read(self.root / "bundle/THIRD_PARTY_LICENSES.txt", self.root / "bundle/sources.json")

        self.assertIn("Bootstrap/LICENSE.txt", {entry["name"] for entry in archive.entries})
        self.assertIn("Exile-UI/LICENSE.md", {entry["name"] for entry in archive.entries})
        self.assertEqual(len(result["files_sha256"]), 6)
        self.assertEqual(result["gui"], "tkinter")
        self.assertLess(result["unique_texts"], result["notices"])
        self.assertNotIn("qt_version", result)

    def test_package_without_licenses_and_missing_python_license_are_rejected(self):
        with patch("importlib.metadata.version", return_value = "1"), patch("importlib.metadata.distribution", return_value = Mock(files = [])):
            with self.assertRaisesRegex(ValueError, "contains no license texts"):
                self.stage()

        self.assertFalse((self.root / "bundle/manifest.json").exists())

        (self.root / "python.txt").unlink()

        with self.assertRaises(FileNotFoundError):
            LicenseBundleWriter.stage(self.root, self.root / "missing", (), self.root / "python.txt", system = "Linux")

    def test_roundtrip_preserves_bytes_and_attributions_while_deduplicating(self):
        archive = LicenseTextArchive(metadata = {"version": "synthetic"})
        original = "Синтетический текст\r\n".encode("utf-8")
        archive.add("first", original)
        archive.add("second", original)
        text, manifest = self.root / "texts.txt", self.root / "texts.json"
        archive.write(text, manifest)
        loaded = LicenseTextArchive.read(text, manifest)

        self.assertEqual(loaded.texts, archive.texts)
        self.assertEqual(loaded.entries, archive.entries)
        self.assertEqual(len(loaded.texts), 1)

        text.write_bytes(b"changed")

        with self.assertRaisesRegex(ValueError, "hash"):
            LicenseTextArchive.read(text, manifest)

        archive.write(text, manifest)
        data = json.loads(manifest.read_text(encoding = "utf-8"))
        next(iter(data["texts"].values()))["offset"] = -1
        manifest.write_text(json.dumps(data), encoding = "utf-8")

        with self.assertRaisesRegex(ValueError, "boundaries"):
            LicenseTextArchive.read(text, manifest)

    def test_build_only_tool_is_not_in_runtime_notices(self):
        with patch("importlib.metadata.version", return_value = "1"), patch("importlib.metadata.distribution") as distribution:
            self.stage(("patchelf",))

        distribution.assert_not_called()
        sources = json.loads((self.root / "bundle/sources.json").read_text(encoding = "utf-8"))

        self.assertNotIn("patchelf", sources["metadata"]["dependencies"])

    def test_windows_uses_original_tcl_and_tk_notices_from_python(self):
        for component in ("tcl", "tk"):
            self.write(f"tcl/{component}8.6/license.terms", (component + "\r\nOriginal notice").encode("utf-8"))

        result = self.stage((), "Windows")
        archive = LicenseTextArchive.read(self.root / "bundle/THIRD_PARTY_LICENSES.txt", self.root / "bundle/sources.json")

        self.assertEqual(result["windows_native_provenance"]["scope"], "included_dll")
        self.assertEqual(result["windows_native_provenance"], archive.metadata["windows_native_provenance"])
        self.assertEqual((self.root / "bundle/WINDOWS_RUNTIME.md").read_bytes(),
                         (self.root / "licenses/WINDOWS_RUNTIME.md").read_bytes())

        for component in ("tcl", "tk"):
            entry = next(row for row in archive.entries if row["name"] == f"toolkit/{component}/license.terms")

            self.assertEqual(archive.texts[entry["sha256"]], (component + "\r\nOriginal notice").encode("utf-8"))
            self.assertEqual(entry["details"]["directory"], component + "8.6")

    def test_windows_without_toolkit_licenses_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "license.*tcl"):
            self.stage((), "Windows")

    def test_windows_dependencies_keep_the_compiled_distribution_for_native_verification(self):
        self.toolkit_catalogue()
        installed = Mock(files = [Path("example.dist-info/licenses/LICENSE")])
        installed.locate_file.return_value = self.root / "dependency/LICENSE"

        with patch("importlib.metadata.version", return_value = "1"), patch("importlib.metadata.distribution", return_value = installed):
            result = self.stage(("example",), "Windows")

        self.assertTrue(result["windows_native_provenance"]["verified"])
        self.assertEqual(result["windows_native_provenance"]["libraries"], 1)

    def test_windows_without_compiler_report_cannot_claim_verified_notices(self):
        self.toolkit_catalogue()

        with self.assertRaisesRegex(ValueError, "require the compiler report"):
            LicenseBundleWriter.stage(self.root, self.root / "bundle", (), self.root / "python.txt", system = "Windows")

        self.assertFalse((self.root / "bundle/manifest.json").exists())

    def toolkit_catalogue(self):
        catalogue = LicenseTextArchive(metadata = {"versions": {"tcl": "8.6.15", "tk": "8.6.15"}})

        for component in ("tcl", "tk"):
            script = "init.tcl" if component == "tcl" else "tk.tcl"
            self.write(f"tcl/{component}8.6/{script}",
                       f"package require -exact {component.title()} 8.6.15\n".encode())
            catalogue.add(f"toolkit/{component}/license.terms", (component + " original\r\n").encode(),
                          {"source": "Synthetic pinned source"})

        catalogue.write(self.root / "licenses/TclTk.txt", self.root / "licenses/TclTk.json")

    def test_windows_installer_without_notices_uses_exact_matching_source_version(self):
        self.toolkit_catalogue()

        self.stage((), "Windows")

        archive = LicenseTextArchive.read(self.root / "bundle/THIRD_PARTY_LICENSES.txt", self.root / "bundle/sources.json")

        for component in ("tcl", "tk"):
            entry = next(row for row in archive.entries if row["name"] == f"toolkit/{component}/license.terms")
            self.assertEqual(archive.texts[entry["sha256"]], (component + " original\r\n").encode())
            self.assertEqual(entry["details"]["version"], "8.6.15")
            self.assertEqual(entry["details"]["source"], "Synthetic pinned source")

    def test_windows_unknown_toolkit_version_is_rejected_without_manifest(self):
        self.toolkit_catalogue()
        self.write("tcl/tk8.6/tk.tcl", b"package require -exact Tk 8.6.16\n")

        with self.assertRaisesRegex(ValueError, "version.*tk"):
            self.stage((), "Windows")

        self.assertFalse((self.root / "bundle/manifest.json").exists())

    def test_distribution_rejects_old_gui_and_keeps_visible_notices(self):
        distribution = self.root / "dist"
        distribution.mkdir()
        LicenseBundleWriter.finish_distribution(self.root, distribution)

        self.assertEqual((distribution / "LICENSE").read_bytes(), (self.root / "LICENSE").read_bytes())

        for name in ("libQt6Core.so.6", "Qt6Widgets.dll", "PySide6", "shiboken6"):
            path = distribution / name
            path.touch()

            with self.assertRaisesRegex(ValueError, "Excluded GUI library"):
                LicenseBundleWriter.finish_distribution(self.root, distribution)

            path.unlink()
