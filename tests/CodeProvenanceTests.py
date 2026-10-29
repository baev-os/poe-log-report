"""Repository boundaries in code metadata using synthetic worktrees."""

import os
import shutil
import subprocess
import unittest

from pathlib import Path

from tempfile import TemporaryDirectory

from unittest.mock import patch

from poe_log_analyze.runtime.CodeProvenance import CodeProvenance


@unittest.skipUnless(shutil.which("git"), "The metadata check requires Git")
class CodeProvenanceTests(unittest.TestCase):
    """A source copy must not inherit the surrounding repository version."""

    @staticmethod
    def _git(root: Path, *args: str) -> str:
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        return subprocess.check_output(
            ["git", "-C", str(root), "-c", "user.name=Synthetic",
             "-c", "user.email=synthetic@example.invalid", "-c", "commit.gpgsign=false",
             "-c", "core.hooksPath=" + str(root / ".disabled-hooks"), *args],
            env = environment, stderr = subprocess.DEVNULL, text = True, timeout = 5,
        ).strip()

    @classmethod
    def _repository(cls, root: Path) -> str:
        root.mkdir()
        cls._git(root, "init", "--template=")
        (root / "sample.txt").write_text("synthetic\n", encoding = "utf-8")
        cls._git(root, "add", "sample.txt")
        cls._git(root, "commit", "-m", "Синтетический снимок")

        return cls._git(root, "rev-parse", "HEAD")

    def test_copy_without_git_does_not_inherit_parent(self):
        with TemporaryDirectory() as temporary:
            parent = Path(temporary) / "parent"
            self._repository(parent)
            project = parent / "copy"
            project.mkdir()

            self.assertEqual(CodeProvenance.git_state(project), {"sha": None, "dirty": None})
            self.assertFalse((project / ".git").exists())

    def test_own_repository_reports_clean_and_changed_states(self):
        with TemporaryDirectory() as temporary:
            parent = Path(temporary) / "parent"
            self._repository(parent)
            project = parent / "проект с пробелами"
            sha = self._repository(project)
            index = project / ".git" / "index"
            before = index.read_bytes()

            self.assertEqual(CodeProvenance.git_state(project), {"sha": sha, "dirty": False})

            (project / "sample.txt").write_text("changed\n", encoding = "utf-8")

            self.assertEqual(CodeProvenance.git_state(project), {"sha": sha, "dirty": True})
            self.assertEqual(index.read_bytes(), before)

            self._git(project, "add", "sample.txt")

            self.assertEqual(CodeProvenance.git_state(project), {"sha": sha, "dirty": True})

            self._git(project, "reset", "--hard", "HEAD")
            (project / "untracked.txt").write_text("synthetic\n", encoding = "utf-8")

            self.assertEqual(CodeProvenance.git_state(project), {"sha": sha, "dirty": True})

    def test_linked_worktree_gitfile_is_supported(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            sha = self._repository(project)
            worktree = root / "linked"
            self._git(project, "worktree", "add", "--detach", str(worktree))

            self.assertTrue((worktree / ".git").is_file())
            self.assertEqual(CodeProvenance.git_state(worktree), {"sha": sha, "dirty": False})

            (worktree / "untracked.txt").write_text("synthetic\n", encoding = "utf-8")

            self.assertEqual(CodeProvenance.git_state(worktree), {"sha": sha, "dirty": True})
            self.assertEqual(CodeProvenance.git_state(project), {"sha": sha, "dirty": False})

    def test_inherited_git_environment_does_not_redirect_metadata(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            sha = self._repository(project)
            other = root / "other"
            self._repository(other)
            (other / "untracked.txt").write_text("synthetic\n", encoding = "utf-8")
            copy = root / "copy"
            copy.mkdir()

            with patch.dict(os.environ, {
                "GIT_DIR": str(other / ".git"), "GIT_WORK_TREE": str(other),
                "GIT_COMMON_DIR": str(other / ".git"), "GIT_INDEX_FILE": str(other / ".git" / "index"),
            }):
                self.assertEqual(CodeProvenance.git_state(project), {"sha": sha, "dirty": False})
                self.assertEqual(CodeProvenance.git_state(copy), {"sha": None, "dirty": None})

    def test_invalid_local_git_does_not_fall_back_to_parent(self):
        with TemporaryDirectory() as temporary:
            parent = Path(temporary) / "parent"
            self._repository(parent)
            project = parent / "copy"
            project.mkdir()
            (project / ".git").write_text("invalid\n", encoding = "utf-8")

            self.assertEqual(CodeProvenance.git_state(project), {"sha": None, "dirty": None})

    def test_missing_git_executable_keeps_unknown_metadata(self):
        with patch("subprocess.check_output", side_effect = FileNotFoundError):
            self.assertEqual(CodeProvenance.git_state(Path.cwd()), {"sha": None, "dirty": None})
