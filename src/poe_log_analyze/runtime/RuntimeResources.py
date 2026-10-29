import json
import zoneinfo

from pathlib import Path

class RuntimeResources:
    """Development and standalone resources independent of the working directory."""

    @staticmethod
    def resource_root() -> Path:
        """Select bundled resources, otherwise the source project root."""

        packaged = Path(__file__).resolve().parents[1] / "resources"
        return packaged if packaged.is_dir() else Path(__file__).resolve().parents[3]

    @staticmethod
    def build_metadata() -> dict | None:
        """Distribution metadata replaces Git and source access in the compiled application."""

        path = RuntimeResources.resource_root() / "build-info.json"
        return json.loads(path.read_text(encoding = "utf-8")) if path.is_file() else None

    @staticmethod
    def configure_timezone() -> None:
        """Always use the bundled time zone database in a distribution."""

        path = RuntimeResources.resource_root() / "zoneinfo"

        if path.is_dir():
            zoneinfo.reset_tzpath([str(path)])
        elif not zoneinfo.TZPATH:
            import tzdata
            zoneinfo.reset_tzpath([str(Path(tzdata.__file__).parent / "zoneinfo")])
