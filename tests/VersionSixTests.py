"""Anonymous version-6 formats, rule boundaries, and continuation order."""

import unittest

from base64 import b64decode
from io import BytesIO

from zoneinfo import ZoneInfo

from poe_log_analyze.stages.parsing.LogParser import LogParser
from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue

from RulesV6Fixture import RulesV6Fixture


class VersionSixTests(unittest.TestCase):
    """Check new families and preservation of unknown variants."""

    def rows(self, raw):
        return list(LogParser.iter_records(BytesIO(raw), ZoneInfo('Asia/Almaty')))

    def test_new_technical_and_system_formats(self):
        cases = {
            "Client couldn't execute an instant action from the server.": 'action.instant_failed',
            'GEAL Triggered action with animation event was serialized to the client, but the client did not have the action.': 'action.animation_missing',
            'InstanceClientFinishChannellingAction id did not match current channelled action': 'action.channel_mismatch',
            'MeleeAttackActionClientImpl::ContactAttack on_hit_bone Invalid for Metadata/Chests/Synthetic': 'action.contact_bone_invalid',
            '[D3D11] Buffer Count = 3': 'd3d11.buffer_count',
            '[D3D11] Runtime version = 11.1': 'd3d11.runtime_version',
            '[D3D11] Feature Level = 11.1': 'd3d11.feature_level',
            '[D3D11] Driver Concurrent Creates = YES': 'd3d11.driver_capability',
            '[D3D11] Vendor = Intel': 'd3d11.vendor',
            'CreateSwapChain: SetFullScreenState 0': 'd3d11.swapchain_fullscreen',
            '[ENGINE] Old file Engine version detected 0.0.0': 'engine.old_version',
            '[ENTITY2] Regather Pass Types': 'entity2.regather',
            'GEAL Triggered action with animation event - could not find specified event': 'geal.animation_event_missing',
            'Error executing GEAL on Metadata/Pet/Synthetic.ao: Expression passed to function gave an empty result, expected a location or object': 'geal.path_error',
            'Deadlock detected with timeout 10000ms; running graph nodes: Present': 'graph.deadlock',
            'Abnormal disconnect: The realm is currently down for maintenance. Try again later.': 'network.maintenance_disconnect',
            'Abnormal disconnect: Failed to connect to instance': 'network.instance_disconnect',
            'CalculateShortestPathToRoot, nodes evaluated: 100': 'pathfinding.shortest_path',
            '[RENDER] Failed to start device': 'render.device_failed',
            '[RENDER] Falling back to DirectX11': 'render.fallback_d3d11',
            '[RENDER] Clear Descriptor Sets': 'render.lifecycle',
            ': You have played for 1 day, 2 hours, 3 minutes, and 1 second.': 'screen.played_time_days',
            ': You have played for 1 minute and 2 seconds.': 'screen.played_time_minutes',
            ': Your character was created 2 hours, 1 minute, and 1 second ago.': 'screen.character_age_hours',
            ': Failed to use item: Item is unusable.': 'screen.use_failed',
            ': 100 total Passive Skill Points (99 allocated)': 'screen.passive_points',
            ': 10 Passive Skill Points from character level': 'screen.level_points',
            ': 1 monster remains.': 'screen.monsters_remaining',
            ': Your bug report reference number is 1,234,567,890.': 'screen.bug_reference',
            ': Card drawn from the deck: <divination>{Synthetic Card}': 'screen.card_drawn',
            ': Added 10x Greater Black Scythe Artifact to your Expedition Locker': 'screen.expedition_added',
            ': You have received 8% increased Movement Speed.': 'screen.movement_reward',
            ': Cannot reroll Favoured Resources while a shipment to this port is in progress': 'screen.favoured_resources_busy',
            ': Speak to Helena in The Forest Encampment and complete the Intruders in Black quest in order to use this': 'screen.hideout_quest_required',
            ': Crafting recipe already unlocked': 'screen.recipe_already_unlocked',
            ': You do not have the item required to open this passage.': 'screen.passage_item_required',
            ': Error: Failed to join any instances.': 'screen.join_instances_failed',
            ': Target is corrupted.': 'screen.corrupted_target',
            ': The door is locked.': 'screen.door_locked',
            ": You cannot use other people's crafting benches.": 'screen.foreign_bench',
            ': Crafting failed: No target item found.': 'screen.crafting_no_target',
            ': Cannot interact with this unless it is within Lanternlight': 'screen.lantern_required',
            ': Error: Unable to connect to achievement server.': 'screen.achievement_server_failed',
            ': Unable to get PvP match list because: The operation timed out.': 'screen.pvp_list_timeout',
            ': Cannot afford Recombinator cost': 'screen.recombinator_cost',
            ': Activation cancelled.': 'screen.activation_cancelled',
            ': This door is locked. You need a Golden Key to open it.': 'screen.golden_key_required',
            ': Not enough room for item.': 'screen.item_no_room',
            ": This Contract's level was too low to grant Blueprint Reveals. Complete higher level Contracts to gain Blueprint Reveals.": 'screen.contract_low_level',
            ': Error: Failed to join instance because: The realm is currently down for maintenance. Try again later.': 'screen.join_maintenance',
            ': Error: Failed to join instance because: Disconnected from server.': 'screen.join_disconnected',
            ': You must talk to the Client before embarking on this mission.': 'screen.mission_client_required',
            '[Settlers] GoldRespec|PassivesAllocated 12|GoldCost 100': 'settlers.gold_respec',
            '[SHADER] Failed to load cache. File not found: File not found: ShaderCacheVulkan.packed/index.dat': 'shader.cache_missing',
            '[STREAMLINE] Shutdown complete': 'streamline.shutdown',
            '[STREAMLINE] Shutdown in 0.05 seconds': 'streamline.shutdown_duration',
            'Rebuilding UI::Core::Properties due to input method change': 'ui.input_method_changed',
            '[VULKAN] Separate transfer queue unsupported': 'vulkan.transfer_unsupported',
        }

        for text, kind in cases.items():
            with self.subTest(kind = kind):
                row = self.rows(RulesV6Fixture.message(text))[0]

                self.assertEqual(row['type'], kind)
                self.assertEqual(row['status'], 'recognized')
                # The contextual chest rule is checked separately in ReliquaryTests.
                self.assertEqual([name for name, pattern in RuleCatalogue.MESSAGE_RULES if name != 'reliquary.message' and pattern.fullmatch(text)], [kind])

                # The path has a free-form suffix; check the prefix boundary for this format.
                invalid = 'Unexpected ' + text if kind == 'action.contact_bone_invalid' else text + ' unexpected'

                self.assertEqual(self.rows(RulesV6Fixture.message(invalid))[0]['status'], 'unknown')

    def test_extended_variants_and_apostrophes(self):
        for text, kind in (
            ('[ENGINE] Found pipeline cache file: /synthetic/index (2.0 MB)', 'engine.pipeline_cache'),
            ('[ENGINE] Deleted pipeline cache file: /synthetic/index (0 B)', 'engine.deleted_pipeline'),
            ('[RENDER] Starting device: DirectX11', 'render.start_device'),
            ('[WINDOW] TriggerDeviceDestroyed', 'window.device'),
            ('Achivement stored: ResistAnyElement90%', 'steam.achievement'),
            (': You have received 2 Genesis Tree Equipment Items Skill Points.', 'screen.points_received'),
            (': Your Stash Tab with the Currency Affinity does not have enough space for this item.', 'screen.stash_full'),
            (': You have played for 1 hour, 2 minutes, and 1 second.', 'screen.played_time'),
            (': Your character was created 1 day, 1 hour, 1 minute, and 1 second ago.', 'screen.character_age'),
            (': Failed to apply item: Target Strongbox is locked.', 'screen.apply_failed'),
        ):
            with self.subTest(text = text):
                self.assertEqual(self.rows(RulesV6Fixture.message(text))[0]['type'], kind)

        row = self.rows(RulesV6Fixture.message("Core::OpenVirtualKeyboard called with mode '0', default text 'Synthetic's Item' and title 'Synthetic's Item'"))[0]

        self.assertEqual(row['fields'], {'mode': '0', 'default_text': "Synthetic's Item", 'title': "Synthetic's Item"})

    def test_dialogue_cr_keeps_bytes_and_does_not_consume_following_text(self):
        raw = RulesV6Fixture.message('The King in the Mists: Synthetic utterance.\r') + b'unknown continuation\r\n'
        rows = self.rows(raw)

        self.assertEqual(rows[0]['fields']['utterance'], 'Synthetic utterance.')
        self.assertEqual(rows[1]['status'], 'unknown')
        self.assertEqual(b''.join(b64decode(r['raw_base64']) for r in rows), raw)

    def test_continuation_sequence_and_interruptions(self):
        head = RulesV6Fixture.message('GEAL Triggered action with animation event was serialized to the client, but the client did not have the action.')
        fields = b'skill_instance_id: 1\naction_id: 2\nobject_id: 3\nflags: 4\ntarget_id: 5\nanimation: 6\ntime: 0.5\nevent_id: 7\n'
        rows = self.rows(head + fields)

        self.assertEqual(len(rows), 9)
        self.assertTrue(all(r['record_id'] == 1 and r['status'] == 'recognized' for r in rows))
        self.assertTrue(all('timestamp' not in r for r in rows[1:]))
        self.assertEqual(rows[-2]['fields'], {'time': '0.5'})

        for middle in (b'\n', b'unknown\n', b'\xff\n', RulesV6Fixture.message('[WINDOW] Lost focus')):
            rows = self.rows(head + middle + fields)

            self.assertTrue(all(r['status'] == 'unknown' for r in rows[-8:]))

        rows = self.rows(head + b'flags: 4\nskill_instance_id: 1\n')

        self.assertTrue(all(r['status'] == 'unknown' for r in rows[1:]))

        rows = self.rows(RulesV6Fixture.message("Client couldn't execute an instant action from the server.") + b'action type id = 12\naction type id = 13\n')

        self.assertEqual([r['record_id'] for r in rows], [1, 1, None])
        self.assertEqual(rows[-1]['status'], 'unknown')

    def test_malformed_and_ambiguous_remain_unknown(self):
        for text in ('SyntheticPlayer: v', 'SyntheticPlayer: \x00text', 'Unknown Speaker: text',
                     '[D3D11] Vendor = Unknown', '[D3D11] Buffer Count = many',
                     '[D3D11] Driver Concurrent Creates = MAYBE',
                     '[RENDER] Falling back to Unknown', 'CreateSwapChain: SetFullScreenState 2',
                     ': Your bug report reference number is 1,23,456.',
                     ': Card drawn from the deck: <divination>{broken',
                     ': Failed to apply item: Unknown reason.',
                     ': 2 monster remains.', ': 1 monsters remain.',
                     'The King in the Mists: text\r\r'):
            with self.subTest(text = text):
                self.assertEqual(self.rows(RulesV6Fixture.message(text))[0]['status'], 'unknown')
