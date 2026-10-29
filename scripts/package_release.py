"""Package and optionally verify one standalone release archive."""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from poe_log_analyze.tooling.ReleasePackager import ReleasePackager

if __name__ == "__main__":
    raise SystemExit(ReleasePackager.main())
