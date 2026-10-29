"""Version-5 chat, signature catalogue, and rare-format checks."""

import unittest

from io import BytesIO

from zoneinfo import ZoneInfo

from poe_log_analyze.cli.AnalysisCli import AnalysisCli

from poe_log_analyze.stages.parsing.LogParser import LogParser
from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue
from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue


class VersionFiveTests(unittest.TestCase):
    """Specific examples without user names or conversations."""

    def parse(self, message):
        raw = f"2026/09/01 10:00:00 123 abcd [INFO Client 42] {message}\n".encode()
        return next(LogParser.iter_records(BytesIO(raw), ZoneInfo("Asia/Almaty")))

    def test_chat_fields(self):
        cases = (
            ("%<Guild> SyntheticPlayer: test: content", "chat.channel",
             {"channel": "%", "guild": "<Guild>", "character": "SyntheticPlayer", "message": "test: content"}),
            ("#Игрок: Тест", "chat.channel",
             {"channel": "#", "guild": None, "character": "Игрок", "message": "Тест"}),
            ("@From SyntheticPlayer: hello", "chat.whisper",
             {"direction": "From", "guild": None, "character": "SyntheticPlayer", "message": "hello"}),
            ("@To <Guild> SyntheticPlayer: test", "chat.whisper",
             {"direction": "To", "guild": "<Guild>", "character": "SyntheticPlayer", "message": "test"}),
        )

        for text, kind, fields in cases:
            with self.subTest(text = text):
                row = self.parse(text)

                self.assertEqual(row["type"], kind)
                self.assertEqual(row["fields"], fields)
                self.assertEqual(row["rule_version"], RuleCatalogue.RULES_VERSION)
                # The contextual chest rule is checked separately in ReliquaryTests.
                self.assertEqual([n for n, p in RuleCatalogue.MESSAGE_RULES if n != 'reliquary.message' and p.fullmatch(text)], [kind])

    def test_rejects_ambiguous_chat_and_unknown_speaker(self):
        for text in ("SyntheticPlayer: test", "@SyntheticPlayer: test", "%<Guild SyntheticPlayer: test",
                     "%Player Name: test", "@Else SyntheticPlayer: test", "Unknown Speaker: test"):
            with self.subTest(text = text):
                self.assertEqual(self.parse(text)["status"], "unknown")

    def test_catalogue_uniqueness_and_exact_labels(self):
        self.assertEqual(len(RuleCatalogue.SPEAKERS), 557)
        self.assertEqual(len(RuleCatalogue.SPEAKERS), len(set(RuleCatalogue.SPEAKERS)))

        for label in RuleCatalogue.SPEAKERS:
            row = self.parse(label + ": Synthetic utterance.")

            self.assertEqual(row["type"], "dialogue.named")
            self.assertEqual(row["fields"], {"speaker": label, "utterance": "Synthetic utterance."})

        self.assertEqual(self.parse("OshabiExtra: test")["status"], "unknown")

    def test_technical_and_screen_fields(self):
        cases = (
            ("Achivement stored: SyntheticAchievement", "steam.achievement", {"achievement": "SyntheticAchievement"}),
            ("Unable to set Steam stat SyntheticStat", "steam.stat_failed", {"stat": "SyntheticStat"}),
            ("[Item Filter] Online list returned status: 200", "filter.list_status", {"status": "200"}),
            ("[Item Filter] Online list request resolved to: 192.0.2.1", "filter.list_resolved", {"ip": "192.0.2.1"}),
            ("[Item Filter] List contained online filter synthetic with hash: abcd (local hash is: (empty))", "filter.list_entry", {"filter_id": "synthetic", "hash": "abcd", "local_hash": "(empty)"}),
            ("[SOUND] Buffer size = 64.0 MB", "sound.buffer", {"size": "64.0", "unit": "MB"}),
            ("[SOUND] Channel count = 64 (asked for 32)", "sound.channels", {"count": "64", "requested": "32"}),
            ("[SOUND] Source count = 512", "sound.sources", {"count": "512"}),
            ("[SOUND] Fmod Init success ( version 0x20311 )", "sound.fmod_init", {"version": "0x20311"}),
            ('[SOUND] Changing to device "Synthetic Audio"', "sound.device", {"device": "Synthetic Audio"}),
            ("INVALID CLIENTSTRING: SyntheticKey", "clientstring.invalid", {"key": "SyntheticKey"}),
            ("Failed to parse daily deal, exception: 'Failed to download https://example.test/item.png because: HTTP status is 404'", "daily_deal.download_failed", {"url": "https://example.test/item.png", "status": "404"}),
            (": 23 Passive Skill Points from quests:", "screen.quest_points", {"count": "23"}),
            (": (1 from Synthetic Quest)", "screen.quest_contribution", {"count": "1", "quest": "Synthetic Quest"}),
            (": 6 total Ascendancy Skill Points (6 allocated)", "screen.ascendancy_points", {"total": "6", "allocated": "6"}),
            (": You have received +15% to all Elemental Resistances.", "screen.resistance_reward", {"percent": "15"}),
            (": You have been permanently weakened by Kitava's cruel affliction. You now have -30% to all Resistances.", "screen.kitava_affliction", {"kind": "cruel", "total": None, "percent": "30"}),
            (": SyntheticPlayer is a level 64 Slayer in the Solo Self-Found league and is currently playing in Synthetic Area.", "screen.character_info", {"character": "SyntheticPlayer", "level": "64", "class": "Slayer", "league": "Solo Self-Found", "area": "Synthetic Area"}),
        )

        for text, kind, fields in cases:
            with self.subTest(kind = kind):
                row = self.parse(text)

                self.assertEqual(row["type"], kind)
                self.assertEqual(row["fields"], fields)
                # The contextual chest rule is checked separately in ReliquaryTests.
                self.assertEqual([n for n, p in RuleCatalogue.MESSAGE_RULES if n != 'reliquary.message' and p.fullmatch(text)], [kind])

    def test_malformed_values_remain_unknown(self):
        for text in ("[Item Filter] Online list returned status: 999", "[Item Filter] Online list request resolved to: 256.0.0.1",
                     "[SOUND] Source count = many", "[SOUND] Fmod Init success ( version 0xZZZ )",
                     ": (many from Synthetic Quest)", ": Failed to apply item: Unknown reason."):
            self.assertEqual(self.parse(text)["status"], "unknown")

    def test_extended_existing_patterns(self):
        for text, kind in (
            (": You have received a Genesis Tree Mysterious Items Skill Point.", "screen.point_received"),
            (": You have received 2 Atlas Skill Points.", "screen.points_received"),
            (": Failed to apply item: Target is unmodifiable.", "screen.apply_failed"),
            ("Successfully allocated passive skill id: synthetic's_skill1, name: Synthetic Skill", "passive.allocation"),
            ("[ENGINE] Deleted pipeline cache file: /synthetic/TOUCH (0 B)", "engine.deleted_pipeline"),
        ):
            self.assertEqual(self.parse(text)["type"], kind)

    def test_cli_requires_explicit_source(self):
        from contextlib import redirect_stderr
        from io import StringIO

        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as result:
            AnalysisCli.main([])

        self.assertEqual(result.exception.code, 2)
