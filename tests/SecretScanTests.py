"""Synthetic Git sources verify scan boundaries and private failure reporting."""

import io
import json
import os
import shutil
import subprocess
import unittest

from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from poe_log_analyze.tooling.SecretScan import SecretScan


@unittest.skipUnless(shutil.which("git"), "Secret scan checks require Git")
class SecretScanTests(unittest.TestCase):
    """No finding value or external symlink target may escape into scan evidence."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / "build/tmp")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "source"
        self.root.mkdir()
        self.git("init", "--template=")
        (self.root / ".gitignore").write_text("build/\nignored.txt\n", encoding = "utf-8")
        (self.root / "tracked.txt").write_text("Synthetic source\n", encoding = "utf-8")
        self.git("add", ".gitignore", "tracked.txt")
        self.git("commit", "-m", "Synthetic source")
        self.scanner = self.root / "build/tools/gitleaks"
        self.scanner.parent.mkdir(parents = True)
        self.scanner.write_text("Synthetic scanner", encoding = "utf-8")
        self.findings = []
        self.scanner_exit = 0
        self.version = SecretScan.VERSION
        self.omit_report = False
        self.commands = []
        self.actual_run = subprocess.run

    def git(self, *arguments):
        return subprocess.check_output(
            ["git", "-C", str(self.root), "-c", "user.name=Synthetic",
             "-c", "user.email=synthetic@example.invalid", "-c", "commit.gpgsign=false",
             "-c", "core.hooksPath=" + str(self.root / ".disabled-hooks"), *arguments],
            stderr = subprocess.DEVNULL)

    def scanner_run(self, command, **options):
        if command[0] == "git":
            return self.actual_run(command, **options)

        self.commands.append(command)

        if command[1] == "version":
            return subprocess.CompletedProcess(command, 0, stdout = self.version + "\n")

        config = Path(next(value.partition("=")[2] for value in command if value.startswith("--config=")))
        ignore = Path(next(value.partition("=")[2] for value in command if value.startswith("--gitleaks-ignore-path=")))
        self.assertEqual(config.read_text(encoding = "utf-8"), "[extend]\nuseDefault = true\n")
        self.assertEqual(ignore.read_text(encoding = "utf-8"), "")
        self.assertIn("--redact=100", command)
        self.assertIn("--ignore-gitleaks-allow", command)
        self.assertNotIn("GITLEAKS_CONFIG", options["env"])
        self.assertFalse(any(value.startswith("--baseline") for value in command))

        if not self.omit_report:
            report = Path(next(value.partition("=")[2] for value in command if value.startswith("--report-path=")))
            report.write_text(json.dumps(self.findings), encoding = "utf-8")

        return subprocess.CompletedProcess(command, self.scanner_exit)

    def run_scan(self):
        stream = io.StringIO()

        with patch("subprocess.run", side_effect = self.scanner_run), redirect_stdout(stream):
            result = SecretScan.run(self.root, Path("build/audit"))

        summary = json.loads((self.root / "build/audit/results.json").read_text(encoding = "utf-8"))

        return result, summary, stream.getvalue()

    def test_current_files_include_untracked_sources_and_exclude_ignored_or_protected_roots(self):
        (self.root / "untracked с пробелами.txt").write_text("Synthetic addition", encoding = "utf-8")
        (self.root / "ignored.txt").write_text("Excluded local input", encoding = "utf-8")

        for name in (".venv", ".aws", ".codex", ".agents"):
            (self.root / name).mkdir()
            (self.root / name / "local.txt").write_text("Excluded local settings", encoding = "utf-8")

        destination = Path(self.temporary.name) / "snapshot"
        destination.mkdir()
        count = SecretScan.snapshot(self.root, destination, dict(os.environ))

        self.assertEqual(count, 3)
        self.assertEqual({path.relative_to(destination).as_posix() for path in destination.rglob("*") if path.is_file()},
                         {".gitignore", "tracked.txt", "untracked с пробелами.txt"})

    def test_snapshot_does_not_follow_external_file_or_directory_symlinks(self):
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        (outside / "private.txt").write_text("Synthetic private input", encoding = "utf-8")

        try:
            (self.root / "file-link").symlink_to(outside / "private.txt")
            (self.root / "directory-link").symlink_to(outside, target_is_directory = True)
        except OSError:
            self.skipTest("Creating symlinks is unavailable")

        destination = Path(self.temporary.name) / "snapshot"
        destination.mkdir()
        SecretScan.snapshot(self.root, destination, dict(os.environ))

        self.assertEqual({path.name for path in destination.iterdir()}, {".gitignore", "tracked.txt"})

    def test_clean_scans_use_all_history_and_ignore_repository_suppressions(self):
        (self.root / ".gitleaks.toml").write_text("Synthetic repository config", encoding = "utf-8")
        (self.root / ".gitleaksignore").write_text("Synthetic fingerprint", encoding = "utf-8")

        with patch.dict(os.environ, {"GITLEAKS_CONFIG": "Synthetic inherited config"}):
            result, summary, _ = self.run_scan()

        self.assertEqual(result, 0)
        self.assertTrue(summary["passed"])
        self.assertEqual(summary["reachable_commits"], 1)
        self.assertIn("--log-opts=--all --full-history", self.commands[1])
        self.assertEqual([path.name for path in (self.root / "build/audit").iterdir()], ["results.json"])

    def test_findings_fail_and_only_aggregate_counts_survive(self):
        self.findings = [{"Secret": "Synthetic confidential value", "File": "Synthetic sensitive filename"}]
        self.scanner_exit = 1
        result, summary, printed = self.run_scan()
        retained = (self.root / "build/audit/results.json").read_text(encoding = "utf-8")

        self.assertEqual(result, 1)
        self.assertFalse(summary["passed"])
        self.assertEqual(summary["results"]["history"]["findings"], 1)
        self.assertNotIn("confidential", printed + retained)
        self.assertNotIn("sensitive filename", printed + retained)
        self.assertEqual([path.name for path in (self.root / "build/audit").iterdir()], ["results.json"])

    def test_missing_report_fails_even_when_scanner_returns_success(self):
        self.omit_report = True
        result, summary, _ = self.run_scan()

        self.assertEqual(result, 1)
        self.assertIsNone(summary["results"]["history"]["findings"])

    def test_unpinned_scanner_and_output_outside_build_are_rejected(self):
        self.version = "0.0.0"

        with self.assertRaisesRegex(ValueError, "requires Gitleaks"), patch("subprocess.run", side_effect = self.scanner_run):
            SecretScan.run(self.root, Path("build/audit"))

        with self.assertRaisesRegex(ValueError, "inside the project build"):
            SecretScan.run(self.root, Path("report/audit"))

    def test_snapshot_rejects_traversal_and_cross_platform_absolute_names(self):
        destination = Path(self.temporary.name) / "snapshot"
        destination.mkdir()

        for name in (b"../outside\0", b"/outside\0", b"C:\\outside\0", b"directory\\..\\outside\0"):
            with self.subTest(name = name), patch.object(SecretScan, "_git", return_value = name):
                with self.assertRaisesRegex(ValueError, "Invalid source path"):
                    SecretScan.snapshot(self.root, destination, dict(os.environ))
