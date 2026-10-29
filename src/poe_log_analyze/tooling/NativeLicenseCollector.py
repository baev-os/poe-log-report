"""Collect native notices from the packages that own the compiled inputs."""

import base64
import hashlib
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

from importlib import metadata
from pathlib import Path

from poe_log_analyze.tooling.LicenseTextArchive import LicenseTextArchive


class NativeLicenseCollector:
    """Create a separate per-build catalogue without changing pinned notices."""

    DOCUMENTATION = Path("/usr/share/doc")
    COMMON_LICENSES = Path("/usr/share/common-licenses")

    @staticmethod
    def collect(report: Path, destination: Path) -> Path:
        if destination.suffix != ".json":
            raise ValueError('A native catalogue must have a .json manifest')

        text = destination.with_suffix(".txt")

        if destination.exists() or text.exists():
            raise FileExistsError('Native catalogue output already exists: ' + str(destination))

        archive = LicenseTextArchive(metadata = {
            "target": "Linux", "collector": "installed-package-notices",
            "compilation_report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(), "libraries": {}})
        libraries = archive.metadata["libraries"]

        for node in ET.parse(report).getroot().findall("included_dll"):
            if node.attrib.get("ignored") == "yes" or node.attrib["name"].startswith("libpython"):
                continue

            name = node.attrib["name"]
            source = NativeLicenseCollector.source_path(node.attrib["source_path"])
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            package = NativeLicenseCollector.debian_package(source)

            if package is not None:
                package_name, version = package
                copyright_path = NativeLicenseCollector.DOCUMENTATION / package_name.split(":")[0] / "copyright"
                notice = "native/debian/" + package_name + "/copyright"
                notices = NativeLicenseCollector.add_notice(archive, notice, copyright_path,
                                                            {"package": package_name, "version": version,
                                                             "source": str(copyright_path)})
                supplier = "dpkg"
            else:
                package_name, version, notices = NativeLicenseCollector.wheel_notices(source, archive)
                supplier = "python-wheel"

            entry = {"package": package_name, "version": version, "supplier": supplier,
                     "source": str(source), "notice": notices[0], "notices": notices,
                     "original_sha256": digest}

            if name in libraries and libraries[name] != entry:
                raise ValueError('Ambiguous native library sources: ' + name)

            libraries[name] = entry

        destination.parent.mkdir(parents = True, exist_ok = True)
        archive.write(text, destination)
        LicenseTextArchive.read(text, destination)

        return destination

    @staticmethod
    def source_path(value: str) -> Path:
        path = Path(value.replace("${sys.real_prefix}", sys.base_prefix).replace("${sys.prefix}", sys.prefix))

        if not path.is_absolute() or not path.is_file():
            raise ValueError('The compiler report has no readable original native library: ' + value)

        return path

    @staticmethod
    def debian_package(source: Path) -> tuple[str, str] | None:
        candidates = list(dict.fromkeys((source, source.resolve())))

        for path in tuple(candidates):
            value = str(path)

            if value.startswith("/usr/lib/"):
                candidates.append(Path(value.removeprefix("/usr")))
            elif value.startswith("/lib/"):
                candidates.append(Path("/usr" + value))

        owners = set()

        for path in dict.fromkeys(candidates):
            try:
                result = subprocess.check_output(["dpkg-query", "--search", str(path)],
                                                 text = True, stderr = subprocess.DEVNULL, timeout = 10)
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue

            for line in result.splitlines():
                owner, separator, owned = line.rpartition(": ")

                if separator and owned == str(path):
                    owners.add(owner)

        if not owners:
            return None

        if len(owners) != 1:
            raise ValueError('Multiple Debian packages own native library: ' + str(source))

        owner = owners.pop()
        result = subprocess.check_output(["dpkg-query", "--show",
                                          "--showformat=${binary:Package}\t${Version}\t${db:Status-Status}", owner],
                                         text = True, stderr = subprocess.DEVNULL, timeout = 10)
        package, version, status = result.strip().split("\t")

        if status != "installed" or not version or not re.fullmatch(r"[a-z0-9][a-z0-9+.-]*(?::[a-z0-9-]+)?", package):
            raise ValueError('The owning Debian package is not installed: ' + owner)

        return package, version

    @staticmethod
    def add_notice(archive: LicenseTextArchive, name: str, source: Path, details: dict) -> list[str]:
        content = source.read_bytes()
        existing = next((entry for entry in archive.entries if entry["name"] == name), None)

        if existing is None:
            archive.add(name, content, details)
        elif existing["sha256"] != hashlib.sha256(content).hexdigest():
            raise ValueError('A native notice changed while collecting licenses: ' + str(source))

        names = [name]

        for reference in sorted(set(re.findall(rb"/usr/share/common-licenses/([A-Za-z0-9.+_-]+)", content))):
            common = reference.decode("ascii").rstrip(".")
            common_name = "native/common-licenses/" + common

            if common_name != name and not any(entry["name"] == common_name for entry in archive.entries):
                names.extend(NativeLicenseCollector.add_notice(
                    archive, common_name, NativeLicenseCollector.COMMON_LICENSES / common,
                    {"source": "/usr/share/common-licenses/" + common}))
            elif common_name not in names:
                names.append(common_name)

        return sorted(set(names))

    @staticmethod
    def wheel_notices(source: Path, archive: LicenseTextArchive) -> tuple[str, str, list[str]]:
        owners = []

        for distribution in metadata.distributions():
            for relative in distribution.files or ():
                if Path(distribution.locate_file(relative)).resolve() == source.resolve():
                    owners.append((distribution, relative))

        if len(owners) != 1:
            raise ValueError('No unambiguous installed package owns native library: ' + str(source))

        distribution, relative = owners[0]
        record = relative.hash
        digest = base64.urlsafe_b64encode(hashlib.sha256(source.read_bytes()).digest()).decode().rstrip("=")

        if record is None or record.mode != "sha256" or record.value != digest:
            raise ValueError('Native library does not match its installed wheel RECORD: ' + str(source))

        name = distribution.metadata["Name"]
        version = distribution.version

        if not name or not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            raise ValueError('Invalid installed wheel package name')

        notices = []

        for relative in distribution.files or ():
            path = Path(relative)

            if not re.fullmatch(r"(?:licen[sc]e|copying|copyright|notice)(?:[-_.].*)?", path.name, re.I):
                continue

            if path.is_absolute() or ".." in path.parts:
                raise ValueError('Invalid installed wheel notice path: ' + str(path))

            original = Path(distribution.locate_file(relative))
            notice = "native/wheel/" + name + "/" + path.as_posix()
            notices.extend(NativeLicenseCollector.add_notice(archive, notice, original,
                                                             {"package": name, "version": version,
                                                              "source": path.as_posix()}))

        if not notices:
            raise ValueError('The installed wheel has no original notices: ' + name)

        return name, version, sorted(set(notices))
