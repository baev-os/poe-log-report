"""Run the source check suite from any working directory."""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from poe_log_analyze.tooling.CheckSuite import CheckSuite

if __name__ == "__main__":
    raise SystemExit(CheckSuite.main())
