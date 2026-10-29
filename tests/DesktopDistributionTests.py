"""Portable distribution and launch checks from an unrelated directory."""

import json
import os
import subprocess
import unittest

from pathlib import Path

from tempfile import TemporaryDirectory

from unittest.mock import patch

from poe_log_analyze.runtime.NativePlatform import NativePlatform
from poe_log_analyze.runtime.RuntimeResources import RuntimeResources
from poe_log_analyze.runtime.Workspace import Workspace

from poe_log_analyze.tooling.DesktopDistribution import DesktopDistribution


class DesktopDistributionTests(unittest.TestCase):
    """Check real paths and arguments while keeping all data inside build/."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / "build/tmp")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.dist = self.root / "Поставка с пробелами"
        resources = self.dist / "poe_log_analyze/resources"
        resources.mkdir(parents = True)
        (resources / "build-info.json").write_text('{"distribution_layout": "app"}', encoding = "utf-8")
        (self.dist / "library.so").write_bytes(b"synthetic library")
        (self.dist / "LICENSE").write_text("Synthetic license", encoding = "utf-8")
        (self.dist / "THIRD_PARTY_NOTICES.md").write_text("Synthetic notices", encoding = "utf-8")

    @unittest.skipUnless(os.name == "posix", "Shell launcher checks require Linux")
    def test_relocated_launcher_preserves_arguments_cwd_and_exit_status(self):
        binary = self.dist / "poe-log-analyze"
        binary.write_text('#!/bin/sh\nprintf "%s\\0" "$PWD" "$@"\nexit 23\n', encoding = "utf-8", newline = "\n")
        binary.chmod(0o755)
        (self.dist / "alias.so").symlink_to("library.so")
        DesktopDistribution.arrange(self.dist, NativePlatform("Linux", "x86_64", 64))
        moved = self.root / "Перенесённая поставка"
        self.dist.rename(moved)

        self.assertEqual({path.name for path in moved.iterdir()}, {"app", "README.md", "poe-log-analyze"})
        self.assertEqual((moved / "app/alias.so").read_bytes(), b"synthetic library")

        arguments = ["--cli", "имя с пробелами", 'кавычки"', "$значение", ""]
        result = subprocess.run([str(moved / "poe-log-analyze"), *arguments], cwd = self.root,
                                capture_output = True, check = False)

        self.assertEqual(result.returncode, 23)
        self.assertEqual(result.stdout.decode().split("\0")[:-1], [str(self.root), *arguments])
        self.assertEqual(DesktopDistribution.runtime_directory(moved), moved / "app")

        with self.assertRaises(FileExistsError):
            DesktopDistribution.arrange(moved, NativePlatform("Linux", "x86_64", 64))

        self.assertTrue((moved / "poe-log-analyze").is_file())

    def test_windows_entrypoint_keeps_executable_and_libraries_together(self):
        (self.dist / "poe-log-analyze.exe").write_bytes(b"synthetic executable")
        DesktopDistribution.arrange(self.dist, NativePlatform("Windows", "AMD64", 64))

        self.assertEqual({path.name for path in self.dist.iterdir()}, {"app", "README.md", "poe-log-analyze.cmd"})

        command = (self.dist / "poe-log-analyze.cmd").read_bytes()

        self.assertIn(b'"%~dp0app\\poe-log-analyze.exe" %*\r\n', command)
        self.assertIn(b'exit /b %errorlevel%', command)
        self.assertTrue((self.dist / "app/poe-log-analyze.exe").is_file())
        self.assertIn(r".\poe-log-analyze.cmd", (self.dist / "README.md").read_text(encoding = "utf-8"))

    def test_packaged_workspace_and_resources_are_independent_of_parent_project(self):
        for nested in (False, True):
            with self.subTest(nested = nested):
                distribution = self.root / str(nested)
                runtime = distribution / "app" if nested else distribution
                package = runtime / "poe_log_analyze"
                resources = package / "resources"
                resources.mkdir(parents = True)
                metadata = {"distribution_layout": "app"} if nested else {}
                (resources / "build-info.json").write_text(json.dumps(metadata), encoding = "utf-8")

                with patch("poe_log_analyze.runtime.Workspace.__file__", str(package / "runtime/Workspace.py")), \
                        patch("poe_log_analyze.runtime.RuntimeResources.__file__", str(package / "runtime/RuntimeResources.py")), \
                        patch.object(NativePlatform, "current", return_value = NativePlatform("Linux", "x86_64", 64)):
                    self.assertEqual(Workspace.project_root(), distribution)
                    self.assertEqual(Workspace.default_workspace(), distribution / "report")
                    self.assertEqual(RuntimeResources.resource_root(), resources)

                    with self.assertRaises(ValueError):
                        Workspace.local_output(self.root / "build/outside")

                self.assertEqual(DesktopDistribution.runtime_directory(distribution), runtime)
