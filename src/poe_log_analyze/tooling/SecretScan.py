"""Scan available Git history and a safe source snapshot without exposing findings."""

import argparse
import json
import os
import shutil
import subprocess

from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory


class SecretScan:
    """Use pinned Gitleaks rules and retain aggregate results only."""

    VERSION = "8.24.3"
    EXCLUDED_ROOTS = {".git", ".agents", ".aws", ".codex", "build", ".venv", "venv"}

    @staticmethod
    def main() -> int:
        parser = argparse.ArgumentParser(description = "Scan all available Git refs and nonignored source files")
        parser.add_argument("--output", type = Path, default = Path("build/audit-final"))
        args = parser.parse_args()

        return SecretScan.run(Path(__file__).resolve().parents[3], args.output)

    @staticmethod
    def run(root: Path, output: Path) -> int:
        root = root.resolve()
        output = output if output.is_absolute() else root / output

        if output.is_symlink() or not output.resolve().is_relative_to(root / "build"):
            raise ValueError("Secret scan results must be inside the project build/ directory")

        output = output.resolve()
        scanner = root / "build/tools/gitleaks"

        if scanner.is_symlink() or not scanner.is_file() or not scanner.resolve().is_relative_to(root / "build"):
            raise ValueError("Install the verified Gitleaks binary at build/tools/gitleaks")

        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith("GIT_") and key not in {"GITLEAKS_CONFIG", "GITLEAKS_CONFIG_TOML"}}
        version = subprocess.run([str(scanner), "version"], env = environment, cwd = root,
                                 stdout = subprocess.PIPE, stderr = subprocess.DEVNULL, text = True, check = True)

        if version.stdout.strip() != SecretScan.VERSION:
            raise ValueError("Secret scanning requires Gitleaks " + SecretScan.VERSION)

        output.mkdir(parents = True, exist_ok = False)
        summary = {
            "schema_version": "1", "scanner": "gitleaks", "scanner_version": SecretScan.VERSION,
            "commit": SecretScan._git(root, environment, "rev-parse", "HEAD").decode().strip(),
            "available_refs": len(SecretScan._git(root, environment, "for-each-ref", "--format=%(refname)").splitlines()),
            "reachable_commits": int(SecretScan._git(root, environment, "rev-list", "--all", "--count")),
            "rules": "built-in defaults; no repository suppressions, inline allows, or baseline",
            "snapshot_excluded_roots": sorted(SecretScan.EXCLUDED_ROOTS),
            "snapshot_excludes_symlinks": True,
            "results": {},
        }
        failed = False

        with TemporaryDirectory(prefix = "scan-", dir = output) as temporary:
            working = Path(temporary)
            snapshot = working / "working-tree"
            snapshot.mkdir()
            summary["snapshot_files"] = SecretScan.snapshot(root, snapshot, environment)
            config = working / "gitleaks.toml"
            config.write_text("[extend]\nuseDefault = true\n", encoding = "utf-8")
            ignore = working / "gitleaksignore"
            ignore.write_text("", encoding = "utf-8")

            for name, command in (("history", ["git", "--log-opts=--all --full-history", str(root)]),
                                  ("working_tree", ["dir", str(snapshot)])):
                report = working / (name + ".json")
                arguments = [str(scanner), *command, "--config=" + str(config),
                             "--gitleaks-ignore-path=" + str(ignore), "--ignore-gitleaks-allow", "--redact=100",
                             "--max-decode-depth=2", "--no-banner", "--no-color", "--report-format=json",
                             "--report-path=" + str(report)]
                result = subprocess.run(arguments, cwd = root, env = environment,
                                        stdout = subprocess.DEVNULL, stderr = subprocess.DEVNULL)
                findings = None

                try:
                    data = json.loads(report.read_text(encoding = "utf-8"))

                    if isinstance(data, list) and all(isinstance(item, dict) for item in data):
                        findings = len(data)
                except (OSError, UnicodeError, ValueError):
                    pass

                summary["results"][name] = {"exit_code": result.returncode, "findings": findings}
                failed = failed or result.returncode != 0 or findings != 0

        summary["passed"] = not failed
        (output / "results.json").write_text(json.dumps(summary, indent = 2) + "\n", encoding = "utf-8")
        print(json.dumps(summary, indent = 2))

        return 1 if failed else 0

    @staticmethod
    def snapshot(root: Path, destination: Path, environment: dict[str, str]) -> int:
        """Copy regular nonignored files without following file or directory symlinks."""

        if destination.is_symlink() or any(destination.iterdir()):
            raise ValueError("The secret scan snapshot must be a new empty directory")

        files = SecretScan._git(root, environment, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
        count = 0

        for encoded in sorted(set(files.split(b"\0"))):
            if not encoded:
                continue

            relative = PurePosixPath(os.fsdecode(encoded))

            if (relative.is_absolute() or not relative.parts
                    or any(part in {".", ".."} or "\\" in part or ":" in part for part in relative.parts)):
                raise ValueError("Invalid source path in Git file listing")

            if relative.parts[0].lower() in SecretScan.EXCLUDED_ROOTS:
                continue

            source = root.joinpath(*relative.parts)

            if any(parent.is_symlink() for parent in (source, *source.parents) if parent != root and parent.is_relative_to(root)):
                continue

            if not source.resolve().is_relative_to(root) or not source.is_file():
                continue

            target = destination.joinpath(*relative.parts)

            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError("Invalid snapshot destination path")

            target.parent.mkdir(parents = True, exist_ok = True)
            shutil.copyfile(source, target, follow_symlinks = False)
            count += 1

        return count

    @staticmethod
    def _git(root: Path, environment: dict[str, str], *arguments: str) -> bytes:
        return subprocess.check_output(["git", "--no-optional-locks", "-C", str(root),
                                        "--git-dir", str(root / ".git"), "--work-tree", str(root), *arguments],
                                       env = environment, stderr = subprocess.DEVNULL)
