"""Create release archives from a clean, identified standalone distribution."""

import argparse
import hashlib
import json
import os
import re
import stat
import tarfile
import zipfile

from pathlib import Path

from poe_log_analyze.runtime.JsonFiles import JsonFiles
from poe_log_analyze.runtime.Workspace import Workspace

from poe_log_analyze.tooling.BuildVersion import BuildVersion
from poe_log_analyze.tooling.ReleaseArtifact import ReleaseArtifact


class ReleasePackager:
    """Keep application resources intact while excluding build and user output."""

    METADATA = "app/poe_log_analyze/resources/build-info.json"
    FORBIDDEN = {".git", ".venv", "__pycache__", ".env", "build", "report"}

    @staticmethod
    def main() -> int:
        parser = argparse.ArgumentParser(description = "Package a tagged Windows or Linux standalone build")
        parser.add_argument("--distribution", type = Path, required = True)
        parser.add_argument("--output", type = Path, required = True)
        parser.add_argument("--tag", required = True)
        parser.add_argument("--commit", required = True)
        parser.add_argument("--verify", action = "store_true", help = "Run the archived application in English and Russian")
        args = parser.parse_args()

        artifact = ReleasePackager.package(args.distribution, args.output, args.tag, args.commit)
        result = {"archive": str(artifact.archive), "checksum": str(artifact.checksum), "manifest": str(artifact.manifest)}

        if args.verify:
            from poe_log_analyze.tooling.ReleaseVerifier import ReleaseVerifier

            result["verification"] = str(ReleaseVerifier.verify(artifact.archive, artifact.manifest, args.output / "verification"))

        print(json.dumps(result))

        return 0

    @staticmethod
    def package(distribution: Path, output: Path, tag: str, commit: str) -> ReleaseArtifact:
        distribution = Workspace.local_output(distribution)
        output = Workspace.local_output(output)

        if output.is_relative_to(distribution):
            raise ValueError("Release output must be outside the application distribution")

        source_root = Workspace.project_root()
        source = BuildVersion.read(source_root, tag)

        if source.commit != commit:
            raise ValueError("The release commit must identify the current clean source checkout")

        build = ReleasePackager.read_identity(distribution, tag, commit)
        target = build["target"]
        launcher = "poe-log-analyze.cmd" if target == "Windows" else "poe-log-analyze"

        if {path.name for path in distribution.iterdir()} != {"app", "README.md", launcher}:
            raise ValueError("Distribution root must contain only app/, README.md, and its launcher")

        binary = "app/poe-log-analyze.exe" if target == "Windows" else "app/poe-log-analyze"

        for name in (launcher, binary, "README.md", "app/LICENSE", "app/THIRD_PARTY_NOTICES.md",
                     "app/poe_log_analyze/resources/licenses/manifest.json",
                     "app/poe_log_analyze/resources/licenses/THIRD_PARTY_LICENSES.txt"):
            if not (distribution / name).is_file():
                raise ValueError("Required distribution file is missing: " + name)

        paths = ReleasePackager.validate_paths(distribution, target)

        if target == "Linux" and any(not os.access(distribution / name, os.X_OK) for name in (launcher, binary)):
            raise ValueError("Linux launcher and native executable must have executable permissions")

        platform_name = "windows-x64" if target == "Windows" else "linux-x86_64"
        name = f"poe-log-report-{build['version']}-{platform_name}"
        suffix = ".zip" if target == "Windows" else ".tar.gz"
        output.mkdir(parents = True, exist_ok = True)
        archive = output / (name + suffix)
        manifest = output / (name + ".json")
        checksum = output / (name + ".sha256")

        if any(path.exists() or path.is_symlink() for path in (archive, manifest, checksum)):
            raise FileExistsError("Release assets already exist; use a fresh output directory")

        checksums = output / "SHA256SUMS"

        if checksums.is_symlink():
            raise ValueError("The checksum list must be a regular output file")

        if target == "Windows":
            with zipfile.ZipFile(archive, "x", compression = zipfile.ZIP_DEFLATED) as bundle:
                for path in paths:
                    bundle.write(path, name + "/" + path.relative_to(distribution).as_posix())
        else:
            with tarfile.open(archive, "x:gz", format = tarfile.PAX_FORMAT) as bundle:
                bundle.add(distribution, arcname = name, recursive = False)

                for path in paths:
                    bundle.add(path, arcname = name + "/" + path.relative_to(distribution).as_posix(), recursive = False)

        source.verify(source_root)
        digest = ReleasePackager.sha256(archive)
        line = f"{digest}  {archive.name}\n"
        checksum.write_text(line, encoding = "ascii", newline = "\n")
        with checksums.open("a", encoding = "ascii", newline = "\n") as stream:
            stream.write(line)

        JsonFiles.write_json(manifest, {
            "release_manifest_version": "1", "version": build["version"], "tag": tag,
            "commit": commit, "target": target, "architecture": "x86_64",
            "archive": archive.name, "archive_sha256": digest, "root": name,
            "files_sha256": {path.relative_to(distribution).as_posix(): ReleasePackager.sha256(path)
                             for path in paths if path.is_file() and not path.is_symlink()},
            "symlinks": {path.relative_to(distribution).as_posix(): os.readlink(path)
                         for path in paths if path.is_symlink()},
        })

        return ReleaseArtifact(archive, checksum, manifest)

    @staticmethod
    def read_identity(distribution: Path, tag: str, commit: str) -> dict:
        if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+(?:[A-Za-z0-9.-]+)?", tag):
            raise ValueError("A version tag beginning with v is required")

        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("The full lowercase Git commit SHA is required")

        metadata = distribution / ReleasePackager.METADATA

        if not metadata.resolve().is_relative_to(distribution):
            raise ValueError("Build metadata must remain inside the distribution")

        build = json.loads(metadata.read_text(encoding = "utf-8"))
        git = build.get("code", {}).get("git", {})

        if (build.get("version") != tag[1:] or build.get("release_tag") != tag
                or git.get("sha") != commit or git.get("dirty") is not False):
            raise ValueError("Build version, release tag, and clean Git commit must match the release")

        if (build.get("target") not in ("Linux", "Windows") or build.get("architecture") != "x86_64"
                or build.get("distribution_layout") != "app"):
            raise ValueError("A supported Windows/Linux x86_64 app distribution is required")

        return build

    @staticmethod
    def validate_paths(distribution: Path, target: str) -> list[Path]:
        paths = sorted(distribution.rglob("*"))

        for path in paths:
            relative = path.relative_to(distribution)

            if any(part in ReleasePackager.FORBIDDEN or part.startswith(".env.") for part in relative.parts):
                raise ValueError("Development or user output found in distribution: " + relative.as_posix())

            if any("\\" in part or ":" in part or "\n" in part or "\r" in part for part in relative.parts):
                raise ValueError("Unsafe archive path: " + relative.as_posix())

            if path.is_symlink():
                link = Path(os.readlink(path))

                if target == "Windows" or link.is_absolute() or not path.resolve().is_relative_to(distribution):
                    raise ValueError("Unsafe or unsupported distribution symlink: " + relative.as_posix())

                if not path.exists() or not path.resolve().is_file():
                    raise ValueError("Distribution symlinks must refer to existing internal files")
            elif not stat.S_ISREG(path.stat().st_mode) and not path.is_dir():
                raise ValueError("Only regular files, directories, and safe symlinks can be archived")

        return paths

    @staticmethod
    def sha256(path: Path) -> str:
        digest = hashlib.sha256()

        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)

        return digest.hexdigest()
