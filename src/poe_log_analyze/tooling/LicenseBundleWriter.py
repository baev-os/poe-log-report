"""Verifiable notices for the actual standalone distribution."""

import hashlib
import re
import shutil

from importlib import metadata
from pathlib import Path

from poe_log_analyze.runtime.JsonFiles import JsonFiles

from poe_log_analyze.tooling.LicenseTextArchive import LicenseTextArchive
from poe_log_analyze.tooling.NativeLicenseCatalogue import NativeLicenseCatalogue
from poe_log_analyze.tooling.WindowsNativeCatalogue import WindowsNativeCatalogue


class LicenseBundleWriter:
    """Preserve original texts and reject unknown dependencies."""

    BUILD_ONLY = {"patchelf"}

    @staticmethod
    def stage(root: Path, destination: Path, dependencies: tuple[str, ...],
              python_license: Path, *, system: str, native_report: Path | None = None,
              native_catalogue: Path | None = None, distribution: Path | None = None) -> dict:

        archive = LicenseTextArchive(metadata = {"gui": "tkinter", "target": system})
        versions = {name: metadata.version(name) for name in dependencies}
        destination.mkdir(parents = True, exist_ok = False)

        for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
            LicenseBundleWriter.copy(root / name, destination / name)

        for name in ("README.md", "GAME_DATA.md"):
            LicenseBundleWriter.copy(root / "licenses" / name, destination / name)

        for name, path in (("Bootstrap/LICENSE.txt", root / "site/static/vendor/bootstrap-LICENSE.txt"),
                           ("Python/LICENSE.txt", python_license),
                           ("DejaVu/LICENSE.txt", root / "reports/fonts/LICENSE.txt"),
                           ("Exile-UI/LICENSE.md", root / "licenses/Exile-UI.txt")):
            archive.add(name, path.read_bytes())

        for name in dependencies:
            if name in LicenseBundleWriter.BUILD_ONLY:
                continue

            installed = metadata.distribution(name)
            count = 0

            for relative in installed.files or []:
                path = Path(relative)

                if not re.fullmatch(r"(?:licen[sc]e|copying|copyright|notice)(?:[-_.].*)?", path.name, re.I):
                    continue

                if path.is_absolute() or ".." in path.parts:
                    raise ValueError(f"Invalid package license path for {name}")

                source = Path(installed.locate_file(relative))

                if source.is_file():
                    archive.add(f"dependencies/{name}/{path.as_posix()}", source.read_bytes(),
                                {"package": name, "version": versions[name]})
                    count += 1

            if count == 0:
                raise ValueError(f"Package {name} contains no license texts")

        archive.metadata["dependencies"] = {name: version for name, version in versions.items()
                                            if name not in LicenseBundleWriter.BUILD_ONLY}

        if system == "Linux" and native_report is not None:
            NativeLicenseCatalogue.append(root, native_report, archive, native_catalogue)
        elif system == "Windows":
            LicenseBundleWriter.copy(root / "licenses/WINDOWS_RUNTIME.md", destination / "WINDOWS_RUNTIME.md")
            LicenseBundleWriter.add_windows_toolkit(archive, python_license.parent, root)

            if native_report is None or distribution is None:
                raise ValueError("Windows notices require the compiler report and compiled distribution")

            WindowsNativeCatalogue.append(root, native_report, archive, python_license.parent, distribution)

        archive.write(destination / "THIRD_PARTY_LICENSES.txt", destination / "sources.json")
        result = {
            "version": "4", "gui": "tkinter", "dependencies": versions, "target": system,
            "notices": len(archive.entries), "unique_texts": len(archive.texts),
            "files_sha256": {
                path.relative_to(destination).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(destination.rglob("*")) if path.is_file()
            },
        }

        if system == "Windows":
            result["windows_native_provenance"] = archive.metadata["windows_native_provenance"]

        JsonFiles.write_json(destination / "manifest.json", result)

        return result

    @staticmethod
    def add_windows_toolkit(archive: LicenseTextArchive, python_root: Path, root: Path) -> None:
        """Use the installed original or a validated snapshot matching the Tcl/Tk version."""
        for component in ("tcl", "tk"):
            candidates = sorted((python_root / "tcl").glob(component + "[89]*/license.terms"))

            if len(candidates) > 1:
                raise ValueError(f"No unambiguous original license found for {component} in the Python installation")

            if candidates:
                path = candidates[0]
                archive.add(f"toolkit/{component}/license.terms", path.read_bytes(),
                            {"source": "CPython Tcl/Tk", "directory": path.parent.name})
                continue

            text, manifest = root / "licenses/TclTk.txt", root / "licenses/TclTk.json"

            if not text.is_file() or not manifest.is_file():
                raise ValueError(f"No validated original license found for {component}")

            catalogue = LicenseTextArchive.read(text, manifest)
            version = catalogue.metadata["versions"][component]
            script = "init.tcl" if component == "tcl" else "tk.tcl"
            libraries = sorted((python_root / "tcl").glob(component + "[89]*/" + script))
            pattern = r"(?m)^package\s+require\s+-exact\s+" + component.title() + r"\s+([0-9.]+)\s*$"

            if len(libraries) != 1 or re.findall(pattern, libraries[0].read_text(encoding = "utf-8")) != [version]:
                raise ValueError(f"No validated license for the installed version of {component}")

            name = f"toolkit/{component}/license.terms"
            entry = next(item for item in catalogue.entries if item["name"] == name)
            details = dict(entry["details"], version = version, directory = libraries[0].parent.name)
            archive.add(name, catalogue.texts[entry["sha256"]], details)

    @staticmethod
    def copy(source: Path, destination: Path) -> None:
        content = source.read_bytes()

        if not content.strip() or b"\x00" in content:
            raise ValueError(f"Missing license text: {source.name}")

        destination.parent.mkdir(parents = True, exist_ok = True)
        destination.write_bytes(content)

    @staticmethod
    def finish_distribution(root: Path, distribution: Path) -> None:
        """Keep notices visible beside the launcher; exclude the previous GUI from the distribution."""

        for path in distribution.rglob("*"):
            if path.name.lower().startswith(("libqt", "qt6", "pyside", "shiboken")):
                raise ValueError('Excluded GUI library included in the distribution: ' + path.name)

        for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
            shutil.copyfile(root / name, distribution / name)
