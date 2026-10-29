"""Synthetic version-4 technical diagnostics and continuation examples."""

import unittest

from base64 import b64decode
from io import BytesIO

from zoneinfo import ZoneInfo

from poe_log_analyze.stages.parsing.LogParser import LogParser
from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue


CASES = (
    ("skill.missing_row", "Could not find row for SyntheticSkill skill..", {"skill": "SyntheticSkill"}),
    ("action.update_missing", "Matching object found for InstanceClientActionUpdate, but no matching action was found on object to update.", {}),
    ("precalc.table", "PrecalcBaseTypeHashMap", {"table": "BaseTypeHashMap"}),
    ("lmdb.access_denied", "Failed to open LMDB environment at /synthetic/Pipelines. Error: Access denied.\r", {"path": "/synthetic/Pipelines", "trailing_cr": "\r"}),
    ("game.closing", "Closing game gracefully", {}),
    ("currency.foresight", "CurrencyApplicationForesightResult recieved", {}),
    ("labyrinth.craft_options", "InstanceClientLabyrinthCraftResultOptionsList recieved", {}),
    ("adapter.enumerated", "Enumerated adapter: Synthetic GPU", {"adapter": "Synthetic GPU"}),
    ("adapter.device", "Enumerated device for adapter: Synthetic GPU. Selected feature level: 12. Max feature level: 13", {"adapter": "Synthetic GPU", "selected": "12", "maximum": "13"}),
    ("adapter.output", "Enumerated output for adapter Synthetic GPU of \\\\.\\DISPLAY1", {"adapter": "Synthetic GPU", "output": "\\\\.\\DISPLAY1"}),
    ("input.xinput_library", "Selected XInput.dll is xinput1_4.dll", {"library": "xinput1_4.dll"}),
    ("ui.rebuild", "Rebuilding UI::Core properties. Current input mode = '2'", {"mode": "2"}),
    ("ui.virtual_keyboard", "Core::OpenVirtualKeyboard called with mode '0', default text '' and title 'Synthetic Search'", {"mode": "0", "default_text": "", "title": "Synthetic Search"}),
    ("http.user_agent", "[HTTP2] User agent: PoE release/tags/3.28.0k Windows x64", {"version": "3.28.0k", "bits": "64"}),
    ("vulkan.physical_device", "[VULKAN] Found matching physical device using LUID 0123AB (Synthetic GPU - Synthetic Monitor)", {"luid": "0123AB", "device": "Synthetic GPU - Synthetic Monitor"}),
    ("filter.saved", "[Item Filter] Successfully saved online filter synthetic. Hash is now: abcd0123", {"filter_id": "synthetic", "hash": "abcd0123"}),
    ("filter.reloaded", "[Item Filter] Finished reloading online filter synthetic. Result: true. Hash: abcd0123. Type: Normal. Message: ", {"filter_id": "synthetic", "result": "true", "hash": "abcd0123", "type": "Normal", "message": ""}),
    ("filter.empty_hash", "[Item Filter] Hash for online filter synthetic is: (empty)", {"filter_id": "synthetic"}),
    ("network.resync", "Resyncing 123", {"value": "123"}),
    ("network.abnormal_disconnect", "Abnormal disconnect: An unexpected disconnection occurred.", {}),
    ("geal.error", "Error executing GEAL on [ab12] (-3, 4) Metadata/Synthetic@1: Expression passed to function gave an empty result, expected a number type", {"object_id": "ab12", "x": "-3", "y": "4", "path": "Metadata/Synthetic@1", "reason": "Expression passed to function gave an empty result, expected a number type"}),
    ("engine.deleted_pipeline", "[ENGINE] Deleted pipeline cache file: /synthetic/cache.foz (1.2 MB)", {"path": "/synthetic/cache.foz", "size": "1.2", "unit": "MB"}),
    ("hideout.discoverable", "Spawning discoverable Hideout HideoutSynthetic", {"hideout": "HideoutSynthetic"}),
    ("stash.reorder", "Re-ordering tabs to match stash data", {}),
    ("mastery.allocated", "Successfully allocated mastery effect id: 12, mastery: mastery_synthetic1, name: Synthetic Mastery", {"effect_id": "12", "mastery": "mastery_synthetic1", "name": "Synthetic Mastery"}),
    ("screen.area_unreachable", ": You can't go to this area from here.", {}),
    ("screen.portals_disabled", ": Failed to use item: Portals are disabled here.", {}),
    ("screen.bestiary_added", ": This Beast has been successfully added to your Bestiary.", {}),
    ("screen.hiveblood_warning", ": <brequelwarning>{Stored Hiveblood is almost at the maximum!}", {}),
)
PHRASES = (
    ("fear_not_elements", "Fear not the elements."), ("eye_of_storm", "Open the eye of the storm."),
    ("world_to_ice", "Turn your world to ice."), ("none_shall_stop", "None shall stop you."),
    ("courage", "Courage stands tall."), ("fog_of_war", "Shroud your path in the fog of war."),
    ("death_wait", "Death doesn't wait."), ("past_serves_present", "The past shall serve the present."),
    ("restore_lost", "Restore that which was lost."), ("hit_once", "Hit hard. Hit once."),
    ("pain_exquisite", "Deliver pain exquisite."), ("overpower", "Overpower, overrun, overcome. "),
    ("rage", "Let your rage flow freely."), ("shadows", "Wield your shadows."),
)


