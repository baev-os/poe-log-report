import logging

from pathlib import Path
from tempfile import TemporaryDirectory
from types import TracebackType
from typing import Self

from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.result.ReportResult import ReportResult
from poe_log_analyze.core.result.AnalysisSummary import AnalysisSummary
from poe_log_analyze.core.CurrentReport import CurrentReport


class ReportWorkspace:
    """Temporary analysis; archive results or replace the current report."""

    def __init__(self, output: Path, mode: ReportMode, replace_report: bool = False) -> None:
        self.output = output
        self.mode = mode
        self._temporary: TemporaryDirectory[str] | None = None
        self._published = False
        self._current = CurrentReport(output) if replace_report else None

    def __enter__(self) -> Self:
        if self._current is not None:
            self._current.__enter__()
            return self

        self.output.parent.mkdir(parents = True, exist_ok = True)
        self._temporary = TemporaryDirectory(prefix = ".pipeline-", dir = self.output.parent)

        return self

    @property
    def root(self) -> Path:
        if self._current is not None and not self._published:
            return self._current.root

        if self._temporary is None or self._published:
            raise RuntimeError('The workspace is unavailable')

        return Path(self._temporary.name)

    @property
    def target(self) -> Path:
        return self.root / "result"

    @property
    def analysis_directory(self) -> Path:
        return self.target / "analysis" if self.mode == ReportMode.FULL else self.target

    @property
    def report_directory(self) -> Path:
        return self.target / "report" if self.mode == ReportMode.FULL else self.target

    def publish(self, report: Path | None, summary: AnalysisSummary | None) -> ReportResult:
        target = self.target

        if self.mode != ReportMode.EXPORT and not self.analysis_directory.is_dir():
            raise ValueError('No analysis exists for the current run')

        relative_report = None

        if self.mode != ReportMode.ANALYSIS:
            if report is None or not report.is_file() or not report.resolve().is_relative_to(self.report_directory.resolve()):
                raise ValueError("HTML must be inside the current run's report")

            relative_report = report.relative_to(target)

        if self._current is not None:
            self._current.publish(self.report_directory)
            self._published = True

            return ReportResult(self.output, self.output / "public/index.html", summary)

        if self.output.exists() or self.output.is_symlink():
            raise FileExistsError('The result directory already exists')

        directory = self.output / "analysis" if self.mode == ReportMode.FULL else self.output
        result = ReportResult(directory, self.output / relative_report if relative_report else None, summary)
        target.rename(self.output)
        self._published = True

        return result

    def __exit__(self, exc_type: type[BaseException] | None,
                 exc: BaseException | None, traceback: TracebackType | None) -> None:

        if self._current is not None:
            self._current.__exit__(exc_type, exc, traceback)
            return

        if self._temporary is not None:
            try:
                self._temporary.cleanup()
            except OSError:
                if not self._published:
                    raise

                logging.getLogger(__name__).exception('The result was saved but the temporary workspace was not removed')
            finally:
                self._temporary = None
