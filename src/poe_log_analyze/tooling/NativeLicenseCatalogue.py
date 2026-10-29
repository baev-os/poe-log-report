"""Additional shared-library notices from the actual Linux build report."""

import hashlib
import sys
import xml.etree.ElementTree as ET

from pathlib import Path

from poe_log_analyze.tooling.LicenseTextArchive import LicenseTextArchive


class NativeLicenseCatalogue:
    """Never apply old licenses to unknown native library versions."""

    @staticmethod
    def append(root: Path, report: Path, archive: LicenseTextArchive) -> None:
        native = LicenseTextArchive.read(root / "licenses/Native.txt", root / "licenses/Native.json")
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

            source = Path(node.attrib["source_path"].replace("${sys.real_prefix}", sys.base_prefix)
                          .replace("${sys.prefix}", sys.prefix))
            digest = hashlib.sha256(source.read_bytes()).hexdigest()

            if digest != libraries[name]["original_sha256"]:
                raise ValueError('Native library changed; update the license catalogue: ' + name)

            selected[name] = libraries[name]

        wanted = {entry["notice"] for entry in selected.values()}

        for entry in native.entries:
            if entry["name"] in wanted or entry["name"].startswith("native/common-licenses/"):
                archive.add(entry["name"], native.texts[entry["sha256"]], entry["details"])

        archive.metadata["native_libraries"] = selected
