"""Synthetic version-3 settings, notices, and dialogue checks."""

import unittest

from io import BytesIO

from zoneinfo import ZoneInfo

from poe_log_analyze.stages.parsing.LogParser import LogParser
from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue


CASES = (
    ("job.priority_count", "[JOB] HIGH: 6", {"priority": "HIGH", "count": "6"}),
    ("job.start", "[JOB] Start", {}),
    ("job.exception_callback", "[JOB] Irrecoverable Exception Callback: SET", {}),
    ("job.priority_boost", "[JOB] Enable medium thread priority boost = false", {"enabled": "false"}),
    ("storage.bucket_count", "[STORAGE] Mapping bucket count: 8", {"count": "8"}),
    ("storage.init_cache", "[STORAGE] Init bundle cache", {}),
    ("runtime.bucket_count", "[MAT] Dynamic Bucket count: 8", {"subsystem": "MAT", "count": "8"}),
    ("bundle.index", "[BUNDLE] Bundle index: Bundles2/example.bin", {"path": "Bundles2/example.bin"}),
    ("bundle.contents", "[BUNDLE] Found 12 slots (1.25 MB)", {"count": "12", "kind": "slots", "size": "1.25", "unit": "MB"}),
    ("render.start_device", "[RENDER] Starting device", {"backend": None}),
    ("render.driver_version", "[RENDER] Driver Version: 1.2.3.4", {"version": "1.2.3.4"}),
    ("render.gpu_scheduling", "[RENDER] Hardware-accelerated GPU scheduling: Enabled", {"state": "Enabled"}),
    ("shader.load_cache", "[SHADER] Load shader cache: ShaderCacheVulkan", {"cache": "ShaderCacheVulkan"}),
    ("shader.pso_cache", "[SHADER] PSO Cache: Disabled", {"state": "Disabled"}),
    ("mat.table", "[MAT] Mat table size: 12.  3 graph combinations have inlined parameters.  4 parameters are inlined.", {"size": "12", "combinations": "3", "parameters": "4"}),
    ("window.dpi_scale", "[WINDOW] Dpi Scale = 1.5", {"scale": "1.5"}),
    ("http.backend", "[HTTP2] Using backend: cURL", {"backend": "cURL"}),
    ("memory.usage", "[MEMORY] Used=1 B, OsUsed=2.5 GB, Total=8 GB", {"used": "1", "used_unit": "B", "os_used": "2.5", "os_unit": "GB", "total": "8", "total_unit": "GB"}),
    ("dxc.loaded", '[DXC] Successfully loaded "dxcompiler.dll"', {"library": "dxcompiler.dll"}),
    ("filter.resolved", "[Item Filter] Online item filter request resolved to: 192.0.2.1", {"ip": "192.0.2.1"}),
    ("filter.download", "[Item Filter] Preparing to download online filter synthetic_1", {"filter_id": "synthetic_1"}),
    ("filter.status", "[Item Filter] Online item filter synthetic_1 returned status: 304", {"filter_id": "synthetic_1", "status": "304"}),
    ("filter.hash", "[Item Filter] Hash for online filter synthetic_1 is: 0123456789abcdef0123456789abcdef", {"filter_id": "synthetic_1", "hash": "0123456789abcdef0123456789abcdef"}),
    ("filter.list_download", "[Item Filter] Downloading online list", {}),
    ("screen.point_received", ": You have received an Atlas Skill Point.", {"article": "an", "point": "Atlas Skill Point"}),
    ("screen.points_received", ": You have received 3 Passive Respec Points.", {"count": "3", "point": "Passive Respec Points"}),
    ("screen.items_identified", ": 2 Items identified", {"count": "2", "label": "Items identified"}),
    ("screen.chest_locked", ": This chest is locked. A Treasure Key is required to open it.", {"key_required": " A Treasure Key is required to open it."}),
    ("screen.trade", ": Trade accepted.", {"state": "accepted"}),
    ("screen.cursor_item_destroyed", ": Item on cursor destroyed.", {}),
    ("screen.apply_failed", ": Failed to apply item: Target is corrupted.", {"reason": "Target is corrupted."}),
    ("screen.stash_full", ": Your Stash Tab with the Map Affinity does not have enough space for this item.", {"affinity": "Map"}),
    ("screen.slain", ": SyntheticCharacter has been slain.", {"character": "SyntheticCharacter"}),
    ("screen.level_up", ": SyntheticCharacter (Duelist) is now level 12", {"character": "SyntheticCharacter", "class": "Duelist", "level": "12"}),
    ("screen.afk_on", ': AFK mode is now ON. Autoreply "Synthetic reply"', {"reply": "Synthetic reply"}),
    ("screen.afk_off", ": AFK mode is now OFF.", {}),
    ("screen.area_presence", ": SyntheticCharacter has joined the area.", {"character": "SyntheticCharacter", "action": "joined"}),
    ("screen.death_count", ": You have died 12 times.", {"count": "12"}),
    ("screen.kill_count", ": You have killed 1,234,567 monsters.", {"count": "1,234,567"}),
    ("screen.played_time", ": You have played for 12 hours, 34 minutes, and 56 seconds.", {"hours": "12", "minutes": "34", "seconds": "56"}),
    ("screen.character_age", ": Your character was created 7 days, 12 hours, 34 minutes, and 56 seconds ago.", {"days": "7", "hours": "12", "minutes": "34", "seconds": "56"}),
    ("dialogue.named", "Faustus: Synthetic test utterance.", {"speaker": "Faustus", "utterance": "Synthetic test utterance."}),
)


