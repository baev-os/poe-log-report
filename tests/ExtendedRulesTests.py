"""Synthetic version-2 rule-family examples and recognition boundaries."""

import unittest

from io import BytesIO

from zoneinfo import ZoneInfo

from poe_log_analyze.stages.parsing.LogParser import LogParser
from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue


# Examples were written manually from observed formats; no user data is included.
CASES = (
    ("scene.source", "[SCENE] Set Source [Synthetic Town]", {"source": "Synthetic Town"}),
    ("scene.height_map", "[SCENE] Height Map Texture: 16 x 32", {"width": "16", "height": "32"}),
    ("loading.duration", "[LOADING SCREEN] (Synthetic Town) Duration = 1.25 seconds", {"area": "Synthetic Town", "seconds": "1.25"}),
    ("network.instance_connect", "Connecting to instance server at 192.0.2.1:6112 ", {"host": "192.0.2.1", "port": "6112"}),
    ("network.instance_latency", "Connect time to instance server was 42ms", {"milliseconds": "42"}),
    ("network.async_connect", "Async connecting to login.example.test:20488", {"host": "login.example.test", "port": "20488"}),
    ("network.connected", "Connected to login.example.test in 22ms.", {"host": "login.example.test", "milliseconds": "22"}),
    ("engine.pipeline_cache", "[ENGINE] Found pipeline cache file: ../../cache/example.foz (1.25 MB)", {"path": "../../cache/example.foz", "size": "1.25", "unit": "MB"}),
    ("engine.build_revision", "[ENGINE] Build Revision: 123", {"revision": "123"}),
    ("engine.version", "[ENGINE] Running Engine version 4.5", {"version": "4.5"}),
    ("engine.directory", "[ENGINE] Settings directory: C:\\example\\", {"kind": "Settings", "path": "C:\\example\\"}),
    ("engine.wipe_cache", "[ENGINE] Wiping cache Minimap at C:\\cache\\Minimap.tmp", {"cache": "Minimap", "path": "C:\\cache\\Minimap.tmp"}),
    ("engine.os", "[ENGINE] OS: Windows 10 Build 12345", {"kind": "OS", "version": "10", "build": "12345"}),
    ("engine.lifecycle", "[ENGINE] Reset static", {"stage": "Reset static"}),
    ("vulkan.extension", "[VULKAN] Supported device extension: VK_KHR_example_2", {"action": "Supported", "scope": "device", "extension": "VK_KHR_example_2"}),
    ("vulkan.present_mode", "[VULKAN] Present mode = Fifo", {"kind": "Present mode", "mode": "Fifo"}),
    ("vulkan.invalid_present_mode", "[VULKAN] Supported present mode = invalid ( abcdef12 )", {"value": "abcdef12"}),
    ("vulkan.swapchain", "[VULKAN] Init SwapChain = 1920x1080", {"operation": "Init SwapChain", "width": "1920", "height": "1080"}),
    ("vulkan.min_images", "[VULKAN] Min Image Count = 2", {"count": "2"}),
    ("vulkan.memory_type", "[VULKAN] Memory type: heap index = 0, property = { DeviceLocal | HostVisible }", {"heap_index": "0", "properties": "{ DeviceLocal | HostVisible }"}),
    ("vulkan.memory_heap", "[VULKAN] Memory heap: size = 4.5 GB, flags = {}", {"size": "4.5", "unit": "GB", "flags": "{}"}),
    ("vulkan.queue", "[VULKAN] Queue : family = 1, count = 2, flags = { Transfer | SparseBinding }", {"family": "1", "count": "2", "flags": "{ Transfer | SparseBinding }"}),
    ("vulkan.selected_queue", "[VULKAN] Graphics queue: family = 0, index = 1", {"kind": "Graphics", "family": "0", "index": "1"}),
    ("vulkan.gpu_type", "[VULKAN] GPU type: DiscreteGpu (NVidia)", {"kind": "DiscreteGpu", "vendor": "NVidia"}),
    ("vulkan.lifecycle", "[VULKAN] ResizeBuffers", {"operation": "ResizeBuffers"}),
    ("etrade.request", "[ETrade] Requesting to instance for api type 0, request_id = 12", {"api_type": "0", "request_id": "12"}),
    ("etrade.response", "[ETrade] Response from instance for request_id 12, error = 0, took 45 ms", {"request_id": "12", "error": "0", "milliseconds": "45"}),
    ("passive.allocation", "Successfully unallocated passive skill id: synthetic123, name: Synthetic Skill", {"operation": "unallocated", "skill_id": "synthetic123", "name": "Synthetic Skill"}),
    ("trade.gold", "local player brought an item for 123 gold", {"gold": "123"}),
    ("asset.bone_no_influences", "[Art/Models/Example/rig.ast] Bone: synthetic_bone has no vertex influences", {"asset": "Art/Models/Example/rig.ast", "bone": "synthetic_bone"}),
    ("action.detach_finished", "Trying to detach an action that has already finished! Type id: 123", {"action_type_id": "123"}),
    ("effect.missing_node_type", "Failed to create effect graph node (ID: 123). Node type does not exist", {"node_id": "123"}),
    ("effect.missing_node", 'Failed to create effect graph node "Example" in graph "Metadata/Example.fxgraph"', {"node": "Example", "graph": "Metadata/Example.fxgraph"}),
    ("font.empty", "Empty font file (typeface = Example). Skipping...", {"typeface": "Example"}),
    ("window.device", "[WINDOW] TriggerDeviceReset", {"operation": "TriggerDeviceReset"}),
    ("startup.stage_start", "[STARTUP] Tencent Start", {"stage": "Tencent"}),
    ("startup.stage_duration", "[STARTUP] Tencent in 1.25e-05 seconds", {"stage": "Tencent", "seconds": "1.25e-05"}),
    ("streamline.init", "[STREAMLINE] Initialized (Enabled)", {"stage": "Initialized (Enabled)"}),
    ("streamline.init_duration", "[STREAMLINE] Init in 0.5 seconds", {"seconds": "0.5"}),
    ("streamline.version", "[STREAMLINE][DLSS]: Loaded version 1.2 (NGX: 3.4)", {"component": "DLSS", "version": "1.2", "ngx_version": "3.4"}),
    ("streamline.proxy", "[STREAMLINE][NIS]: Loaded proxy version", {"component": "NIS"}),
    ("streamline.enabled", "[STREAMLINE][XeSS] Enabled: false", {"component": "XeSS", "enabled": "false"}),
    ("streamline.reflex", "[STREAMLINE][Reflex] Reflex Low Latency: OFF", {"setting": "Low Latency", "state": "OFF"}),
    ("steam.stats_stored", "Steam stats stored", {}),
    ("area.unconnected_depth", "Attempting to get depth for location in unconnected area", {}),
)


