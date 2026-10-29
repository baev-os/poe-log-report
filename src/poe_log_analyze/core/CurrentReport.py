"""Replace the current report and recover from interrupted saves."""

import json
import filecmp
import shutil

from pathlib import Path

from types import TracebackType
from typing import Self

from poe_log_analyze.runtime.ReportLock import ReportLock
from poe_log_analyze.runtime.Workspace import Workspace


class CurrentReport:
    """Remove temporary analysis; keep the previous report until replacement completes."""

    ENTRY = ('<!doctype html>\n<!-- poe-log-analyze:report-entry -->\n'
             '<html lang="en"><head><meta charset="utf-8">'
             '<meta http-equiv="refresh" content="0; url=report/public/index.html">'
             '<title>Report</title></head><body>'
             '<a href="report/public/index.html">Open report</a>'
             '</body></html>\n')

    LEGACY_ENTRY = ('<!doctype html>\n<!-- poe-log-analyze:report-entry -->\n'
             '<html lang="ru"><head><meta charset="utf-8">'
             '<meta http-equiv="refresh" content="0; url=report/public/index.html">'
             '<title>Отчёт / Report</title></head><body>'
             '<a href="report/public/index.html">Открыть отчёт / Open report</a>'
             '</body></html>\n')

    def __init__(self, output: Path) -> None:
        self.output = output
        self.entry = output.parent / "index.html"
        self.pdf = output.parent / "report.pdf"
        self.root = output.parent / "build/tmp/report-generation"
        self.lock = ReportLock(self.root.with_suffix(".lock"))
        self._preserve = False

    def __enter__(self) -> Self:
        Workspace.current_report_output(self.output)
        Workspace.local_output(self.root)

        if self.root.is_symlink():
            raise ValueError('The temporary workspace must not be a symbolic link')

        self.root.parent.mkdir(parents = True, exist_ok = True)
        self.lock.acquire()

        try:
            self._recover()

            if self.root.exists():
                shutil.rmtree(self.root)

            self._validate_destination()
            self.root.mkdir()
        except BaseException:
            self.lock.release()
            self._remove_empty_parents()
            raise

        return self

    def _validate_destination(self) -> None:
        Workspace.current_report_output(self.output)

        if self.output.exists() and (not self.output.is_dir()
                                    or not (self.output / "report-manifest.json").is_file()
                                    or not (self.output / "public/index.html").is_file()):
            raise ValueError('report contains unrelated data; automatic replacement is unavailable')

        if self.entry.exists() and (not self.entry.is_file()
                                    or self.entry.read_text(encoding = "utf-8") not in (self.ENTRY, self.LEGACY_ENTRY)):
            raise ValueError('index.html contains unrelated data; automatic replacement is unavailable')

        if self.pdf.is_symlink():
            raise ValueError('report.pdf must not be a symbolic link')

        if self.pdf.exists():
            original = self.output / "public/report.pdf"

            if (not self.pdf.is_file() or not original.is_file() or original.is_symlink()
                    or not filecmp.cmp(self.pdf, original, shallow = False)):
                raise ValueError('report.pdf contains unrelated data; automatic replacement is unavailable')

    def publish(self, report: Path) -> None:
        self._validate_destination()
        journal = {"report": self.output.exists(), "index": self.entry.exists(), "pdf": self.pdf.exists()}
        (self.root / "index.html").write_text(self.ENTRY, encoding = "utf-8", newline = "\n")
        new_pdf = report / "public/report.pdf"

        if new_pdf.is_file():
            shutil.copyfile(new_pdf, self.root / "report.pdf")

        if journal["pdf"]:
            shutil.copyfile(self.pdf, self.root / "previous-report.pdf")

        if journal["index"]:
            shutil.copyfile(self.entry, self.root / "previous-index.html")

        (self.root / "publication.pending").write_text(json.dumps(journal), encoding = "utf-8")
        (self.root / "publication.pending").replace(self.root / "publication.json")

        try:
            if journal["report"]:
                self.output.rename(self.root / "previous-report")

            report.rename(self.output)
            (self.root / "index.html").replace(self.entry)

            if (self.root / "report.pdf").is_file():
                (self.root / "report.pdf").replace(self.pdf)
            else:
                self.pdf.unlink(missing_ok = True)

            (self.root / "published").touch()
        except BaseException:
            try:
                self._recover()
            except BaseException:
                self._preserve = True
                raise

            raise

    def _recover(self) -> None:
        journal = self.root / "publication.json"

        if (self.root / "published").exists():
            journal.unlink(missing_ok = True)
            return

        if not journal.is_file():
            return

        previous = json.loads(journal.read_text(encoding = "utf-8"))
        backup = self.root / "previous-report"

        if backup.exists() or not previous["report"]:
            if self.output.is_symlink():
                raise ValueError('Cannot restore a report through a symbolic link')

            if self.output.exists():
                shutil.rmtree(self.output)

            if backup.exists():
                backup.rename(self.output)

        if previous["index"]:
            backup_index = self.root / "previous-index.html"

            if backup_index.exists():
                backup_index.replace(self.entry)
        else:
            self.entry.unlink(missing_ok = True)

        # Legacy journals described HTML only and did not affect the root PDF.
        if "pdf" in previous:
            if self.pdf.is_symlink():
                raise ValueError('Cannot restore a PDF through a symbolic link')

            if previous["pdf"]:
                backup_pdf = self.root / "previous-report.pdf"

                if backup_pdf.exists():
                    backup_pdf.replace(self.pdf)
            else:
                self.pdf.unlink(missing_ok = True)

        journal.unlink()

    def _remove_empty_parents(self) -> None:
        for path in (self.root.parent, self.root.parent.parent):
            try:
                path.rmdir()
            except OSError:
                pass

    def __exit__(self, exc_type: type[BaseException] | None,
                 exc: BaseException | None, traceback: TracebackType | None) -> None:

        try:
            if not self._preserve:
                self._recover()
                shutil.rmtree(self.root)
        finally:
            self.lock.release()
            self._remove_empty_parents()
