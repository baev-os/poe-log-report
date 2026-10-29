"""Launch DesktopBuilder from the source project."""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from poe_log_analyze.tooling.DesktopBuilder import DesktopBuilder

if __name__ == "__main__":
    raise SystemExit(DesktopBuilder.main())
