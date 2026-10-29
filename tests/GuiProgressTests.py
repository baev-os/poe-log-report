"""Check live status and journal in a real Tk window during a synthetic run."""

import importlib.util
import unittest

from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic, sleep

from poe_log_analyze.Bootstrap import Bootstrap
from poe_log_analyze.core.execution.ProgressUpdate import ProgressUpdate
from poe_log_analyze.core.plan.ReportStage import ReportStage
from poe_log_analyze.core.process.GenerationSnapshot import GenerationSnapshot
from poe_log_analyze.core.process.GenerationStatus import GenerationStatus

AVAILABLE = bool(importlib.util.find_spec('_tkinter'))

if AVAILABLE:
    from tkinter import font

    from poe_log_analyze.desktop.MainWindow import MainWindow


@unittest.skipUnless(AVAILABLE, 'Tkinter is required')

class GuiProgressTests(unittest.TestCase):
    """Preserve history, cancellation access, and responsiveness during work."""

    @classmethod
    def setUpClass(cls):
        import tkinter as tk

        try:
            probe = tk.Tk()
            probe.destroy()
        except tk.TclError as error:
            raise unittest.SkipTest('A separate graphical display is required: ' + str(error)) from error

    def setUp(self):
        self.temp = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build')
        self.root = Path(self.temp.name)
        self.window = MainWindow(Bootstrap.report_generator(), self.root / 'report')
        self.window.update()

    def tearDown(self):
        self.window.cancel_task()
        self.wait_idle()
        self.window.close()
        self.temp.cleanup()

    def wait_idle(self):
        deadline = monotonic() + 20

        while self.window.task is not None and monotonic() < deadline:
            self.window.update()
            sleep(.005)

        self.assertIsNone(self.window.task, self.window.progress.message.get())

    def journal(self):
        return self.window.progress.log.get('1.0', 'end-1c')

    def test_large_fonts_resizing_and_small_screen_keep_controls_and_journal_visible(self):
        self.assertEqual(self.window.resizable(), (1, 1))
        self.assertGreaterEqual(font.nametofont('TkDefaultFont', root = self.window).actual('size'), 12)

        for widget in (self.window.viewport, self.window.actions, self.window.progress):
            with self.subTest(widget = str(widget)):
                self.assertTrue(widget.winfo_ismapped())
                self.assertGreater(widget.winfo_width(), 0)
                self.assertGreaterEqual(widget.winfo_rootx(), self.window.winfo_rootx())
                self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                     self.window.winfo_rootx() + self.window.winfo_width())

        self.window.geometry('850x680')
        self.window.update()

        self.assertGreaterEqual(self.window.progress.log.winfo_height(), 95)
        self.assertLess(self.window.actions.winfo_rooty(), self.window.progress.winfo_rooty())
        self.assertLessEqual(self.window.progress.log.winfo_rooty() + self.window.progress.log.winfo_height(),
                             self.window.winfo_rooty() + self.window.winfo_height())

        viewport = self.window.viewport

        self.assertGreater(viewport.inputs.winfo_height(), viewport.canvas.winfo_height())

        viewport.canvas.yview_moveto(1)
        self.window.update()

        self.assertGreater(viewport.canvas.yview()[0], 0)

        workspace = self.window.inputs.workspace_entry

        self.assertLess(workspace.winfo_rooty(), self.window.actions.winfo_rooty())

    def test_journal_keeps_operations_and_coalesces_repeated_counters(self):
        panel = self.window.progress
        panel.start()
        panel.update_state(GenerationSnapshot(GenerationStatus.RUNNING, ReportStage.PARSING, (), 7))

        for number in range(1000):
            panel.update_progress(ProgressUpdate('Read synthetic file', number, 1000, number, 'bytes'))

        panel.update_state(GenerationSnapshot(GenerationStatus.RUNNING, None, (ReportStage.PARSING,), 7))
        panel.update_progress(ProgressUpdate('Read synthetic file', 1000, 1000, 1000, 'bytes'))
        panel.update_progress(ProgressUpdate('HTML: Calendar', 1, unit = 'pages'))
        self.window.update()
        text = self.journal()

        self.assertIn('New analysis started', text)
        self.assertIn('Stage 1 of 7: Parsing', text)
        self.assertIn('Stage completed: Parsing', text)
        self.assertIn('Lines: 1,000', text)
        self.assertIn('HTML: Calendar', text)
        self.assertLess(len(text.splitlines()), 10)
        self.assertGreaterEqual(panel.log.yview()[1], .99)

        panel.copy_journal()

        self.assertEqual(self.window.clipboard_get(), text)

    def test_unknown_total_stays_indeterminate_and_does_not_display_zero_lines(self):
        panel = self.window.progress
        panel.start()
        panel.update_progress(ProgressUpdate('Reading', 5, 10, unit = 'bytes'))

        self.assertEqual(float(panel.bar['value']), 50)

        panel.update_progress(ProgressUpdate('PDF layout', 4, unit = 'pages'))

        self.assertEqual(str(panel.bar['mode']), 'indeterminate')
        self.assertIn('Pages: 4', panel.message.get())
        self.assertNotIn('Lines', panel.message.get())

        panel.finish('Done', True)

        self.assertEqual(float(panel.bar['value']), 100)
        self.assertIsNone(panel.clock_id)
        self.assertIn('Total time', panel.timing.get())

    def test_clock_and_buttons_stay_responsive_when_worker_has_no_new_messages(self):
        entered = Event()
        clicked = []

        self.window.launch(self.wait_for_cancel(entered))

        self.assertTrue(entered.wait(2))

        panel = self.window.progress
        panel.started_at -= 3
        panel.last_signal -= 2
        self.window.after(10, lambda: clicked.append(True))
        deadline = monotonic() + .6

        while monotonic() < deadline:
            self.window.update()
            sleep(.005)

        self.assertTrue(clicked)
        self.assertIn('00:00:03', panel.timing.get())
        self.assertIn('Worker signal: 2', panel.timing.get())

        self.window.actions.cancel.invoke()
        self.wait_idle()

        self.assertIn('Operation cancelled', self.journal())
        self.assertFalse(panel.running)

    @staticmethod
    def wait_for_cancel(entered):
        from functools import partial
        return partial(GuiProgressTests.cancel_operation, entered)

    @staticmethod
    def cancel_operation(entered, control):
        entered.set()

        while not control.cancelled():
            sleep(.01)

        control.check()
        raise AssertionError('Cancellation must interrupt the operation')

    def test_full_run_records_calculations_html_pdf_verification_and_success(self):
        from ReportPeriodTests import ReportPeriodTests
        source = self.root / 'synthetic.txt'
        source.write_text(ReportPeriodTests.source(), encoding = 'utf-8')
        self.window.inputs.add_files([source])
        self.window.inputs.extended_report.set(True)
        self.window.inputs.pdf_dark.set(True)
        self.window.start_analysis()

        self.assertTrue(self.window.inputs.pdf_dark_check.instate(("disabled",)))

        self.window.inputs.pdf_dark.set(False)
        self.wait_idle()
        text = self.journal()

        for stage in ReportStage:
            self.assertIn('Stage completed: ' + stage.value, text)

        for label in ('Calculate:', 'Basic HTML:', 'Extended HTML:', 'PDF:', 'page layout',
                      'Verify HTML:', 'Checksums verified', 'Analysis complete. Report ready:'):
            self.assertIn(label, text)

        import json
        manifest = json.loads((self.root / 'report/report-manifest.json').read_text())

        self.assertTrue(all(pdf['theme'] == 'dark' for pdf in manifest['pdfs'].values()))
        self.assertTrue((self.root / 'report/pdf/basic/report.pdf').is_file())
        self.assertTrue((self.root / 'report/pdf/extended/report.pdf').is_file())
        self.assertIsNone(self.window.progress.clock_id)
