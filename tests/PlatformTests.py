"""Platform branches are checked separately from native Windows acceptance."""

import json
import os
import zoneinfo
import unittest

from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import patch

from poe_log_analyze.runtime.JsonFiles import JsonFiles
from poe_log_analyze.runtime.NativePlatform import NativePlatform
from poe_log_analyze.runtime.ProcessEnvironment import ProcessEnvironment
from poe_log_analyze.runtime.RuntimeResources import RuntimeResources

from poe_log_analyze.tooling.DesktopBuilder import DesktopBuilder


class PlatformTests(unittest.TestCase):
    """Mocking the platform in a test is not an actual Windows GUI run."""

    def test_names_architectures_and_build_options(self):
        windows = NativePlatform("Windows", "AMD64", 64)
        linux = NativePlatform("Linux", "x86_64", 64)

        self.assertEqual(windows.application_name, "poe-log-analyze.exe")
        self.assertEqual(DesktopBuilder.platform_options(windows), ["--msvc=latest", "--windows-console-mode=attach", "--assume-yes-for-downloads"])
        self.assertNotIn("--static-libpython=no", DesktopBuilder.platform_options(windows))

        for system, machine, bits in (("Darwin", "arm64", 64), ("Windows", "AMD64", 32), ("Linux", "aarch64", 64)):
            with self.subTest(system = system, machine = machine), self.assertRaises(RuntimeError):
                NativePlatform(system, machine, bits)

    def test_compiler_report_rejects_development_modules_in_runtime(self):
        with TemporaryDirectory() as temporary:
            report = Path(temporary) / "compilation-report.xml"
            launcher = '<module name="poe_log_analyze.cli.DesktopLauncher"/>'
            toolkit = ''.join(f'<module name="{name}"/>' for name in ('tkinter', 'tkinter.ttk', '_tkinter'))
            launcher += toolkit
            report.write_text('<report>' + launcher + '<module name="poe_log_analyze.stages.parsing.ParseLogs"/></report>')

            self.assertEqual(len(DesktopBuilder.validate_runtime_modules(report)), 2)

            for name in (*DesktopBuilder.EXCLUDED_PACKAGES, "poe_log_analyze.tooling.DesktopBuilder",
                         "unittest.mock"):
                with self.subTest(name = name):
                    report.write_text('<report>' + launcher + f'<module name="{name}"/></report>')

                    with self.assertRaisesRegex(ValueError, "Excluded modules"):
                        DesktopBuilder.validate_runtime_modules(report)

            report.write_text('<report><module name="other"/></report>')

            with self.assertRaisesRegex(ValueError, "entry point"):
                DesktopBuilder.validate_runtime_modules(report)

            report.write_text('<report><module name="poe_log_analyze.cli.DesktopLauncher"/></report>')

            with self.assertRaisesRegex(ValueError, "Tkinter"):
                DesktopBuilder.validate_runtime_modules(report)

    def test_process_temp_paths_are_local_without_global_environment_changes(self):
        previous = dict(os.environ)

        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "Данные приложения"
            env = ProcessEnvironment.within(root)

            for key in ("TEMP", "TMP", "TMPDIR"):
                self.assertEqual(Path(env[key]), root / "tmp")
                self.assertTrue(Path(env[key]).is_dir())

            self.assertEqual(env["PYTHONUTF8"], "1")

        self.assertEqual(dict(os.environ), previous)

    def test_json_has_explicit_utf8_and_lf(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "Данные.json"
            JsonFiles.write_json(path, {"текст": "строка\nещё"})

            self.assertNotIn(b"\r\n", path.read_bytes())
            self.assertEqual(json.loads(path.read_bytes()), {"текст": "строка\nещё"})

    def test_tzdata_is_available_without_system_database(self):
        previous = zoneinfo.TZPATH

        try:
            zoneinfo.reset_tzpath([])

            with TemporaryDirectory() as temporary, patch.object(RuntimeResources, "resource_root", return_value = Path(temporary)):
                RuntimeResources.configure_timezone()

                self.assertTrue(zoneinfo.TZPATH)

                zone = zoneinfo.ZoneInfo.no_cache("Asia/Almaty")

                self.assertEqual(zone.key, "Asia/Almaty")
        finally:
            zoneinfo.reset_tzpath(previous)
