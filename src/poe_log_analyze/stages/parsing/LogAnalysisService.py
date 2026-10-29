import hashlib
import json
import os
import platform

from base64 import b64decode
from collections import Counter
from datetime import datetime, timezone

from pathlib import Path

from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

from poe_log_analyze import __version__

from poe_log_analyze.stages.parsing.LogParser import LogParser
from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.stages.parsing.DiagnosticSummary import DiagnosticSummary
from poe_log_analyze.stages.parsing.DiagnosticMarkdown import DiagnosticMarkdown

from poe_log_analyze.runtime.RuntimeResources import RuntimeResources
from poe_log_analyze.runtime.JsonFiles import JsonFiles
from poe_log_analyze.runtime.CodeProvenance import CodeProvenance

class LogAnalysisService:
    """Stream results, verify coverage, and write the run manifest."""

    @staticmethod
    def source_signature(stat: os.stat_result) -> tuple:
        """Fields for detecting source changes or replacement during reading."""

        return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns

    @staticmethod
    def _file_hash(path: Path, control: ExecutionContext) -> str:
        """Hash artifacts with cancellation checks between bounded reads."""

        digest = hashlib.sha256()

        with path.open("rb") as artifact:
            while True:
                control.check()
                block = artifact.read(1024 * 1024)

                if not block:
                    break

                digest.update(block)

        control.check()

        return digest.hexdigest()

    @staticmethod
    def analyze(input_path: Path, output_path: Path, timezone_name: str = "Asia/Almaty",
                require_complete: bool = False, *,
                control: ExecutionContext | None = None, source_label: str = "") -> dict:
        """Create a new result directory; never overwrite an existing one."""

        control = control or ExecutionContext()
        control.check()
        input_path = input_path.resolve(strict = True)
        output_path = output_path.resolve()

        if not input_path.is_file():
            raise ValueError('Input must be a regular file')

        if input_path.is_relative_to(output_path):
            raise ValueError('The result directory cannot contain the source file')

        if output_path.exists():
            raise FileExistsError('The result directory already exists; specify a new --output')

        RuntimeResources.configure_timezone()
        zone = ZoneInfo(timezone_name)
        started_at = datetime.now(timezone.utc).isoformat()
        package = Path(__file__).resolve().parents[2]
        build = RuntimeResources.build_metadata()
        code_hashes = build["code"]["files_sha256"] if build else CodeProvenance.source_hashes(package)
        git = build["code"]["git"] if build else CodeProvenance.git_state(package.parent.parent)
        output_path.parent.mkdir(parents = True, exist_ok = True)
        statuses, types, reasons = Counter(), Counter(), Counter()
        diagnostic_summary = DiagnosticSummary()
        digest = hashlib.sha256()
        offset = total = 0

        with TemporaryDirectory(prefix = ".analysis-", dir = output_path.parent) as temporary:
            target = Path(temporary) / "result"
            target.mkdir()

            with input_path.open("rb") as source, \
                    (target / "lines.jsonl").open("w", encoding = "utf-8", newline = "\n") as ledger, \
                    (target / "diagnostics.jsonl").open("w", encoding = "utf-8", newline = "\n") as diagnostics:
                before = LogAnalysisService.source_signature(os.fstat(source.fileno()))
                control.report('Parsing', total = before[2], force = True, unit = 'bytes')

                for record in LogParser.iter_records(source, zone):
                    control.check()
                    raw = b64decode(record["raw_base64"], validate = True)
                    total += 1

                    if (record["line_number"] != total or record["byte_start"] != offset
                            or record["byte_end"] != offset + len(raw) or not raw):
                        raise ValueError('Invalid line or byte-range coverage')

                    offset += len(raw)
                    digest.update(raw)
                    statuses[record["status"]] += 1
                    types[record["type"]] += 1
                    encoded = json.dumps(record, ensure_ascii = False, sort_keys = True) + "\n"
                    ledger.write(encoded)

                    if record["status"] != "recognized":
                        diagnostics.write(encoded)
                        reasons[record["reason"]] += 1
                        diagnostic_summary.add(record)

                    control.report('Parsing', offset, before[2], total, unit = 'bytes')

                # Windows stat and fstat expose different ctime semantics; compare handles.
                with input_path.open("rb") as current:
                    if (before != LogAnalysisService.source_signature(os.fstat(source.fileno()))
                            or before != LogAnalysisService.source_signature(os.fstat(current.fileno()))):
                        raise ValueError('The source file changed during analysis; the result was not saved')

            if offset != before[2] or total != sum(statuses.values()):
                raise ValueError('Not all input bytes or lines were accounted for')

            complete = statuses["unknown"] == statuses["error"] == 0
            coverage = {
                "schema_version": LogParser.SCHEMA_VERSION, "rules_version": RuleCatalogue.RULES_VERSION,
                "input_sha256": digest.hexdigest(), "input_bytes": before[2],
                "accounted_bytes": offset, "total_lines": total,
                "recognized_lines": statuses["recognized"], "unknown_lines": statuses["unknown"],
                "error_lines": statuses["error"], "accounting_complete": True,
                "recognition_complete": complete,
                "recognized_fraction": statuses["recognized"] / total if total else None,
                "types": dict(sorted(types.items())), "diagnostic_reasons": dict(sorted(reasons.items())),
            }
            JsonFiles.write_json(target / "coverage.json", coverage)
            summary = diagnostic_summary.result(digest.hexdigest(), RuleCatalogue.RULES_VERSION)

            if summary["total_lines"] != statuses["unknown"] + statuses["error"]:
                raise ValueError('The review queue does not match the problematic line count')

            JsonFiles.write_json(target / "diagnostic_summary.json", summary)
            (target / "diagnostic_summary.md").write_text(DiagnosticMarkdown.summary_markdown(summary), encoding = "utf-8", newline = "\n")
            manifest = {
                "schema_version": LogParser.SCHEMA_VERSION, "rules_version": RuleCatalogue.RULES_VERSION,
                "tool_version": __version__, "started_at_utc": started_at,
                "input": {"path": str(input_path), "sha256": digest.hexdigest(),
                          "bytes": before[2], "lines": total},
                "environment": {"python": platform.python_version(),
                                "implementation": platform.python_implementation(),
                                "dependencies": [], "timezone": CodeProvenance.timezone_metadata(timezone_name)},
                "code": {"git": git, "files_sha256": code_hashes},
                "parameters": {"timezone": timezone_name, "require_complete": require_complete,
                               "output": str(output_path),
                               "source_label": source_label or input_path.name},
                "artifacts_sha256": {},
            }
            state = "Распознавание завершено" if complete else "Распознавание не завершено"
            percentage = f"{coverage['recognized_fraction']:.2%}" if total else "не применимо (пустой файл)"
            report = (
                f"# Отчёт о покрытии\n\n**{state}.**\n\n"
                f"- SHA-256 входа: `{digest.hexdigest()}`.\n"
                f"- Часовой пояс: `{timezone_name}`.\n"
                f"- Учтено bytesов: {offset} of {before[2]}.\n"
                f"- Lines accounted for: {total}.\n"
                f"- Распознано: {statuses['recognized']} ({percentage}).\n"
                f"- Неизвестных: {statuses['unknown']}.\n"
                f"- Ошибок: {statuses['error']}.\n\n"
                "Учёт строк полный. Распознанный заголовок не означает распознанное сообщение.\n"
                "Пустой файл удовлетворяет проверке покрытия, но не содержит игровых событий.\n\n"
                "Остаток сохранён без потерь. Группы и порядок ручного разбора: [очередь диагностики](diagnostic_summary.md).\n\n"
                "## Типы строк\n\n| Тип | Строк |\n| --- | ---: |\n"
                + "".join(f"| `{kind}` | {count} |\n" for kind, count in sorted(types.items()))
            )
            (target / "coverage.md").write_text(report, encoding = "utf-8", newline = "\n")

            for path in sorted(target.iterdir()):
                control.report('Save reports', force = True)

                manifest["artifacts_sha256"][path.name] = LogAnalysisService._file_hash(path, control)

            JsonFiles.write_json(target / "manifest.json", manifest)
            control.check()
            target.rename(output_path)

        return coverage
