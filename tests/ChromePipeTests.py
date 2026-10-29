"""Browser subprocess environments keep Unix sockets within the platform limit."""

import os
import unittest

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from ChromePipe import ChromePipe


class ChromePipeTests(unittest.TestCase):
    """Exercise the hosted-runner path and child environment without a browser."""

    def test_hosted_checkout_uses_shared_build_tmp_without_mutating_caller(self):
        caller = {"TMPDIR": "/synthetic/nested/tmp", "TEMP": "/synthetic/nested/temp",
                  "TMP": "/synthetic/nested/tmp", "XDG_CONFIG_HOME": "/synthetic/config"}
        original = dict(caller)
        project = Path("/home/runner/work/poe-log-report/poe-log-report").resolve()

        with patch("ChromePipe.__file__", str(project / "tests/ChromePipe.py")), patch.object(Path, "mkdir"):
            environment = ChromePipe.environment(caller)

        self.assertEqual(caller, original)
        self.assertEqual(environment["XDG_CONFIG_HOME"], caller["XDG_CONFIG_HOME"])

        for variable in ("TMPDIR", "TEMP", "TMP"):
            self.assertEqual(environment[variable], str(project / "build/tmp"))

        self.assertLessEqual(len(os.fsencode(environment["TMPDIR"] + ChromePipe.SOCKET_SUFFIX)), 107)

    def test_deep_unicode_checkout_is_rejected_before_creating_directories(self):
        project = Path(__file__).resolve().parents[1] / "build/tmp" / ("界" * 50)

        with patch("ChromePipe.__file__", str(project / "tests/ChromePipe.py")), patch.object(Path, "mkdir") as mkdir:
            with self.assertRaisesRegex(ValueError, "107 bytes.*shorter project"):
                ChromePipe.environment({})

        mkdir.assert_not_called()

    def test_pipe_subprocess_receives_consistent_temporary_environment(self):
        with TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / "build/tmp") as temporary:
            root = Path(temporary)
            caller = {"TMPDIR": str(root / "nested"), "TEMP": str(root / "other"), "TMP": str(root / "third")}

            with patch("subprocess.Popen") as launch:
                browser = ChromePipe("synthetic-chrome", root / "profile", caller, root / "browser.log")

            with browser.log:
                environment = launch.call_args.kwargs["env"]
                expected = str(Path(__file__).resolve().parents[1] / "build/tmp")

                self.assertTrue(all(environment[variable] == expected for variable in ("TMPDIR", "TEMP", "TMP")))
                self.assertEqual(caller["TMPDIR"], str(root / "nested"))
