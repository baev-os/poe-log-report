"""Check distribution reproducibility without source files or Git during analysis."""

import hashlib
import json
import zoneinfo
import unittest

from importlib.resources import files

from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import patch

from poe_log_analyze.stages.parsing.LogAnalysisService import LogAnalysisService

from poe_log_analyze.runtime.JsonFiles import JsonFiles


class RuntimeTests(unittest.TestCase):
    """Isolate the bundled time zone database and code metadata."""

    def test_bundled_metadata_and_timezone_do_not_require_git(self):
        original = zoneinfo.TZPATH
        utc_bytes = files("tzdata").joinpath("zoneinfo", "UTC").read_bytes()

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            zone = root / "zoneinfo" / "UTC"
            zone.parent.mkdir()
            zone.write_bytes(utc_bytes)
            (zone.parent / "tzdata.zi").write_text("# version synthetic\n")
            code = {"git": {"sha": "a" * 40, "dirty": True}, "files_sha256": {"parser.py": "b" * 64}}
            JsonFiles.write_json(root / "build-info.json", {"code": code})
            source = root / "source.txt"
            source.write_bytes(b"\n")

            try:
                with patch("poe_log_analyze.runtime.RuntimeResources.RuntimeResources.resource_root", return_value = root), \
                        patch("poe_log_analyze.runtime.CodeProvenance.CodeProvenance.git_state", side_effect = AssertionError("Git недоступен")):
                    LogAnalysisService.analyze(source, root / "result", "UTC")

                manifest = json.loads((root / "result" / "manifest.json").read_text())

                self.assertEqual(manifest["code"], code)
                self.assertEqual(manifest["environment"]["timezone"]["database_version"], "# version synthetic")
                self.assertEqual(manifest["environment"]["timezone"]["zone_sha256"], hashlib.sha256(zone.read_bytes()).hexdigest())
            finally:
                zoneinfo.reset_tzpath(original)
                zoneinfo.ZoneInfo.clear_cache()