class ExtendedRulesTests(unittest.TestCase):
    """Full matches, named fields, and rejection of unconfirmed forms."""

    def parse(self, message: str) -> dict:
        raw = f"2026/09/01 10:00:00 123 abcd [INFO Client 42] {message}\n".encode()
        return next(LogParser.iter_records(BytesIO(raw), ZoneInfo("Asia/Almaty")))

    def test_examples_fields_and_unambiguous_matching(self):
        for kind, message, fields in CASES:
            with self.subTest(kind = kind):
                row = self.parse(message)

                self.assertEqual(row["status"], "recognized")
                self.assertEqual(row["type"], kind)
                self.assertEqual(row["fields"], fields)
                # The contextual chest rule is checked separately in ReliquaryTests.
                self.assertEqual([name for name, pattern in RuleCatalogue.MESSAGE_RULES if name != 'reliquary.message' and pattern.fullmatch(message)], [kind])

    def test_changed_prefix_is_unknown_for_every_family(self):
        for kind, message, _ in CASES:
            with self.subTest(kind = kind):
                self.assertEqual(self.parse("unexpected " + message)["status"], "unknown")

    def test_bad_fields_and_truncated_messages(self):
        malformed = (
            "Connecting to instance server at 256.0.2.1:6112 ",
            "Connecting to instance server at 192.0.2.1:65536 ",
            "Connecting to instance server at 192.0.2.1:0 ",
            "Connecting to instance server at 192.0.2.1:6112 extra",
            "Connect time to instance server was -1ms",
            "[LOADING SCREEN] (Town) Duration = -2 seconds",
            "[LOADING SCREEN] (Town) Duration = 2 milliseconds",
            "[ENGINE] Found pipeline cache file: example.txt (1 MB)",
            "[ENGINE] Found pipeline cache file: example.foz (1 unknown)",
            "[VULKAN] Supported device extension: something_else",
            "[VULKAN] Supported device extension: VK_KHR_example extra",
            "[VULKAN] Present mode = UnverifiedMode",
            "[VULKAN] Memory type: heap index = 0, property = { DeviceLocal | }",
            "[VULKAN] Queue : family = 1, count = 2, flags = { Transfer",
            "[ETrade] Response from instance for request_id 12, error = 0",
            "Successfully allocated passive skill id: example, name: ",
            "local player brought an item for 12 silver",
            "[Art/Models/Example/rig.ast] Bone: bone has no vertex influences extra",
            "[STARTUP] UnknownStage Start",
            "[STREAMLINE][DLSS] Enabled: maybe",
            "[STREAMLINE][UnknownComponent] Enabled: true",
            "Steam stats stored extra",
            "Unknown Speaker: Some arbitrary text",
        )

        for message in malformed:
            with self.subTest(message = message):
                self.assertEqual(self.parse(message)["status"], "unknown")

    def test_port_boundaries_and_optional_observed_space(self):
        for port in (1, 9999, 10000, 59999, 60000, 64999, 65000, 65499, 65500, 65529, 65530, 65535):
            for suffix in ("", " "):
                with self.subTest(port = port, suffix = suffix):
                    row = self.parse(f"Connecting to instance server at 255.0.0.1:{port}{suffix}")

                    self.assertEqual(row["type"], "network.instance_connect")
