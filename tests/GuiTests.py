"""Tkinter GUI integration checks on a separate display without user dialogs."""

import importlib.util
import unittest

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import get_ident
from time import monotonic, sleep

from poe_log_analyze.Bootstrap import Bootstrap

from unittest.mock import patch

AVAILABLE = bool(importlib.util.find_spec("_tkinter"))

if AVAILABLE:
    import tkinter as tk

    from poe_log_analyze.desktop.MainWindow import MainWindow


@unittest.skipUnless(AVAILABLE, "Tkinter is required")

class GuiTests(unittest.TestCase):
    """Check the complete window workflow with real worker threads."""

    @classmethod
    def setUpClass(cls):
        """Create a local directory for temporary test results."""

        (Path(__file__).resolve().parents[1] / "build").mkdir(exist_ok = True)

        try:
            probe = tk.Tk()
            probe.destroy()
        except tk.TclError as error:
            raise unittest.SkipTest("GUI checks require a graphical display: " + str(error)) from error

    def setUp(self):
        self.temp = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / "build")
        self.root = Path(self.temp.name)
        self.window = MainWindow(Bootstrap.report_generator(), self.root / "report")
        self.window.withdraw()
        self.source = self.root / "Лог (дом).txt"
        self.source.write_bytes(b"unknown\n" * 210 + b"\n")
        self.window.inputs.add_files([self.source])

    def tearDown(self):
        self.window.cancel_task()
        self.wait_idle()
        self.window.close()
        self.temp.cleanup()

    def wait_idle(self):
        deadline = monotonic() + 15

        while self.window.task is not None and monotonic() < deadline:
            self.window.update()
            sleep(0.005)

        if not self.window.closed:
            self.window.update()

        self.assertIsNone(self.window.task, self.window.progress.message.get())

    def test_select_dialog_cancel_keeps_source(self):
        previous = self.window.inputs.files.list.get(0)

        with patch("poe_log_analyze.desktop.InputPanel.filedialog.askopenfilenames", return_value = ()):
            self.window.inputs.choose_files()

        self.assertEqual(self.window.inputs.files.list.get(0), previous)

    def test_period_is_frozen_and_used_by_report_and_pdf(self):
        import json

        from ReportPeriodTests import ReportPeriodTests
        self.source.write_text(ReportPeriodTests.source(), encoding = "utf-8", newline = "\n")
        period = self.window.inputs.period

        self.assertFalse(period.value().active)
        self.assertTrue(period.start_entry.instate(("disabled",)))

        period.use_start.set(True)
        period.use_end.set(True)
        period.start.set(date(2026, 9, 1).isoformat())
        period.end.set(date(2026, 9, 1).isoformat())
        self.window.start_analysis()

        self.assertFalse(period.enabled)

        period.start.set(date(2030, 1, 1).isoformat())
        self.wait_idle()

        self.assertIsNotNone(self.window.session.report_path, self.window.progress.message.get())

        manifest = json.loads((self.root / 'report/report-manifest.json').read_text(encoding = "utf-8"))

        self.assertEqual(manifest['report_period']['date_from'], '2026-09-01')
        self.assertTrue((self.root / 'report/pdf/basic/report.pdf').is_file())
        self.assertFalse((self.root / 'build').exists())

    def test_reversed_period_keeps_previous_report_without_starting_task(self):
        self.window.start_analysis()
        self.wait_idle()
        previous = self.window.session.report_path
        period = self.window.inputs.period
        period.use_start.set(True)
        period.use_end.set(True)
        period.start.set(date(2026, 9, 2).isoformat())
        period.end.set(date(2026, 9, 1).isoformat())
        self.window.start_analysis()

        self.assertIsNone(self.window.task)
        self.assertIn('period start is later', self.window.progress.message.get())
        self.assertEqual(previous, self.window.session.report_path)
        self.assertTrue(previous.is_file())

    def test_comparison_dates_are_validated_and_frozen_before_worker_starts(self):
        import json

        from ReportPeriodTests import ReportPeriodTests
        self.source.write_text(ReportPeriodTests.source(), encoding = "utf-8", newline = "\n")
        self.window.start_analysis()
        self.wait_idle()
        previous = self.window.session.report_path
        panel = self.window.inputs

        self.assertFalse(panel.compare.get())
        self.assertFalse(panel.comparison_period.enabled)

        panel.extended_report.set(True)
        panel.compare.set(True)

        self.assertTrue(panel.comparison_period.enabled)

        self.window.start_analysis()

        self.assertIsNone(self.window.task)
        self.assertIn('both', self.window.progress.message.get())
        self.assertEqual(self.window.session.report_path, previous)
        self.assertTrue(previous.is_file())

        for widget, month, day in ((panel.period, 9, 1), (panel.comparison_period, 8, 31)):
            widget.use_start.set(True)
            widget.use_end.set(True)
            widget.start.set(date(2026, month, day).isoformat())
            widget.end.set(date(2026, month, day).isoformat())

        self.window.start_analysis()

        self.assertFalse(panel.comparison_period.enabled)

        panel.comparison_period.start.set(date(2030, 1, 1).isoformat())
        panel.compare.set(False)
        self.wait_idle()
        manifest = json.loads((self.root / 'report/report-manifest.json').read_text(encoding = "utf-8"))

        self.assertEqual(manifest['comparison_period']['date_from'], '2026-08-31')
        self.assertEqual(manifest['report_period']['date_from'], '2026-09-01')
        self.assertTrue((self.root / 'report/extended/public/comparison/index.html').is_file())
        self.assertFalse(panel.comparison_period.enabled)
        self.assertFalse((self.root / 'build').exists())

    def test_workspace_is_local_and_read_only(self):
        from poe_log_analyze.runtime.Workspace import Workspace

        from poe_log_analyze.desktop.InputPanel import InputPanel
        panel = InputPanel(self.window)

        self.assertEqual(Path(panel.workspace.get()), Workspace.default_workspace())
        self.assertTrue(panel.workspace_entry.instate(("readonly",)))

        panel.destroy()

    def test_analysis_always_creates_report_and_opens_it(self):
        self.window.start_analysis()
        self.wait_idle()

        self.assertIsNotNone(self.window.session.report_path, self.window.progress.message.get())
        self.assertTrue(self.window.session.report_path.is_file())
        self.assertTrue(not self.window.actions.view_report.instate(("disabled",)))

        with patch("poe_log_analyze.desktop.MainWindow.webbrowser.open", return_value = True) as opened:
            self.window.open_report()

        self.assertEqual(opened.call_args.args[0], (self.root / "index.html").as_uri())
        self.assertFalse((self.root / "build").exists())

    def test_reopened_window_finds_current_report(self):
        self.window.start_analysis()
        self.wait_idle()
        reopened = MainWindow(Bootstrap.report_generator(), self.root / "report")

        self.assertEqual(reopened.session.report_path, self.window.session.report_path)
        self.assertTrue(not reopened.actions.view_report.instate(("disabled",)))

        reopened.close()

    def test_selected_reports_always_include_pdf_on_replacement(self):
        self.window.start_analysis()
        self.wait_idle()
        pdf = self.root / 'report/pdf/basic/report.pdf'

        self.assertTrue(pdf.is_file(), self.window.progress.message.get())
        self.assertIn('report.pdf', self.window.session.report_path.read_text(encoding = "utf-8"))

        self.window.inputs.basic_report.set(False)
        self.window.inputs.extended_report.set(True)
        self.window.start_analysis()
        self.wait_idle()

        self.assertFalse(pdf.exists())
        self.assertFalse((self.root / 'report/basic').exists())
        self.assertTrue((self.root / 'report/extended/public/index.html').is_file())
        self.assertTrue((self.root / 'report/pdf/extended/report.pdf').is_file())
        self.assertIn('report.pdf', self.window.session.report_path.read_text(encoding = "utf-8"))

        self.window.inputs.basic_report.set(True)
        self.window.inputs.extended_report.set(False)
        self.window.start_analysis()
        self.wait_idle()

        self.assertTrue(pdf.is_file())
        self.assertFalse((self.root / 'report/extended').exists())
        self.assertFalse((self.root / 'report/pdf/extended').exists())

    def test_removed_controls_and_timezone_selection(self):
        self.assertEqual(self.window.inputs.period_panel.winfo_manager(), "grid")

        combo = self.window.inputs.timezone

        self.assertEqual(self.window.inputs.timezone_key(), "Asia/Almaty")
        self.assertIn("GMT", combo.get())

        self.window.inputs.set_timezone("Asia/Kathmandu")
        self.window.start_analysis()
        self.wait_idle()
        import json
        analysis = json.loads((self.window.session.result_dir / "project/data/basic.json").read_text(encoding = "utf-8"))

        self.assertEqual(analysis["timezone"], "Asia/Kathmandu")

    def test_report_language_is_selected_before_start_and_frozen(self):
        import json
        combo = self.window.inputs.report_language

        self.assertEqual(self.window.inputs.language_code(), "en")
        self.assertEqual(list(combo["values"]), ["English", "Russian"])

        self.window.inputs.set_report_language("en")
        self.window.start_analysis()

        self.assertTrue(combo.instate(("disabled",)))

        self.window.inputs.set_report_language("ru")
        self.wait_idle()
        report = self.window.session.report_path

        self.assertIsNotNone(report, self.window.progress.message.get())

        manifest = json.loads((report.parent.parent / "report-manifest.json").read_text(encoding = "utf-8"))

        self.assertEqual(manifest["report_language"], "en")
        self.assertIn('lang="en"', report.read_text(encoding = "utf-8"))

    def test_cancel_preserves_previous_report(self):
        self.window.start_analysis()
        self.wait_idle()
        previous = self.window.session.report_path
        self.source.write_bytes(b"unknown\n" * 100000)
        self.window.start_analysis()
        self.window.cancel_task()
        self.wait_idle()

        self.assertEqual(self.window.session.report_path, previous)
        self.assertIn('cancelled', self.window.progress.message.get())
        self.assertFalse((self.root / "build").exists())

    def test_export_failure_preserves_previous_report_and_cleans_run(self):
        self.window.start_analysis()
        self.wait_idle()
        previous = self.window.session.report_path

        with patch("poe_log_analyze.stages.rendering.RenderReport.RenderReport.execute", side_effect = RuntimeError("Synthetic HTML failure")):
            self.window.start_analysis()
            self.wait_idle()

        self.assertIn("Synthetic HTML failure", self.window.progress.message.get())
        self.assertEqual(self.window.session.report_path, previous)
        self.assertTrue(not self.window.actions.view_report.instate(("disabled",)))
        self.assertFalse((self.root / "build").exists())

    def test_missing_file_does_not_create_report(self):
        self.source.unlink()
        self.window.start_analysis()
        self.wait_idle()

        self.assertIn("failed", self.window.progress.message.get())
        self.assertIsNone(self.window.session.report_path)
        self.assertTrue(not self.window.actions.start.instate(("disabled",)))

    def test_close_requests_cancel_and_waits_for_thread(self):
        self.source.write_bytes(b"unknown\n" * 100000)
        self.window.start_analysis()
        self.window.close()
        self.wait_idle()

        self.assertTrue(self.window.session.closing)
        self.assertIsNone(self.window.session.report_path)

    def test_multiple_inputs_are_in_one_automatic_report(self):
        self.window.inputs.add_files([self.source])
        self.window.start_analysis()
        self.wait_idle()
        result = self.window.session.result_dir

        self.assertIsNotNone(result, self.window.progress.message.get())

        import json
        manifest = json.loads((result / "report-manifest.json").read_text(encoding = "utf-8"))

        self.assertEqual(len(manifest["sources"]), 2)
        self.assertIn("Daily playtime", (self.root / "report/basic/public/index.html").read_text(encoding = "utf-8"))

    def test_invalid_date_does_not_start_worker(self):
        period = self.window.inputs.period
        period.use_start.set(True)
        period.start.set("2026-02-30")
        self.window.start_analysis()

        self.assertIsNone(self.window.task)
        self.assertIn("YYYY-MM-DD", self.window.progress.message.get())
        self.assertFalse((self.root / "report").exists())

    def test_add_remove_and_always_visible_period(self):
        self.window.inputs.add_files([self.source, self.root / "Другой лог.txt"])
        self.window.inputs.files.list.selection_set(0, 1)
        self.window.inputs.files.remove_selected()

        self.assertEqual(self.window.inputs.paths(), (self.root / "Другой лог.txt",))

        self.window.update()

        self.assertEqual(self.window.inputs.period_panel.winfo_manager(), "grid")

        self.window.inputs.compare.set(True)

        self.assertEqual(self.window.inputs.period_panel.winfo_manager(), "grid")

    def test_report_choices_include_pdf_and_are_frozen(self):
        panel = self.window.inputs

        self.assertTrue(panel.basic_report.get())
        self.assertFalse(panel.extended_report.get())
        self.assertEqual([check.cget('text') for check in panel.report_checks],
                         ['Basic report', 'Extended report', 'Dark theme for PDFs and area image'])

        panel.basic_report.set(False)
        self.window.start_analysis()

        self.assertIsNone(self.window.task)
        self.assertIn('at least one', self.window.progress.message.get())

        panel.extended_report.set(True)
        self.window.start_analysis()

        self.assertTrue(all(check.instate(('disabled',)) for check in panel.report_checks))

        panel.extended_report.set(False)
        self.wait_idle()

        self.assertTrue((self.root / 'report/pdf/extended/report.pdf').is_file())
        self.assertFalse((self.root / 'report/basic').exists())
        self.assertTrue((self.root / 'report/extended/public/index.html').is_file())
        self.assertFalse((self.root / 'report/pdf/basic').exists())
        self.assertTrue(all(not check.instate(('disabled',)) for check in panel.report_checks))

    def test_progress_widgets_are_updated_only_in_main_thread(self):
        self.progress_threads = []
        self.original_progress = self.window.progress.update_progress

        with patch.object(self.window.progress, "update_progress", side_effect = self.record_progress):
            self.window.start_analysis()
            self.wait_idle()

        self.assertTrue(self.progress_threads)
        self.assertEqual(set(self.progress_threads), {get_ident()})

    def record_progress(self, update):
        self.progress_threads.append(get_ident())
        self.original_progress(update)
