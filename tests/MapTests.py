"""Map checks using independent transition and gap sequences."""

import hashlib
import json
import unittest

from datetime import datetime, timedelta, timezone

from pathlib import Path
from tempfile import TemporaryDirectory

from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.stages.reconstruction.MapActivityBuilder import MapActivityBuilder


class MapTests(unittest.TestCase):
    """Durations are specified manually; false endings and joins are prohibited."""

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ledger = Path(self.temp.name) / "lines.jsonl"
        self.rows = []

    def event(self, second, kind, fields = None, status = "recognized"):
        line = len(self.rows) + 1
        moment = datetime(2026, 7, 20, 23, 59, 0, tzinfo = timezone(timedelta(hours = 5)))
        self.rows.append({"line_number": line, "record_id": line, "type": kind,
                          "fields": fields or {}, "status": status,
                          "timestamp": (moment + timedelta(seconds = second)).isoformat() if second is not None else None})

    def enter(self, second, area = "MapWorldsBeach", seed = "1", instance = "11", name = "Beach"):
        self.event(second, "network.instance_connect", {"host": "PRIVATE_IP"})

        if instance is not None:
            self.event(second, "instance.id", {"instance_id": instance})

        self.event(second, "area.generate", {"area": area, "level": "83", "seed": seed})
        self.event(second + 2, "area.enter", {"area": name})

    def build(self, **kwargs):
        self.ledger.write_text("".join(json.dumps(row) + "\n" for row in self.rows))
        return MapActivityBuilder.build_map_activity(self.ledger, "Asia/Almaty", hashlib.sha256(self.ledger.read_bytes()).hexdigest(), **kwargs)

    def runs(self, result):
        return [run for day in result["by_date"].values() for run in day["runs"]]

    def test_returns_pause_afk_deaths_and_midnight(self):
        self.enter(0)
        self.event(10, "screen.afk_on")
        self.event(12, "screen.afk_on")
        self.event(20, "screen.afk_off")
        self.event(21, "screen.slain", {"character": "PRIVATE_CHARACTER"})
        self.event(22, "screen.death_count", {"count": "999"})
        self.event(23, "unknown", {"text": "PRIVATE_CHAT"}, "unknown")
        self.enter(30, "HideoutOssuary", "9", "99", "Hideout")
        self.enter(70)
        self.event(75, "window.focus", {"state": "Lost"})
        self.enter(90, seed = "2", instance = "22")
        self.event(100, "chat.local", {"text": "PRIVATE_CHAT"})

        result = self.build()
        first, last = self.runs(result)

        self.assertEqual(first["seconds"], 46)  # 2 to 30 and 72 to 90.
        self.assertEqual(first["afk_seconds"], 10)
        self.assertEqual(first["between_visits_seconds"], 42)
        self.assertEqual(first["returns"], 1)
        self.assertEqual(first["date"], "2026-07-20")
        self.assertEqual(first["uncertain_lines"], 1)
        self.assertEqual(len(first["death_messages"]), 1)
        self.assertEqual(last["seconds"], 0)
        self.assertEqual(last["unbounded_visits"], 1)
        self.assertIsNone(last["visits"][0]["seconds"])
        self.assertEqual(result["entrances"], 3)
        self.assertEqual(first['visits'][0]['death_messages'][0]['character'], 'PRIVATE_CHARACTER')
        self.assertNotIn("PRIVATE_CHAT", json.dumps(result))
        self.assertNotIn("PRIVATE_IP", json.dumps(result))

    def test_mechanics_and_deaths_belong_to_each_visit(self):
        self.enter(0)
        self.event(3, 'dialogue.named', {'speaker': 'Sister Cassia'})
        self.event(4, 'dialogue.named', {'speaker': 'Sister Cassia'})
        self.event(5, 'dialogue.named.field', {'speaker': 'Oshabi'})
        self.event(6, 'dialogue.named', {'speaker': 'Tujen, the Harbourmaster'})
        self.event(7, 'dialogue.named', {'speaker': 'Rog, the Disenchanter'})
        self.event(8, 'dialogue.named', {'speaker': 'The Maven'}, 'unknown')
        self.event(9, 'screen.slain', {'character': 'SyntheticOne'})
        self.event(10, 'screen.slain', {'character': 'SyntheticTwo'})
        self.enter(20, 'HideoutOssuary')
        self.event(23, 'dialogue.named', {'speaker': 'Niko, Master of the Depths'})
        self.enter(30)
        self.event(33, 'dialogue.named', {'speaker': 'Tujen, the Haggler'})
        self.event(34, 'dialogue.named', {'speaker': 'Jun, Veiled Master'})
        self.event(35, 'dialogue.named', {'speaker': 'Gravicius Reborn'})
        self.event(None, 'screen.slain', {'character': 'SyntheticUnknownTime'})
        visits = self.runs(self.build())[0]['visits']

        self.assertEqual(len(visits), 2)
        self.assertEqual([item['code'] for item in visits[0]['mechanics']], ['blight'])
        self.assertEqual([item['code'] for item in visits[1]['mechanics']], ['expedition', 'betrayal'])
        self.assertEqual([item['character'] for item in visits[0]['death_messages']], ['SyntheticOne', 'SyntheticTwo'])
        self.assertEqual(visits[1]['death_messages'][0]['character'], 'SyntheticUnknownTime')
        self.assertIsNone(visits[1]['death_messages'][0]['timestamp'])

    def test_events_after_boundaries_are_not_attached_to_previous_map(self):
        for kind, at, fields in (
            ('network.abnormal_disconnect', 10, {}), ('log.open', 10, {}),
            ('network.instance_connect', 10, {}),
            ('area.generate', 10, {'area': 'MapWorldsBeach', 'level': '83', 'seed': '2'}),
            ('area.enter', 10, {'area': 'Unknown entry'}),
            ('dialogue.named', 4000, {'speaker': 'Oshabi'}),
            ('dialogue.named', -10, {'speaker': 'Oshabi'}),
        ):
            with self.subTest(kind = kind, at = at):
                self.rows = []
                self.enter(0)
                self.event(kind = kind, second = at, fields = fields)
                self.event(at + 1, 'dialogue.named', {'speaker': 'Oshabi'})
                self.event(at + 2, 'screen.slain', {'character': 'OutsideVisit'})
                self.event(at + 3, 'dialogue.named', {'speaker': 'Alara, the Cyaxan Progeny',
                                                     'utterance': 'Have we met before?'})
                visit = self.runs(self.build())[0]['visits'][0]

                self.assertEqual(visit['mechanics'], [])
                self.assertEqual(visit['death_messages'], [])
                self.assertEqual(visit['mercenaries'], [])

    def test_mercenary_greetings_keep_first_evidence_per_name_and_visit(self):
        first = {'speaker': 'Alara, the Cyaxan Progeny', 'utterance': 'Have we met before? '}
        second = {'speaker': 'Zargan, the Keitan Brute', 'utterance': 'You sure you want to do this?'}
        self.enter(0)
        self.event(3, 'dialogue.named', {**first, 'utterance': 'Synthetic combat dialogue.'})
        self.event(4, 'dialogue.named', first)
        self.event(5, 'dialogue.named', {**first, 'utterance': 'Advance. I am ready for you.'})
        self.event(6, 'dialogue.named', second, 'unknown')
        self.event(7, 'dialogue.named.field', second)
        self.event(8, 'dialogue.named', second)
        self.rows[-1]['record_id'] -= 1
        self.event(9, 'dialogue.named', second)
        self.enter(10, 'HideoutOssuary', seed = '2', instance = '2')
        self.event(13, 'dialogue.named', first)
        self.enter(20)
        self.event(None, 'dialogue.named', first)
        visits = self.runs(self.build())[0]['visits']

        self.assertEqual(len(visits), 2)
        self.assertEqual([item['speaker'] for item in visits[0]['mercenaries']], [first['speaker'], second['speaker']])
        self.assertEqual(visits[0]['mercenaries'][0]['utterance'], first['utterance'])
        self.assertEqual(visits[0]['mercenaries'][0]['line'], 6)
        self.assertEqual(len(visits[1]['mercenaries']), 1)
        self.assertIsNone(visits[1]['mercenaries'][0]['timestamp'])

    def test_mercenaries_before_entry_in_hideout_and_boss_arena_are_not_map_encounters(self):
        greeting = {'speaker': 'Alara, the Cyaxan Progeny', 'utterance': 'Have we met before?'}
        self.event(0, 'area.generate', {'area': 'MapWorldsBeach', 'level': '83', 'seed': '1'})
        self.event(1, 'dialogue.named', greeting)
        self.event(2, 'area.enter', {'area': 'Beach'})

        for second, area in ((10, 'HideoutOssuary'), (20, 'MapAtlasShapersRealm'), (30, '1_1_1')):
            self.enter(second, area, seed = str(second), instance = str(second))
            self.event(second + 3, 'dialogue.named', greeting)

        for run in self.runs(self.build(include_areas = True)):
            self.assertTrue(all(not visit['mercenaries'] for visit in run['visits']))

    def test_discovery_before_entry_belongs_to_new_map_and_repetitions_are_tags(self):
        self.enter(0)
        self.event(5, 'area.generate', {'area': 'MapWorldsDunes', 'level': '83', 'seed': '2'})
        self.event(6, 'hideout.discoverable', {'hideout': 'HideoutSynthetic'})
        self.event(7, 'area.enter', {'area': 'Dunes'})
        self.event(8, 'hideout.discoverable', {'hideout': 'HideoutSynthetic'})
        self.event(9, 'screen.reflecting_mist')
        self.event(10, 'screen.reflecting_mist')
        self.event(11, 'screen.suicide', {'character': 'SyntheticHero'})
        first, second = self.runs(self.build())

        self.assertEqual(first['visits'][0]['discoveries'], [])
        self.assertEqual([item['code'] for item in second['visits'][0]['discoveries']], ['hideout', 'reflecting_mist'])
        self.assertLess(second['visits'][0]['discoveries'][0]['line'], second['visits'][0]['entry_line'])
        self.assertEqual(second['visits'][0]['death_messages'][0]['code'], 'screen.suicide')
        self.assertEqual(len(second['death_messages']), 1)

    def test_pending_discoveries_are_discarded_on_boundaries_and_other_generation(self):
        for kind, fields, at in (
            ('network.abnormal_disconnect', {}, 3), ('log.open', {}, 3),
            ('network.instance_connect', {}, 3),
            ('area.generate', {'area': 'MapWorldsDunes', 'level': '83', 'seed': '2'}, 3),
            ('window.focus', {}, 4000), ('window.focus', {}, -5),
        ):
            with self.subTest(kind = kind, at = at):
                self.rows = []
                self.event(0, 'area.generate', {'area': 'MapWorldsBeach', 'level': '83', 'seed': '1'})
                self.event(1, 'hideout.discoverable', {'hideout': 'HideoutSynthetic'})
                self.event(at, kind, fields)
                self.event(at + 1, 'area.enter', {'area': 'Synthetic'})
                runs = self.runs(self.build())

                self.assertTrue(all(not visit['discoveries'] for run in runs for visit in run['visits']))

    def test_mechanic_catalogue_uses_recognized_npcs_and_excludes_other_areas(self):
        from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue
        from poe_log_analyze.stages.reconstruction.MapEncounterTracker import MapEncounterTracker

        self.assertTrue(set(MapEncounterTracker.BY_SPEAKER) <= set(RuleCatalogue.SPEAKERS))

        self.enter(0)

        for second, speaker in enumerate(MapEncounterTracker.BY_SPEAKER, 3):
            self.event(second, 'dialogue.named', {'speaker': speaker})

        self.assertEqual({item['code'] for item in self.runs(self.build())[0]['visits'][0]['mechanics']},
                         set(MapEncounterTracker.SPEAKERS))

        for area in ('MapWorldsShapersRealm', 'MapAtlasShapersRealm', 'Synthesis_MapBoss',
                     'HeistDungeon8', 'ExpeditionCemetery', 'HideoutOssuary'):
            with self.subTest(area = area):
                self.rows = []
                self.enter(0, area)
                self.event(3, 'dialogue.named', {'speaker': 'The Maven'})

                self.assertEqual(self.runs(self.build(include_areas = True))[0]['visits'][0]['mechanics'], [])

    def test_instance_change_missing_identity_and_same_name(self):
        self.enter(0)
        self.enter(10, instance = "12")
        self.enter(20, area = "MapWorldsLaboratory")
        self.enter(30, instance = None)
        self.enter(40, instance = None)
        self.enter(50, seed = "0")
        self.enter(60, seed = "0")

        result = self.build()

        self.assertEqual(result["run_count"], 7)
        self.assertEqual(sum(r["returns"] for r in self.runs(result)), 0)
        self.assertFalse(self.runs(result)[3]["identity_complete"])

    def test_gap_clock_disconnect_and_open_never_invent_duration(self):
        for kind, at in (("log.open", 20), ("network.abnormal_disconnect", 20),
                         ("chat.local", 4000), ("chat.local", -10)):
            with self.subTest(kind = kind, at = at):
                self.rows = []
                self.enter(0)
                self.event(at, kind)
                self.enter(max(at + 1, 30))

                result = self.build()

                self.assertEqual(result["run_count"], 2)
                self.assertEqual(result["unbounded_visits"], 2)
                self.assertEqual(result["seconds"], 0)

    def test_no_generation_no_entry_and_non_map_are_visible(self):
        self.event(0, "area.enter", {"area": "Beach"})
        self.enter(10, "HeistLaboratory")
        self.event(20, "area.generate", {"area": "MapWorldsBeach", "seed": "1", "level": "83"})

        result = self.build()

        self.assertEqual(result["run_count"], 0)
        self.assertEqual(result["diagnostics"]["entry_without_generation"], 1)
        self.assertEqual(result["diagnostics"]["generation_without_entry"], 1)
        self.assertEqual(result["outside_areas"], {"HeistLaboratory": 1})

    def test_missing_time_breaks_pairing(self):
        self.enter(0)
        self.event(None, "area.enter", {"area": "Town"})
        self.enter(20)

        result = self.build()

        self.assertEqual(result["run_count"], 2)
        self.assertEqual(result["seconds"], 0)
        self.assertEqual(result["diagnostics"]["missing_time"], 1)

    def test_missing_entry_time_keeps_visit_and_known_exit(self):
        self.event(0, "instance.id", {"instance_id": "1"})
        self.event(0, "area.generate", {"area": "MapWorldsBeach", "level": "83", "seed": "1"})
        self.event(None, "area.enter", {"area": "Beach"})
        self.event(20, "network.instance_connect")

        result = self.build()
        run = self.runs(result)[0]
        visit = run["visits"][0]

        self.assertIsNone(run["started_at"])
        self.assertEqual(run["date"], "undated")
        self.assertIsNone(visit["entered_at"])
        self.assertEqual(visit["ended_at"], self.rows[-1]["timestamp"])
        self.assertIsNone(visit["seconds"])
        self.assertFalse(visit["bounded"])
        self.assertEqual(visit["position_at"], self.rows[0]["timestamp"])
        self.assertEqual(visit["position_basis"], "generation")
        self.assertEqual(result["seconds"], 0)

    def test_both_times_unknown_and_later_exit_anchor(self):
        self.event(None, "area.generate", {"area": "MapWorldsBeach", "level": "83", "seed": "1"})
        self.event(None, "area.enter", {"area": "Beach"})
        unknown = self.runs(self.build())[0]

        self.assertIsNone(unknown["position_at"])
        self.assertIsNone(unknown["visits"][0]["ended_at"])

        self.event(20, "network.instance_connect")
        bounded_end = self.runs(self.build())[0]

        self.assertIsNone(bounded_end["started_at"])
        self.assertEqual(bounded_end["position_basis"], "exit")
        self.assertEqual(bounded_end["unbounded_visits"], 1)

    def test_afk_spans_transitions_but_not_breaks(self):
        self.event(0, "screen.afk_on")
        self.enter(10)
        self.enter(20, "HideoutOssuary")
        self.enter(30)
        self.event(35, "screen.afk_off")
        self.enter(40, "HideoutOssuary")
        first = self.runs(self.build())[0]

        self.assertEqual(first["seconds"], 16)
        self.assertEqual(first["afk_seconds"], 11)

    def test_arena_and_synthesis_scope(self):
        self.enter(0, "MapWorldsElderArenaUber")
        self.enter(10, "Synthesis_MapGuardian1")
        self.enter(20, "MavenBoss")

        result = self.build()

        self.assertEqual((result["map_count"], result["arena_count"]), (1, 1))
        self.assertEqual(result["outside_areas"], {"MavenBoss": 1})

    def test_empty_integrity_offsets_order_and_cancellation(self):
        self.assertEqual(self.build()["run_count"], 0)

        with self.assertRaisesRegex(ValueError, "changed"):
            MapActivityBuilder.build_map_activity(self.ledger, "Asia/Almaty", "0" * 64)

        with self.assertRaises(GenerationCancelled):
            self.build(control = ExecutionContext(cancelled = lambda: True))

        with self.assertRaises(ValueError):
            self.build(max_gap_seconds = 0)

        self.event(0, "log.open")
        self.rows[0]["timestamp"] = "2026-07-20T01:00:00"

        with self.assertRaisesRegex(ValueError, "offset"):
            self.build()
