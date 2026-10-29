"""Draft-only GitHub release behavior using synthetic verified archives."""

import json
import subprocess
import unittest

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from poe_log_analyze.tooling.DraftRelease import DraftRelease
from poe_log_analyze.tooling.ReleasePackager import ReleasePackager


class DraftReleaseTests(unittest.TestCase):
    """Incomplete or inconsistent artifacts must never reach a release mutation."""

    COMMIT = "a" * 40

    def setUp(self):
        temporary = Path(__file__).resolve().parents[1] / "build/tmp"
        temporary.mkdir(parents = True, exist_ok = True)
        self.temporary = TemporaryDirectory(dir = temporary)
        self.addCleanup(self.temporary.cleanup)
        self.assets = Path(self.temporary.name)

        for target, platform_name, suffix in (("Linux", "linux-x86_64", ".tar.gz"),
                                               ("Windows", "windows-x64", ".zip")):
            stem = "poe-log-report-0.1.0-" + platform_name
            archive = self.assets / (stem + suffix)
            archive.write_bytes(("Synthetic " + target + " archive").encode())
            digest = ReleasePackager.sha256(archive)
            (self.assets / (stem + ".sha256")).write_text(f"{digest}  {archive.name}\n", encoding = "ascii")
            metadata = {"release_manifest_version": "1", "version": "0.1.0", "tag": "v0.1.0",
                        "commit": self.COMMIT, "target": target, "architecture": "x86_64", "root": stem,
                        "archive": archive.name, "archive_sha256": digest}
            self.write(stem + ".json", metadata)
            verification = {"passed": True, "relocated": True, "tag": "v0.1.0", "commit": self.COMMIT,
                            "target": target, "archive": archive.name, "archive_sha256": digest,
                            "languages": {"en": {"passed": True}, "ru": {"passed": True}}}
            self.write("verification-" + target + ".json", verification)

    def write(self, name, value):
        (self.assets / name).write_text(json.dumps(value), encoding = "utf-8")

    def response(self, code = 0, stdout = "", stderr = ""):
        return subprocess.CompletedProcess([], code, stdout, stderr)

    def create(self):
        return DraftRelease.create(self.assets, "v0.1.0", self.COMMIT, "synthetic/example")

    def successful_responses(self):
        return [self.response(stdout = self.COMMIT + "\n"),
                self.response(1, stderr = "release not found"),
                self.response(stdout = "https://github.com/synthetic/example/releases/tag/v0.1.0\n")]

    def test_success_creates_only_draft_with_two_verified_targets_and_sorted_checksums(self):
        (self.assets / "unrelated-private.log").write_text("Synthetic unused file")

        with patch("subprocess.run", side_effect = self.successful_responses()) as run:
            url = self.create()

        self.assertEqual(url, "https://github.com/synthetic/example/releases/tag/v0.1.0")
        command = run.call_args_list[-1].args[0]

        self.assertEqual(command[:4], ["gh", "release", "create", "v0.1.0"])
        self.assertIn("--draft", command)
        self.assertIn("--verify-tag", command)
        self.assertEqual(command[command.index("--target") + 1], self.COMMIT)
        self.assertNotIn(str(self.assets / "unrelated-private.log"), command)
        self.assertFalse(any(call.kwargs.get("shell") for call in run.call_args_list))

        checksums = (self.assets / "SHA256SUMS").read_text().splitlines()

        self.assertEqual(len(checksums), 2)
        self.assertEqual(checksums, sorted(checksums, key = lambda line: line.split("  ", 1)[1]))

        metadata = json.loads((self.assets / "RELEASE_METADATA.json").read_text())

        self.assertEqual(metadata["state"], "draft")
        self.assertEqual(set(metadata["targets"]), {"Linux", "Windows"})
        self.assertFalse(metadata["clean_linux_runtime_verified"])
        self.assertIn("manual_clean_windows_10_11_acceptance", metadata["pending_publication_checks"])
        self.assertIn("game_material_redistribution_review", metadata["pending_publication_checks"])
        self.assertIn("remain pending", (self.assets / "release-notes.md").read_text())

    def test_missing_platform_archive_prevents_any_github_call(self):
        (self.assets / "poe-log-report-0.1.0-windows-x64.zip").unlink()

        with patch("subprocess.run") as run:
            with self.assertRaisesRegex(ValueError, "regular release asset"):
                self.create()

        run.assert_not_called()

    def test_changed_archive_or_mismatching_commit_prevents_any_github_call(self):
        path = self.assets / "poe-log-report-0.1.0-linux-x86_64.json"
        metadata = json.loads(path.read_text())
        metadata["commit"] = "b" * 40
        self.write(path.name, metadata)

        with patch("subprocess.run") as run:
            with self.assertRaisesRegex(ValueError, "manifest identity"):
                self.create()

        run.assert_not_called()
        metadata["commit"] = self.COMMIT
        self.write(path.name, metadata)
        (self.assets / "poe-log-report-0.1.0-linux-x86_64.tar.gz").write_bytes(b"changed")

        with patch("subprocess.run") as run:
            with self.assertRaisesRegex(ValueError, "archive digest"):
                self.create()

        run.assert_not_called()

    def test_missing_language_and_stale_verification_are_rejected(self):
        path = self.assets / "verification-Windows.json"
        original = json.loads(path.read_text())

        for key in ("languages", "archive_sha256"):
            changed = dict(original)
            changed[key] = {"en": {"passed": True}} if key == "languages" else "b" * 64
            self.write(path.name, changed)

            with self.subTest(key = key), patch("subprocess.run") as run:
                with self.assertRaisesRegex(ValueError, "Complete verification"):
                    self.create()

                run.assert_not_called()

    def test_remote_tag_on_another_commit_is_rejected(self):
        with patch("subprocess.run", return_value = self.response(stdout = "b" * 40)) as run:
            with self.assertRaisesRegex(ValueError, "remote release tag"):
                self.create()

        self.assertEqual(run.call_count, 1)

    def test_existing_draft_and_published_release_are_never_overwritten(self):
        for draft in (True, False):
            responses = [self.response(stdout = self.COMMIT), self.response(stdout = json.dumps({"isDraft": draft}))]

            with self.subTest(draft = draft), patch("subprocess.run", side_effect = responses) as run:
                with self.assertRaisesRegex(FileExistsError, "already exists"):
                    self.create()

                self.assertEqual(run.call_count, 2)

        self.assertFalse((self.assets / "RELEASE_METADATA.json").exists())

    def test_network_or_authentication_failure_is_not_treated_as_an_absent_release(self):
        responses = [self.response(stdout = self.COMMIT), self.response(1, stderr = "authentication failed")]

        with patch("subprocess.run", side_effect = responses) as run:
            with self.assertRaisesRegex(RuntimeError, "could not confirm"):
                self.create()

        self.assertEqual(run.call_count, 2)

    def test_clean_linux_evidence_is_validated_and_attached_when_present(self):
        verification = json.loads((self.assets / "verification-Linux.json").read_text())
        verification.update(clean_runtime = True, python_available = False)
        self.write("verification-clean-Linux.json", verification)

        with patch("subprocess.run", side_effect = self.successful_responses()) as run:
            self.create()

        self.assertIn(str(self.assets / "verification-clean-Linux.json"), run.call_args.args[0])
        metadata = json.loads((self.assets / "RELEASE_METADATA.json").read_text())

        self.assertTrue(metadata["clean_linux_runtime_verified"])
        self.assertNotIn("clean_linux_runtime_acceptance", metadata["pending_publication_checks"])

    def test_clean_linux_claim_requires_no_python_and_matching_archive(self):
        verification = json.loads((self.assets / "verification-Linux.json").read_text())
        verification.update(clean_runtime = True, python_available = True)
        self.write("verification-clean-Linux.json", verification)

        with patch("subprocess.run") as run:
            with self.assertRaisesRegex(ValueError, "without Python"):
                self.create()

        run.assert_not_called()
