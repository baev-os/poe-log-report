"""Release version and Git identity checks using a synthetic checkout."""

import shutil
import subprocess
import unittest

from pathlib import Path
from tempfile import TemporaryDirectory

from poe_log_analyze.tooling.BuildVersion import BuildVersion


@unittest.skipUnless(shutil.which("git"), "Release source checks require Git")
class BuildVersionTests(unittest.TestCase):
    """A release must identify an unchanged, versioned source commit."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / "build/tmp")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "pyproject.toml").write_text('[project]\nversion = "1.2.3"\n', encoding = "utf-8")
        self.git("init", "--template=")
        self.git("add", "pyproject.toml")
        self.git("commit", "-m", "Synthetic source")
        self.git("tag", "v1.2.3")

    def git(self, *arguments):
        return subprocess.check_output(
            ["git", "-C", str(self.root), "-c", "user.name=Synthetic",
             "-c", "user.email=synthetic@example.invalid", "-c", "commit.gpgsign=false",
             "-c", "tag.gpgsign=false", "-c", "core.hooksPath=" + str(self.root / ".disabled-hooks"), *arguments],
            text = True, stderr = subprocess.DEVNULL, timeout = 10).strip()

    def test_clean_tag_records_application_version_and_commit(self):
        release = BuildVersion.read(self.root, "v1.2.3")

        self.assertEqual(release.version, "1.2.3")
        self.assertEqual(release.release_tag, "v1.2.3")
        self.assertEqual(release.commit, self.git("rev-parse", "HEAD"))
        self.assertFalse(release.dirty)
        release.verify(self.root)

    def test_mismatching_version_and_missing_tag_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "match the application version"):
            BuildVersion.read(self.root, "v1.2.4")

        self.git("tag", "-d", "v1.2.3")

        with self.assertRaisesRegex(ValueError, "exist locally"):
            BuildVersion.read(self.root, "v1.2.3")

    def test_dirty_release_fails_but_development_metadata_remains_available(self):
        (self.root / "extra.txt").write_text("Synthetic change", encoding = "utf-8")

        with self.assertRaisesRegex(ValueError, "clean Git worktree"):
            BuildVersion.read(self.root, "v1.2.3")

        development = BuildVersion.read(self.root)

        self.assertTrue(development.dirty)
        self.assertIsNone(development.release_tag)

    def test_tag_on_another_commit_is_rejected(self):
        (self.root / "extra.txt").write_text("Synthetic change", encoding = "utf-8")
        self.git("add", "extra.txt")
        self.git("commit", "-m", "New synthetic source")

        with self.assertRaisesRegex(ValueError, "current source commit"):
            BuildVersion.read(self.root, "v1.2.3")

    def test_changes_during_compilation_are_rejected(self):
        release = BuildVersion.read(self.root, "v1.2.3")
        (self.root / "extra.txt").write_text("Synthetic change", encoding = "utf-8")

        with self.assertRaisesRegex(ValueError, "clean Git worktree"):
            release.verify(self.root)

    def test_source_copy_cannot_claim_a_release(self):
        shutil.rmtree(self.root / ".git")

        with self.assertRaisesRegex(ValueError, "known commit"):
            BuildVersion.read(self.root, "v1.2.3")
