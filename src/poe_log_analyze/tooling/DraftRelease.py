"""Create a draft containing both verified portable builds without publishing it."""

import argparse
import json
import re
import subprocess

from pathlib import Path

from poe_log_analyze.runtime.JsonFiles import JsonFiles
from poe_log_analyze.runtime.Workspace import Workspace

from poe_log_analyze.tooling.ReleaseArtifact import ReleaseArtifact
from poe_log_analyze.tooling.ReleasePackager import ReleasePackager


class DraftRelease:
    """Validate the complete asset set before invoking draft-only GitHub commands."""

    @staticmethod
    def main() -> int:
        parser = argparse.ArgumentParser(description = "Create a draft release from two verified portable builds")
        parser.add_argument("--assets", type = Path, required = True)
        parser.add_argument("--tag", required = True)
        parser.add_argument("--commit", required = True)
        parser.add_argument("--repo", default = "baev-os/poe-log-report")
        args = parser.parse_args()
        print(DraftRelease.create(args.assets, args.tag, args.commit, args.repo))

        return 0

    @staticmethod
    def create(assets: Path, tag: str, commit: str, repo: str) -> str:
        assets = Workspace.local_output(assets)

        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            raise ValueError("The repository must be an explicit owner/name")

        artifacts = DraftRelease.validate_assets(assets, tag, commit)
        clean_linux = assets / "verification-clean-Linux.json"

        if clean_linux.exists() or clean_linux.is_symlink():
            DraftRelease.validate_verification(clean_linux, artifacts["Linux"], tag, commit, "Linux")
            clean = json.loads(clean_linux.read_text(encoding = "utf-8"))

            if clean.get("clean_runtime") is not True or clean.get("python_available") is not False:
                raise ValueError("Clean Linux verification must explicitly confirm a runtime without Python")

        remote = subprocess.run(["gh", "api", f"repos/{repo}/commits/{tag}", "--jq", ".sha"],
                                check = True, capture_output = True, text = True, timeout = 60)

        if remote.stdout.strip() != commit:
            raise ValueError("The remote release tag does not identify the verified source commit")

        existing = subprocess.run(["gh", "release", "view", tag, "--repo", repo, "--json", "isDraft,url"],
                                  check = False, capture_output = True, text = True, timeout = 60)

        if existing.returncode == 0:
            kind = "draft" if json.loads(existing.stdout).get("isDraft") is True else "published"
            raise FileExistsError("A " + kind + " release already exists for " + tag)

        if "release not found" not in existing.stderr.lower() and "http 404" not in existing.stderr.lower():
            raise RuntimeError("GitHub could not confirm whether this release already exists")

        checksums = assets / "SHA256SUMS"
        document = assets / "RELEASE_METADATA.json"
        notes = assets / "release-notes.md"

        if any(path.is_symlink() for path in (checksums, document, notes)):
            raise ValueError("Generated release records must be regular output files")

        lines = [artifact.checksum.read_text(encoding = "ascii") for artifact in artifacts.values()]
        checksums.write_text("".join(sorted(lines, key = lambda line: line.split("  ", 1)[1])),
                             encoding = "ascii", newline = "\n")
        pending = ["manual_clean_windows_10_11_acceptance", "game_material_redistribution_review",
                   "windows_native_dependency_provenance_review"]

        if not clean_linux.exists():
            pending.append("clean_linux_runtime_acceptance")

        JsonFiles.write_json(document, {
            "release_metadata_version": "1", "state": "draft", "repository": repo,
            "version": tag[1:], "tag": tag, "commit": commit,
            "targets": {target: {"archive": artifact.archive.name,
                                 "sha256": ReleasePackager.sha256(artifact.archive),
                                 "verification": f"verification-{target}.json"}
                        for target, artifact in artifacts.items()},
            "clean_linux_runtime_verified": clean_linux.exists(),
            "pending_publication_checks": pending,
        })
        notes.write_text(
            f"# PoE Log Report {tag}\n\n"
            "Portable Path of Exile 1 log analysis with English and Russian HTML/PDF reports.\n\n"
            f"Source: tag `{tag}`, commit `{commit}`.\n\n"
            "The Windows x64 ZIP and Linux x86_64 tar.gz were checked against their SHA256 manifests. "
            "Both archived applications passed the English and Russian GUI self-tests after extraction "
            "to a relocated directory containing spaces and Unicode.\n\n"
            + ("The Linux archive additionally passed the same checks in a clean runtime container.\n\n"
               if clean_linux.exists() else "Clean Linux runtime acceptance remains pending.\n\n")
            + "Manual acceptance on clean Windows 10/11 client systems and review of game-material "
            "redistribution remain pending. A Windows compiler-runner check does not establish "
            "client-system compatibility.\n\n"
            "Windows OpenSSL/zlib DLL source and notice mappings and Visual C runtime provenance "
            "remain maintainer review items before publication. Recorded notice hashes do not settle "
            "those mappings.\n\n"
            "Extract the entire archive into a writable folder. Start `poe-log-analyze.cmd` on Windows "
            "or `./poe-log-analyze` on Linux. Keep the `app/` directory and license notices together.\n\n"
            "This draft records release preparation. Publishing the release and changing repository "
            "visibility require separate actions.\n",
            encoding = "utf-8", newline = "\n")

        attachments = [path for artifact in artifacts.values()
                       for path in (artifact.archive, artifact.manifest, artifact.checksum)]
        attachments.extend(assets / f"verification-{target}.json" for target in artifacts)

        if clean_linux.exists():
            attachments.append(clean_linux)

        attachments.extend((checksums, document))
        command = ["gh", "release", "create", tag, "--repo", repo, "--draft", "--verify-tag",
                   "--target", commit, "--title", "PoE Log Report " + tag, "--notes-file", str(notes),
                   *(str(path) for path in attachments)]
        result = subprocess.run(command, check = True, capture_output = True, text = True, timeout = 600)

        return result.stdout.strip()

    @staticmethod
    def validate_assets(assets: Path, tag: str, commit: str) -> dict[str, ReleaseArtifact]:
        if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+(?:(?:a|b|rc)[0-9]+)?", tag):
            raise ValueError("An explicit application version tag is required")

        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("The full lowercase Git commit SHA is required")

        artifacts = {}

        for target, platform_name, suffix in (("Linux", "linux-x86_64", ".tar.gz"),
                                               ("Windows", "windows-x64", ".zip")):
            stem = f"poe-log-report-{tag[1:]}-{platform_name}"
            artifact = ReleaseArtifact(assets / (stem + suffix), assets / (stem + ".sha256"), assets / (stem + ".json"))

            for path in (artifact.archive, artifact.checksum, artifact.manifest):
                DraftRelease.regular_file(path)

            metadata = json.loads(artifact.manifest.read_text(encoding = "utf-8"))
            digest = ReleasePackager.sha256(artifact.archive)

            if (metadata.get("release_manifest_version") != "1" or metadata.get("version") != tag[1:]
                    or metadata.get("tag") != tag or metadata.get("commit") != commit
                    or metadata.get("target") != target or metadata.get("architecture") != "x86_64"
                    or metadata.get("root") != stem or metadata.get("archive") != artifact.archive.name
                    or metadata.get("archive_sha256") != digest):
                raise ValueError("Release manifest identity or archive digest does not match: " + target)

            if artifact.checksum.read_text(encoding = "ascii") != f"{digest}  {artifact.archive.name}\n":
                raise ValueError("Archive checksum sidecar does not match: " + target)

            DraftRelease.validate_verification(assets / f"verification-{target}.json", artifact, tag, commit, target)
            artifacts[target] = artifact

        return artifacts

    @staticmethod
    def validate_verification(path: Path, artifact: ReleaseArtifact, tag: str, commit: str, target: str) -> None:
        DraftRelease.regular_file(path)
        metadata = json.loads(path.read_text(encoding = "utf-8"))

        if (metadata.get("passed") is not True or metadata.get("relocated") is not True
                or metadata.get("tag") != tag or metadata.get("commit") != commit
                or metadata.get("target") != target or metadata.get("archive") != artifact.archive.name
                or metadata.get("archive_sha256") != ReleasePackager.sha256(artifact.archive)
                or any(metadata.get("languages", {}).get(language, {}).get("passed") is not True
                       for language in ("en", "ru"))):
            raise ValueError("Complete verification for the exact archive is required: " + target)

    @staticmethod
    def regular_file(path: Path) -> None:
        if path.is_symlink() or not path.is_file():
            raise ValueError("A regular release asset is required: " + path.name)
