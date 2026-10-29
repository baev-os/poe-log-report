import hashlib
import os
import subprocess
import zoneinfo

from pathlib import Path

class CodeProvenance:
    """Code version, module hashes, and time zone database provenance."""

    @staticmethod
    def git_state(root: Path) -> dict:
        """Read only this project's Git state without changing the index or local refs."""

        try:
            return {"sha": CodeProvenance._git(root, "rev-parse", "HEAD"),
                    "dirty": bool(CodeProvenance._git(root, "status", "--porcelain", "--untracked-files=all"))}
        except (OSError, subprocess.SubprocessError):
            return {"sha": None, "dirty": None}

    @staticmethod
    def timezone_metadata(name: str) -> dict:
        """Record the actual system time zone file in use."""

        for root in zoneinfo.TZPATH:
            zone_file = Path(root) / name

            if zone_file.is_file():
                version_file = Path(root) / "tzdata.zi"
                version = None

                if version_file.is_file():
                    with version_file.open(encoding = "utf-8") as source:
                        version = source.readline().strip()

                return {"name": name, "database_version": version,
                        "zone_sha256": hashlib.sha256(zone_file.read_bytes()).hexdigest()}

        return {"name": name, "database_version": None, "zone_sha256": None}

    @staticmethod
    def source_hashes(package: Path | None = None) -> dict[str, str]:
        """Include all package Python modules, including nested directories."""

        package = package or Path(__file__).resolve().parents[1]
        return {p.relative_to(package).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(package.rglob("*.py")) if "resources" not in p.relative_to(package).parts}

    @staticmethod
    def _git(root: Path, *args: str) -> str:
        root = root.resolve()
        # An explicit .git prevents upward discovery and supports worktree gitfiles.
        # Inherited Git variables must not substitute another repository or index.
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}

        return subprocess.check_output(
            ["git", "--no-optional-locks", "-C", str(root),
             "--git-dir", str(root / ".git"), "--work-tree", str(root), *args],
            env = environment, stderr = subprocess.DEVNULL, text = True, timeout = 5,
        ).strip()
