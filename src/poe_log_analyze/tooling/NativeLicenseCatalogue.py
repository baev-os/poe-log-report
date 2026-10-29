"""Additional shared-library notices from the actual Linux build report."""

import hashlib
import xml.etree.ElementTree as ET

from pathlib import Path

from poe_log_analyze.tooling.LicenseTextArchive import LicenseTextArchive
from poe_log_analyze.tooling.NativeLicenseCollector import NativeLicenseCollector


class NativeLicenseCatalogue:
    """Never apply old licenses to unknown native library versions."""

    @staticmethod
    def append(root: Path, report: Path, archive: LicenseTextArchive, catalogue: Path | None = None) -> None:
        manifest = root / "licenses/Native.json" if catalogue is None else catalogue

        if manifest.suffix != ".json":
            raise ValueError('A native catalogue must have a .json manifest')

        native = LicenseTextArchive.read(manifest.with_suffix(".txt"), manifest)
        libraries = native.metadata["libraries"]
        selected = {}

        for node in ET.parse(report).getroot().findall("included_dll"):
            if node.attrib.get("ignored") == "yes":
                continue

            name = node.attrib["name"]

            if name.startswith("libpython"):
                continue

            if name not in libraries:
                raise ValueError('No validated notices for native library: ' + name)

            source = NativeLicenseCollector.source_path(node.attrib["source_path"])
            digest = hashlib.sha256(source.read_bytes()).hexdigest()

            if digest != libraries[name]["original_sha256"]:
                raise ValueError('Native library changed; update the license catalogue: ' + name)

            selected[name] = libraries[name]

        wanted = set()

        for entry in selected.values():
            notices = entry.get("notices", [entry["notice"]])

            if not isinstance(notices, list) or not notices or not all(isinstance(name, str) for name in notices):
                raise ValueError('Invalid native library notice references')

            wanted.update(notices)

        if not wanted.issubset({entry["name"] for entry in native.entries}):
            raise ValueError('A native library notice is missing from the catalogue')

        for entry in native.entries:
            if entry["name"] in wanted or entry["name"].startswith("native/common-licenses/"):
                archive.add(entry["name"], native.texts[entry["sha256"]], entry["details"])

        archive.metadata["native_libraries"] = selected
