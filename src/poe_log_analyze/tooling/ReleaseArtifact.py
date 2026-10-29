"""Paths belonging to one portable release archive."""

from dataclasses import dataclass

from pathlib import Path


@dataclass(frozen = True, slots = True)
class ReleaseArtifact:
    """The archive and its independently readable integrity records."""

    archive: Path
    checksum: Path
    manifest: Path
