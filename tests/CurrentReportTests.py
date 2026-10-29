"""Report replacement, recovery, cleanup, and protection of neighboring files."""

import subprocess
import sys
import unittest

from dataclasses import replace
from pathlib import Path

from tempfile import TemporaryDirectory

from unittest.mock import patch

from poe_log_analyze.Bootstrap import Bootstrap

from poe_log_analyze.core.CurrentReport import CurrentReport
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.runtime.ReportLock import ReportLock
from poe_log_analyze.runtime.Workspace import Workspace


class CurrentReportTests(unittest.TestCase):
    """All checks use a separate synthetic root inside build/."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source.log"
        self.source.write_bytes(b"unknown\n")
        self.output = self.root / "report"
        self.request = ReportRequest((self.source,), self.output, report_language = "ru", replace_report = True)
        self.generator = Bootstrap.report_generator()

    def test_repeated_run_replaces_report_and_keeps_only_final_files(self):
        first = self.generator.generate(self.request)

        self.assertEqual(first.directory, self.output)
        self.assertEqual((self.root / "index.html").read_text(), CurrentReport.ENTRY)
        self.assertTrue(first.report_path.is_file())

        stale = self.output / "public/old-page.html"
        stale.write_text("previous report")
        self.source.write_bytes(b"\n")

        self.generator.generate(replace(self.request, report_language = "en"))

        self.assertFalse(stale.exists())
        self.assertIn('lang="en"', first.report_path.read_text())
        self.assertEqual({p.name for p in self.root.iterdir()}, {"source.log", "report", "index.html"})
        self.assertFalse(list(self.root.rglob("lines.jsonl")))
        self.assertEqual(self.source.read_bytes(), b"\n")

    def test_previous_russian_entry_can_be_replaced_by_an_english_report(self):
        self.generator.generate(self.request)
        entry = self.root / "index.html"
        entry.write_text(CurrentReport.LEGACY_ENTRY, encoding = "utf-8")

        result = self.generator.generate(replace(self.request, report_language = "en"))

        self.assertEqual(entry.read_text(encoding = "utf-8"), CurrentReport.ENTRY)
        self.assertIn('lang="en"', result.report_path.read_text(encoding = "utf-8"))
        self.assertFalse((self.root / "build").exists())

    def test_failure_and_cancellation_keep_previous_report(self):
        self.generator.generate(self.request)
        before = self.snapshot()

        with patch("poe_log_analyze.stages.rendering.RenderReport.RenderReport.execute",
                   side_effect = RuntimeError("synthetic failure")):
            with self.assertRaises(RuntimeError):
                self.generator.generate(self.request)

        self.assertEqual(before, self.snapshot())

        control = ExecutionContext(cancelled = self.cancel_after_parsing)

        with self.assertRaises(GenerationCancelled):
            self.generator.generate(self.request, control)

        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.root / "build").exists())

    def test_pdf_beside_entry_is_replaced_and_removed_with_report(self):
        request = replace(self.request, generate_pdf = True)

        self.generator.generate(request)
        pdf = self.root / "report.pdf"
        before = pdf.read_bytes()

        self.assertEqual(before, (self.output / "public/report.pdf").read_bytes())

        self.generator.generate(replace(request, report_language = "en"))

        self.assertNotEqual(before, pdf.read_bytes())
        self.assertEqual(pdf.read_bytes(), (self.output / "public/report.pdf").read_bytes())

        self.generator.generate(self.request)

        self.assertFalse(pdf.exists())
        self.assertFalse((self.output / "public/report.pdf").exists())
        self.assertFalse((self.root / "build").exists())

    def test_pdf_publication_failures_restore_all_previous_files(self):
        request = replace(self.request, generate_pdf = True)

        self.generator.generate(request)
        before = self.snapshot()
        self.original_replace = Path.replace

        with patch.object(Path, "replace", autospec = True, side_effect = self.fail_new_pdf):
            with self.assertRaisesRegex(OSError, "synthetic"):
                self.generator.generate(replace(request, report_language = "en"))

        self.assertEqual(before, self.snapshot())

        for pdf_enabled in (True, False):
            with patch.object(Path, "touch", side_effect = OSError("synthetic publication failure")):
                with self.assertRaisesRegex(OSError, "synthetic"):
                    self.generator.generate(replace(request, generate_pdf = pdf_enabled, report_language = "en"))

            self.assertEqual(before, self.snapshot())

    def fail_new_pdf(self, path, target):
        if path.name == "report.pdf":
            raise OSError("synthetic PDF replacement failure")

        return self.original_replace(path, target)

    def test_first_pdf_publication_failure_removes_both_copies(self):
        with patch.object(Path, "touch", side_effect = OSError("synthetic publication failure")):
            with self.assertRaisesRegex(OSError, "synthetic"):
                self.generator.generate(replace(self.request, generate_pdf = True))

        self.assertEqual({p.name for p in self.root.iterdir()}, {"source.log"})

    def test_interrupted_pdf_publication_is_recovered(self):
        self.generator.generate(replace(self.request, generate_pdf = True))
        (self.root / "index.html").write_text(CurrentReport.LEGACY_ENTRY, encoding = "utf-8")
        before = self.snapshot()
        work = self.root / "build/tmp/report-generation"
        work.mkdir(parents = True)
        (work / "publication.json").write_text('{"report": true, "index": true, "pdf": true}')
        (work / "previous-index.html").write_bytes((self.root / "index.html").read_bytes())
        (self.root / "report.pdf").rename(work / "previous-report.pdf")
        self.output.rename(work / "previous-report")
        self.output.mkdir()
        (self.root / "report.pdf").write_bytes(b"partial PDF")

        with CurrentReport(self.output):
            self.assertEqual((self.root / "report.pdf").read_bytes(), before[Path("report.pdf")])

        self.assertEqual(before, self.snapshot())

    def test_unrelated_pdf_symlink_and_input_are_preserved(self):
        pdf = self.root / "report.pdf"
        pdf.write_bytes(b"user document")

        with self.assertRaisesRegex(ValueError, "unrelated"):
            self.generator.generate(self.request)

        self.assertEqual(pdf.read_bytes(), b"user document")

        with self.assertRaisesRegex(ValueError, "internal workspace"):
            self.generator.generate(replace(self.request, inputs = (pdf,)))

        self.assertEqual(pdf.read_bytes(), b"user document")

        pdf.unlink()
        pdf.symlink_to(self.source)

        with self.assertRaisesRegex(ValueError, "symbolic link"):
            self.generator.generate(self.request)

        self.assertTrue(pdf.is_symlink())
        self.assertEqual(self.source.read_bytes(), b"unknown\n")

    def cancel_after_parsing(self):
        return any((self.root / "build").rglob("lines.jsonl"))

    def snapshot(self):
        return {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def test_failed_index_replacement_rolls_back_old_report(self):
        self.generator.generate(self.request)
        before = self.snapshot()
        self.original_replace = Path.replace

        with patch.object(Path, "replace", autospec = True, side_effect = self.fail_new_entry):
            with self.assertRaisesRegex(OSError, "synthetic"):
                self.generator.generate(replace(self.request, report_language = "en"))

        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.root / "build").exists())

    def fail_new_entry(self, path, target):
        if path.name == "index.html":
            raise OSError("synthetic index replacement failure")

        return self.original_replace(path, target)

    def test_first_publication_failure_removes_partial_report(self):
        self.original_replace = Path.replace

        with patch.object(Path, "replace", autospec = True, side_effect = self.fail_new_entry):
            with self.assertRaises(OSError):
                self.generator.generate(self.request)

        self.assertEqual({p.name for p in self.root.iterdir()}, {"source.log"})

    def test_abandoned_temporary_files_and_interrupted_publication_are_recovered(self):
        self.generator.generate(self.request)
        (self.root / "index.html").write_text(CurrentReport.LEGACY_ENTRY, encoding = "utf-8")
        before = self.snapshot()
        work = self.root / "build/tmp/report-generation"
        work.mkdir(parents = True)
        (work / "publication.json").write_text('{"report": true, "index": true}')
        (work / "previous-index.html").write_bytes((self.root / "index.html").read_bytes())
        self.output.rename(work / "previous-report")
        self.output.mkdir()
        (self.output / "incomplete.html").write_text("unfinished")
        (self.root / "index.html").write_text("unfinished entry")

        with CurrentReport(self.output):
            self.assertEqual((self.root / "index.html").read_text(), CurrentReport.LEGACY_ENTRY)
            self.assertTrue((self.output / "public/index.html").is_file())

        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.root / "build").exists())

    def test_other_files_and_symlinks_are_preserved(self):
        entry = self.root / "index.html"
        entry.write_text("unrelated file")

        with self.assertRaisesRegex(ValueError, "unrelated"):
            self.generator.generate(self.request)

        self.assertEqual(entry.read_text(), "unrelated file")

        entry.unlink()
        self.output.mkdir()
        (self.output / "user-data.txt").write_text("keep")

        with self.assertRaisesRegex(ValueError, "unrelated"):
            self.generator.generate(self.request)

        self.assertEqual((self.output / "user-data.txt").read_text(), "keep")

        link = self.root / "nested"
        link.mkdir()
        (link / "report").symlink_to(self.output, target_is_directory = True)

        with self.assertRaises(ValueError):
            self.generator.generate(replace(self.request, output = link / "report"))

    def test_inputs_inside_report_or_temporary_area_are_never_removed(self):
        for folder in (self.output, self.root / "build/tmp/report-generation"):
            folder.mkdir(parents = True, exist_ok = True)
            source = folder / "source.log"
            source.write_bytes(b"keep original\n")

            with self.assertRaises(ValueError):
                self.generator.generate(replace(self.request, inputs = (source,)))

            self.assertEqual(source.read_bytes(), b"keep original\n")

    def test_completed_publication_is_kept_when_recovering_cleanup(self):
        self.generator.generate(self.request)
        (self.root / "index.html").write_text(CurrentReport.LEGACY_ENTRY, encoding = "utf-8")
        before = self.snapshot()
        work = self.root / "build/tmp/report-generation"
        work.mkdir(parents = True)
        (work / "publication.json").write_text('{"report": true, "index": true}')
        (work / "published").touch()
        (work / "previous-report").mkdir()
        (work / "previous-report/partially-deleted").touch()

        with CurrentReport(self.output):
            self.assertTrue((self.output / "public/index.html").is_file())

        self.assertEqual(before, self.snapshot())

    def test_root_report_is_allowed_without_relaxing_archive_boundaries(self):
        with patch.object(Workspace, "project_root", return_value = self.root):
            self.assertEqual(Workspace.current_report_output(self.output), self.output)

            with self.assertRaises(ValueError):
                Workspace.local_output(self.output)

            with self.assertRaises(ValueError):
                Workspace.current_report_output(self.root / "another/report")

            self.generator.generate(self.request)

        self.assertTrue((self.root / "index.html").is_file())

    def test_concurrent_process_cannot_use_or_clean_active_workspace(self):
        with CurrentReport(self.output) as working:
            marker = working.root / "active"
            marker.write_text("keep")
            command = [sys.executable, "-B", "-c",
                       "from pathlib import Path; import sys; "
                       "from poe_log_analyze.runtime.ReportLock import ReportLock; "
                       "ReportLock(Path(sys.argv[1])).acquire()", str(working.lock.path)]
            completed = subprocess.run(command, capture_output = True, timeout = 10)

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("already generating a report", completed.stderr.decode())

            for attempt in range(2):
                with self.subTest(attempt = attempt), self.assertRaises(RuntimeError):
                    with CurrentReport(self.output):
                        self.fail("An active workspace must not be opened")

            self.assertEqual(marker.read_text(), "keep")

        self.assertFalse((self.root / "build").exists())

        with CurrentReport(self.output):
            self.assertFalse(marker.exists())

        self.assertFalse((self.root / "build").exists())

    def test_os_releases_lock_after_process_exit(self):
        folder = self.root / "build/tmp"
        folder.mkdir(parents = True)
        path = folder / "report-generation.lock"
        command = [sys.executable, "-B", "-c",
                   "from pathlib import Path; import os, sys; "
                   "from poe_log_analyze.runtime.ReportLock import ReportLock; "
                   "lock = ReportLock(Path(sys.argv[1])); lock.acquire(); os._exit(0)", str(path)]
        subprocess.run(command, check = True, timeout = 10)
        lock = ReportLock(path)
        lock.acquire()
        lock.release()

        self.assertFalse(path.exists())
