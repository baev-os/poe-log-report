"""Paths to local licenses and instructions for obtaining library source code."""

from pathlib import Path

from poe_log_analyze.runtime.RuntimeResources import RuntimeResources


class LicenseQuery:
    """Expose the directory to the GUI without reading licenses or modifying files."""

    @staticmethod
    def directory() -> Path:
        return RuntimeResources.resource_root() / "licenses"
