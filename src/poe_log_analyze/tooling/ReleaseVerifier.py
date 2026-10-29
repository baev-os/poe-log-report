"""Verify the exact release archive after extraction to an unrelated path."""

import argparse
import json
import os
import stat
import subprocess
import tarfile
import zipfile

from pathlib import Path, PurePosixPath

from poe_log_analyze.runtime.JsonFiles import JsonFiles
from poe_log_analyze.runtime.NativePlatform import NativePlatform
from poe_log_analyze.runtime.ProcessEnvironment import ProcessEnvironment
from poe_log_analyze.runtime.Workspace import Workspace

from poe_log_analyze.tooling.ReleasePackager import ReleasePackager


class ReleaseVerifier:
    """Check archive hashes, complete contents, and both localized GUI workflows."""

    @staticmethod
    def main() -> int:
        parser = argparse.ArgumentParser(description = "Verify a packaged application on its target operating system")
        parser.add_argument("--archive", type = Path, required = True)
        parser.add_argument("--manifest", type = Path, required = True)
        parser.add_argument("--output", type = Path, required = True)
        args = parser.parse_args()
        print(ReleaseVerifier.verify(args.archive, args.manifest, args.output))

        return 0

    @staticmethod
    def verify(archive: Path, manifest: Path, output: Path) -> Path:
        archive = Workspace.local_output(archive)
        manifest = Workspace.local_output(manifest)
        output = Workspace.local_output(output)
        metadata = json.loads(manifest.read_text(encoding = "utf-8"))

        if (metadata.get("release_manifest_version") != "1" or metadata.get("archive") != archive.name
                or ReleasePackager.sha256(archive) != metadata.get("archive_sha256")):
            raise ValueError("Release archive name or SHA256 does not match its manifest")

        if metadata.get("target") != NativePlatform.current().system:
            raise ValueError("Run release verification on the archive's target operating system")

        root = metadata["root"]
        ReleaseVerifier.safe_name(root, root)
        extraction = output / "Relocated application Проверка с пробелами"
        extraction.mkdir(parents = True, exist_ok = False)
        ReleaseVerifier.extract(archive, extraction, root)
        distribution = extraction / root
        build = ReleasePackager.read_identity(distribution, metadata["tag"], metadata["commit"])
        paths = ReleasePackager.validate_paths(distribution, metadata["target"])
        actual_files = {path.relative_to(distribution).as_posix(): ReleasePackager.sha256(path)
                        for path in paths if path.is_file() and not path.is_symlink()}
        actual_links = {path.relative_to(distribution).as_posix(): os.readlink(path)
                        for path in paths if path.is_symlink()}

        if actual_files != metadata["files_sha256"] or actual_links != metadata["symlinks"]:
            raise ValueError("Extracted application files or symlinks do not match the release manifest")

        provenance = ReleasePackager.windows_provenance(distribution, build)

        if ("windows_native_provenance" in metadata) != (provenance is not None):
            raise ValueError("Windows native provenance is missing from the build or release manifest")

        if provenance is not None:
            recorded = ReleasePackager.validate_windows_provenance(metadata["windows_native_provenance"])

            if recorded != provenance:
                raise ValueError("Windows native provenance differs between the build and release manifest")

        windows = metadata["target"] == "Windows"
        launcher = distribution / ("poe-log-analyze.cmd" if windows else "poe-log-analyze")

        if not windows and not os.access(launcher, os.X_OK):
            raise ValueError("Linux launcher lost its executable permission")

        cwd = output / "Unrelated working directory"
        cwd.mkdir()
        environment = ProcessEnvironment.within(output)

        for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
            environment.pop(name, None)

        if windows:
            windows_directory = environment.get("SYSTEMROOT") or environment.get("SystemRoot")

            if not windows_directory:
                raise ValueError("Windows verification requires the system Windows directory")

            windows_root = Path(windows_directory)
            environment["PATH"] = str(windows_root / "System32") + os.pathsep + str(windows_root)

        results = {}

        for language in ("en", "ru"):
            result_directory = distribution / "build" / ("self-test-" + language)
            command = [str(launcher), "--self-test", str(result_directory), "--report-language", language]

            if windows:
                command = [str(windows_root / "System32/cmd.exe"), "/d", "/s", "/c", "call", *command]

            with (output / ("self-test-" + language + ".log")).open("w", encoding = "utf-8") as stream:
                subprocess.run(command, cwd = cwd, env = environment, stdout = stream,
                               stderr = subprocess.STDOUT, check = True, timeout = 180)

            summary = json.loads((result_directory / "self-test.json").read_text(encoding = "utf-8"))

            if (summary.get("passed") is not True or summary.get("report_language") != language
                    or any(summary.get(name) is not True for name in
                           ("cancellation_preserved_report", "replacement_removed_pdf", "temporary_files_removed"))):
                raise ValueError("The standalone self-test did not confirm the complete " + language + " workflow")

            results[language] = {"passed": True}

        report = output / "verification.json"
        verification = {
            "passed": True, "archive": archive.name, "archive_sha256": metadata["archive_sha256"],
            "tag": metadata["tag"], "commit": metadata["commit"], "target": metadata["target"],
            "relocated": True, "languages": results,
        }

        if provenance is not None:
            verification["windows_native_provenance"] = provenance

        JsonFiles.write_json(report, verification)

        return report

    @staticmethod
    def extract(archive: Path, destination: Path, root: str) -> None:
        names = set()

        if archive.suffix == ".zip":
            with zipfile.ZipFile(archive) as bundle:
                for entry in bundle.infolist():
                    ReleaseVerifier.safe_name(entry.filename.rstrip("/"), root)

                    if entry.filename in names or stat.S_ISLNK(entry.external_attr >> 16):
                        raise ValueError("Duplicate archive member or unsupported ZIP symlink")

                    names.add(entry.filename)

                bundle.extractall(destination)
        else:
            with tarfile.open(archive, "r:gz") as bundle:
                for entry in bundle.getmembers():
                    ReleaseVerifier.safe_name(entry.name, root)

                    if entry.name in names or not (entry.isfile() or entry.isdir() or entry.issym() or entry.islnk()):
                        raise ValueError("Duplicate or unsupported tar archive member")

                    if entry.issym():
                        link = PurePosixPath(entry.linkname)

                        if link.is_absolute() or "\\" in entry.linkname or ":" in entry.linkname:
                            raise ValueError("Unsafe archive symlink")

                    if entry.islnk():
                        ReleaseVerifier.safe_name(entry.linkname, root)

                    names.add(entry.name)

                bundle.extractall(destination, filter = "data")

    @staticmethod
    def safe_name(name: str, root: str) -> None:
        path = PurePosixPath(name)

        if (not name or path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name
                or "\n" in name or "\r" in name or not path.parts or path.parts[0] != root):
            raise ValueError("Unsafe release archive member path")
