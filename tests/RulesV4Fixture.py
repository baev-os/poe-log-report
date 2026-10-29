"""Synthetic version-4 technical diagnostics and continuation examples."""


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


class RulesV4Fixture:
    """Synthetic inputs and test helpers."""

    @staticmethod
    def header(text: str) -> bytes:
        """Create a client line from a synthetic message."""

        return f"2026/09/01 10:00:00 123 abcd [INFO Client 42] {text}\n".encode()
