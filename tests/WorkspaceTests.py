"""Local workspace checks and rejection of writes outside its boundaries."""

import unittest

from contextlib import redirect_stderr, chdir
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from poe_log_analyze.Bootstrap import Bootstrap

from poe_log_analyze.cli.AnalysisCli import AnalysisCli

from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.cli.ReportCli import ReportCli

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.runtime.Workspace import Workspace

ROOT = Path(__file__).resolve().parents[1]


class WorkspaceTests(unittest.TestCase):
    """Relative paths are project-relative; symlinks cannot bypass the restriction."""

    def setUp(self):
        (ROOT / "build").mkdir(exist_ok = True)
        self.temporary = TemporaryDirectory(dir = ROOT / "build")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)

    def test_default_does_not_depend_on_cwd(self):
        with chdir(self.folder):
            self.assertEqual(Workspace.project_root(), ROOT)
            self.assertEqual(Workspace.default_workspace(), ROOT / "report")
            self.assertEqual(Workspace.local_output(Path("build/example")), ROOT / "build/example")

    def test_removed_database_option_is_rejected_without_writes(self):
        output = self.folder / "result"
        error = StringIO()

        with redirect_stderr(error), self.assertRaises(SystemExit) as failure:
            AnalysisCli.main(["--input", str(self.folder / "missing"),
                              "--output", str(output), "--database"])

        self.assertEqual(failure.exception.code, 2)
        self.assertIn("Invalid arguments", error.getvalue())
        self.assertFalse(output.exists())
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_outside_and_symlink_are_rejected_without_writes(self):
        for path in (ROOT / "outside-result", Path("../outside-result")):
            with self.assertRaisesRegex(ValueError, "inside"):
                Workspace.local_output(path)

        link = self.folder / "escape"
        link.symlink_to(ROOT, target_is_directory = True)

        with self.assertRaisesRegex(ValueError, "inside"):
            Workspace.local_output(link / "outside-result")

        self.assertFalse((ROOT / "outside-result").exists())

    def test_gui_command_rejects_external_output_before_work(self):
        output = ROOT / "outside-result"

        with self.assertRaisesRegex(ValueError, "inside"):
            Bootstrap.report_generator().generate(
                ReportRequest((self.folder / "missing",), output), ExecutionContext())

        self.assertFalse(output.exists())

    def test_cli_rejects_external_output(self):
        error = StringIO()

        with redirect_stderr(error):
            status = AnalysisCli.main(["--input", str(self.folder / "missing"),
                           "--output", str(ROOT / "outside-result")])

        self.assertEqual(status, 1)
        self.assertIn("inside", error.getvalue())

    def test_report_cli_rejects_external_output_before_reading_analysis(self):
        error = StringIO()

        with redirect_stderr(error):
            status = ReportCli.main(["--result", str(self.folder / "missing"),
                                         "--output", str(ROOT / "outside-result")])

        self.assertEqual(status, 1)
        self.assertIn("inside", error.getvalue())
        self.assertFalse((ROOT / "outside-result").exists())
