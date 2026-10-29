"""Application version and validated source identity for release builds."""

import re
import subprocess
import tomllib

from dataclasses import dataclass
from pathlib import Path

from poe_log_analyze.runtime.CodeProvenance import CodeProvenance


@dataclass(frozen = True)
class BuildVersion:
    """Keep the application version, release tag, and source commit together."""

    version: str
    release_tag: str | None
    commit: str | None
    dirty: bool | None

    @staticmethod
    def read(root: Path, release_tag: str | None = None) -> "BuildVersion":
        with (root / "pyproject.toml").open("rb") as source:
            version = tomllib.load(source)["project"]["version"]

        if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:(?:a|b|rc)[0-9]+)?", version):
            raise ValueError('The application version must be an explicit release or prerelease version')

        git = CodeProvenance.git_state(root)
        result = BuildVersion(version, release_tag, git["sha"], git["dirty"])

        if release_tag is not None:
            if release_tag != "v" + version:
                raise ValueError('The release tag must match the application version: v' + version)

            if result.commit is None or result.dirty is not False:
                raise ValueError('A release build requires a clean Git worktree with a known commit')

            try:
                tagged = CodeProvenance._git(root, "rev-parse", "--verify", "refs/tags/" + release_tag + "^{commit}")
            except (OSError, subprocess.SubprocessError) as error:
                raise ValueError('The release tag must exist locally and identify the source commit') from error

            if tagged != result.commit:
                raise ValueError('The release tag does not identify the current source commit')

        return result

    def verify(self, root: Path) -> None:
        """Reject source changes made while a release was being compiled."""

        if self.release_tag is not None and BuildVersion.read(root, self.release_tag) != self:
            raise ValueError('The source identity changed during the release build')
