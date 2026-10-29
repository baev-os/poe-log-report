"""Bind copied Windows DLLs to reviewed CPython inputs and original notices."""

import hashlib
import platform
import re
import xml.etree.ElementTree as ET

from pathlib import Path, PurePosixPath

from poe_log_analyze.tooling.LicenseTextArchive import LicenseTextArchive


class WindowsNativeCatalogue:
    """Reject unknown DLLs and changes to either compiler inputs or shipped copies."""

    @staticmethod
    def append(root: Path, report: Path, archive: LicenseTextArchive,
               python_root: Path, distribution: Path) -> dict:
        manifest = root / "licenses/WindowsNative.json"
        catalogue = LicenseTextArchive.read(manifest.with_suffix(".txt"), manifest)

        if (catalogue.metadata.get("target") != "Windows"
                or catalogue.metadata.get("architecture") != "x86_64"
                or catalogue.metadata.get("python") != platform.python_version()):
            raise ValueError("The Windows native catalogue does not match the installed Python")

        libraries = catalogue.metadata.get("libraries", {})
        notices = {entry["name"]: entry for entry in catalogue.entries}
        selected = {}
        wanted = set()
        python_root = python_root.resolve()
        compilation = ET.parse(report).getroot()

        if compilation.attrib.get("completion") != "yes" or compilation.attrib.get("mode") != "standalone":
            raise ValueError("A complete standalone compiler report is required for Windows native notices")

        for node in compilation.findall("included_dll"):
            if node.attrib.get("ignored") == "yes":
                continue

            name = node.attrib["name"].casefold()

            if name not in libraries or name in selected:
                raise ValueError("Unknown or duplicate Windows native library: " + name)

            entry = libraries[name]
            relative = WindowsNativeCatalogue.relative_path(entry["python_relative_path"])
            destination = WindowsNativeCatalogue.relative_path(node.attrib["dest_path"].replace("\\", "/"))
            value = node.attrib["source_path"].replace("${sys.real_prefix}", str(python_root))
            value = value.replace("${sys.prefix}", str(python_root)).replace("\\", "/")
            source = Path(value)

            if (not source.is_absolute() or not source.is_file() or source.is_symlink()
                    or not source.resolve().is_relative_to(python_root)
                    or source.resolve().relative_to(python_root).as_posix().casefold() != relative.casefold()
                    or PurePosixPath(relative).name.casefold() != name):
                raise ValueError("Windows native library is outside its reviewed Python source: " + name)

            digest = hashlib.sha256(source.read_bytes()).hexdigest()

            if digest != entry.get("original_sha256"):
                raise ValueError("Windows native library changed; review its provenance: " + name)

            references = entry.get("notices")
            sources = entry.get("sources")

            if (not entry.get("component") or not entry.get("version")
                    or not isinstance(sources, list) or not sources
                    or not all(isinstance(url, str) and url.startswith("https://") for url in sources)
                    or not isinstance(references, list) or not references
                    or not all(isinstance(notice, str) and notice in notices for notice in references)):
                raise ValueError("Windows native library has incomplete provenance or notices: " + name)

            selected[name] = dict(entry, destination = destination)
            wanted.update(references)

        if not selected:
            raise ValueError("The compiler report contains no reviewed Windows native libraries")

        for name in sorted(wanted):
            entry = notices[name]
            archive.add(name, catalogue.texts[entry["sha256"]], entry["details"])

        summary = {
            "verified": True, "scope": "included_dll", "libraries": len(selected),
            "python": catalogue.metadata["python"],
            "catalogue_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        }
        archive.metadata["native_libraries"] = selected
        archive.metadata["windows_native_provenance"] = summary
        archive.metadata["windows_native_sources"] = {
            key: value for key, value in catalogue.metadata.items() if key != "libraries"
        }
        archive.metadata["windows_compilation_report_sha256"] = hashlib.sha256(report.read_bytes()).hexdigest()
        WindowsNativeCatalogue.verify_distribution(distribution, archive)

        return summary

    @staticmethod
    def verify_distribution(distribution: Path, archive: LicenseTextArchive) -> dict:
        summary = archive.metadata.get("windows_native_provenance", {})
        libraries = archive.metadata.get("native_libraries", {})

        if (summary.get("verified") is not True or summary.get("scope") != "included_dll"
                or type(summary.get("libraries")) is not int
                or summary["libraries"] <= 0 or summary["libraries"] != len(libraries)
                or not isinstance(summary.get("python"), str) or not summary["python"]
                or not re.fullmatch(r"[0-9a-f]{64}", str(summary.get("catalogue_sha256", "")))):
            raise ValueError("Verified Windows native provenance is required")

        actual = {}

        for path in distribution.rglob("*"):
            if path.suffix.casefold() != ".dll":
                continue

            name = path.relative_to(distribution).as_posix().casefold()

            if name in actual or path.is_symlink() or not path.is_file():
                raise ValueError("Invalid Windows native library in distribution: " + name)

            actual[name] = path

        expected = {}
        notices = {entry["name"] for entry in archive.entries}

        for name, entry in libraries.items():
            destination = WindowsNativeCatalogue.relative_path(entry["destination"]).casefold()
            references = entry.get("notices", [])

            if (destination in expected or not references
                    or not all(isinstance(notice, str) and notice in notices for notice in references)):
                raise ValueError("Incomplete or ambiguous shipped Windows native notices: " + name)

            expected[destination] = entry["original_sha256"]

        if set(actual) != set(expected):
            raise ValueError("Shipped Windows DLL inventory does not match the compiler report")

        for name, path in actual.items():
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected[name]:
                raise ValueError("Shipped Windows native library changed: " + name)

        return summary

    @staticmethod
    def relative_path(value: str) -> str:
        path = PurePosixPath(value)

        if (not value or path.is_absolute() or ".." in path.parts or "\\" in value
                or ":" in value or "\n" in value or "\r" in value or value == "."):
            raise ValueError("A safe relative Windows native library path is required")

        return path.as_posix()