from RulesV4Fixture import RulesV4Fixture


class VersionFourTests(unittest.TestCase):
    """Check exact fields, continuation context, and byte preservation."""

    def parse(self, text: str) -> dict:
        # A body CR is separate from CRLF: physical input retains CRCRLF.
        return next(LogParser.iter_records(BytesIO(RulesV4Fixture.header(text)[:-1] + b"\r\n"), ZoneInfo("Asia/Almaty")))

    def test_messages_and_unique_rules(self):
        for kind, text, expected in CASES:
            with self.subTest(kind = kind):
                row = self.parse(text)

                self.assertEqual(row["status"], "recognized")
                self.assertEqual(row["type"], kind)
                self.assertEqual(row["fields"], expected)
                # The contextual chest rule is checked separately in ReliquaryTests.
                self.assertEqual([name for name, pattern in RuleCatalogue.MESSAGE_RULES if name != 'reliquary.message' and pattern.fullmatch(text)], [kind])
                self.assertEqual(self.parse("Unexpected " + text)["status"], "unknown")

    def test_exact_screen_phrases(self):
        for name, phrase in PHRASES:
            with self.subTest(name = name):
                self.assertEqual(self.parse(": " + phrase)["type"], "screen.phrase." + name)
                self.assertEqual(self.parse(": " + phrase + " extra")["status"], "unknown")
                self.assertEqual(self.parse("OtherSpeaker: " + phrase)["status"], "unknown")

    def test_action_update_continuations(self):
        raw = (RulesV4Fixture.header(CASES[1][1]) + b"\tAction Id = 12\n\tDetach Id = 34\n"
               b"\tSkill Type Id = 56\n\tSkill Instance Id =78\n\tAction Id = 99\n")
        rows = list(LogParser.iter_records(BytesIO(raw), ZoneInfo("Asia/Almaty")))

        self.assertEqual([row["record_id"] for row in rows], [1, 1, 1, 1, 1, None])
        self.assertEqual([row["fields"] for row in rows[1:5]], [
            {"action_id": "12"}, {"detach_id": "34"}, {"skill_type_id": "56"}, {"skill_instance_id": "78"},
        ])
        self.assertEqual(rows[-1]["status"], "unknown")
        self.assertEqual(b"".join(b64decode(row["raw_base64"]) for row in rows), raw)

    def test_wrong_order_and_interruption(self):
        for middle in (b"\tDetach Id = 1\n", b"\n", b"\xff\n", RulesV4Fixture.header("Unknown")):
            rows = list(LogParser.iter_records(BytesIO(RulesV4Fixture.header(CASES[1][1]) + middle + b"\tAction Id = 2\n"), ZoneInfo("Asia/Almaty")))

            self.assertEqual(rows[-1]["status"], "unknown")
            self.assertIsNone(rows[-1]["record_id"])

    def test_invalid_variants(self):
        bad = (
            "PrecalcUnknownMap", "CurrencyApplicationForesightResult received",
            "Failed to open LMDB environment at /synthetic. Error: Unknown error.",
            "[Item Filter] Finished reloading online filter synthetic. Result: true. Hash: xyz. Type: Normal. Message: ",
            "[Item Filter] Successfully saved online filter synthetic. Hash is now: ",
            "Error executing GEAL on [ab12] (1, 2) Metadata/Synthetic: Unknown reason",
            "[HTTP2] User agent: PoE release/tags/unknown Windows x64",
            "[Art/Models/Synthetic/rig.ast] Bone: bone| has no vertex influences",
            "[ENGINE] Deleted pipeline cache file: /synthetic/cache.txt (1 MB)",
        )

        for text in bad:
            with self.subTest(text = text):
                self.assertEqual(self.parse(text)["status"], "unknown")

    def test_changed_existing_formats(self):
        cases = (
            ("[STARTUP] DebugGUI Start", "startup.stage_start", "stage", "DebugGUI"),
            ("[STARTUP] DebugGUI in 1e-05 seconds", "startup.stage_duration", "seconds", "1e-05"),
            ("[Art/Models/Synthetic/rig.ast] Bone: bone_a|bone_b has no vertex influences", "asset.bone_no_influences", "bone", "bone_a|bone_b"),
            ("[Item Filter] Hash for online filter synthetic is: abcd0123", "filter.hash", "hash", "abcd0123"),
        )

        for text, kind, field, value in cases:
            with self.subTest(kind = kind):
                row = self.parse(text)

                self.assertEqual(row["type"], kind)
                self.assertEqual(row["fields"][field], value)

    def test_lmdb_embedded_cr_is_preserved(self):
        text = CASES[3][1]
        row = self.parse(text)

        self.assertEqual(row["text"], RulesV4Fixture.header(text)[:-1].decode())
        self.assertEqual(b64decode(row["raw_base64"]), RulesV4Fixture.header(text)[:-1] + b"\r\n")
        self.assertEqual(row["fields"]["trailing_cr"], "\r")
        self.assertEqual(self.parse(text[:-1])["fields"]["trailing_cr"], "")