class VersionThreeTests(unittest.TestCase):
    """Check specific structures, fields, and allowed-format boundaries."""

    def parse(self, message: str) -> dict:
        raw = f"2026/09/01 10:00:00 123 abcd [INFO Client 42] {message}\n".encode()
        return next(LogParser.iter_records(BytesIO(raw), ZoneInfo("Asia/Almaty")))

    def test_family_examples_and_fields(self):
        for kind, message, expected in CASES:
            with self.subTest(kind = kind):
                row = self.parse(message)

                self.assertEqual(row["status"], "recognized")
                self.assertEqual(row["type"], kind)
                self.assertEqual(row["fields"], expected)
                # The contextual chest rule is checked separately in ReliquaryTests.
                self.assertEqual([name for name, pattern in RuleCatalogue.MESSAGE_RULES if name != 'reliquary.message' and pattern.fullmatch(message)], [kind])
                self.assertEqual(self.parse("Unexpected " + message)["status"], "unknown")

    def test_boolean_subsystems(self):
        examples = (
            ("ENGINE", "Test Synchronous UI"), ("GRAPH", "Inline Uniforms"),
            ("JOB", "Emulate Platforms"), ("MAT", "Ingore Temp"),
            ("MESH", "Small Caches"), ("PARTICLE", "Keep Persistent"),
            ("RENDER", "Disable Transfer Queue"), ("RESOURCE", "Jobs"),
            ("SHADER", "Force Compile"), ("SOUND", "Audio"),
            ("STORAGE", "Consolidate"), ("TEXTURE", "Active Always Fits"),
            ("TRAILS", "Immutable"), ("VIDEO", "Enable"),
        )

        for subsystem, setting in examples:
            for state in ("ON", "OFF"):
                with self.subTest(subsystem = subsystem, state = state):
                    row = self.parse(f"[{subsystem}] {setting}: {state}")

                    self.assertEqual(row["type"], f"setting.{subsystem.lower()}")
                    self.assertEqual(row["fields"], {"subsystem": subsystem, "setting": setting, "state": state})

    def test_crossed_settings_and_malformed_messages(self):
        malformed = (
            "[RENDER] Audio: ON", "[SOUND] Audio: maybe", "[MAT] Ignore Temp: ON",
            "[UNKNOWN] Enable: ON", "[JOB] HIGH: many", "[JOB] Start extra",
            "[Item Filter] Online item filter synthetic_1 returned status: 999",
            "[Item Filter] Hash for online filter synthetic_1 is: xyz",
            ": You have killed 1,23,456 monsters.", ": You have received a Mystery Point.",
            ": Failed to apply item: An unknown reason.", ": Trade probably accepted.",
            ": You have played for twelve hours, 34 minutes, and 56 seconds.",
            "Unknown Speaker: Synthetic utterance.", "Faustus: ",
            "FaustusExtra: Synthetic utterance.", "Faustus: First\rSecond",
            "[ENGINE] Running Engine version 2.9.0extra",
            "[STREAMLINE][DLSS]: Loaded version 2.4.10 (NGX: invalid)",
        )

        for message in malformed:
            with self.subTest(message = message):
                self.assertEqual(self.parse(message)["status"], "unknown")

    def test_extended_versions_cache_names_and_formats(self):
        cases = (
            ("[ENGINE] Running Engine version 2.9.0", "engine.version", "version", "2.9.0"),
            ("[STREAMLINE][DLSS]: Loaded version 2.4.10 (NGX: 3.7.10)", "streamline.version", "ngx_version", "3.7.10"),
            ("[ENGINE] Cache directory: /synthetic/cache", "engine.directory", "kind", "Cache"),
            ("[ENGINE] Wiping cache ShaderCacheD3D12_X at /synthetic/cache", "engine.wipe_cache", "cache", "ShaderCacheD3D12_X"),
            ("[ENGINE] Found pipeline cache file: /synthetic/TOUCH (0 B)", "engine.pipeline_cache", "unit", "B"),
            ("[ENGINE] Found pipeline cache file: /synthetic/cache.bin (1 MB)", "engine.pipeline_cache", "path", "/synthetic/cache.bin"),
            ("[ENGINE] Found pipeline cache file: /synthetic/cache.toc (2 KB)", "engine.pipeline_cache", "path", "/synthetic/cache.toc"),
        )

        for message, kind, key, expected in cases:
            with self.subTest(kind = kind, message = message):
                row = self.parse(message)

                self.assertEqual(row["type"], kind)
                self.assertEqual(row["fields"][key], expected)
