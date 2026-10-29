import hashlib
import json

from pathlib import Path

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.stages.parsing.DiagnosticSummary import DiagnosticSummary

class AnalysisValidator:
    """Validate saved-analysis integrity before export."""

    @staticmethod
    def file_hash(path: Path, control: ExecutionContext) -> str:
        """Compute a hash with cancellation checks for large registries."""

        digest = hashlib.sha256()

        with path.open("rb") as source:
            while block := source.read(1024 * 1024):
                control.check()
                digest.update(block)

        return digest.hexdigest()

    @staticmethod
    def report_data(directory: Path, control: ExecutionContext) -> tuple[dict, dict]:
        """Verify hashes and aggregate-source links; select fields for HTML."""

        manifest = json.loads((directory / "manifest.json").read_text(encoding = "utf-8"))

        for name in ("coverage.json", "lines.jsonl"):
            if AnalysisValidator.file_hash(directory / name, control) != manifest["artifacts_sha256"][name]:
                raise ValueError(f"Hash of {name} does not match the manifest")

        coverage = json.loads((directory / "coverage.json").read_text(encoding = "utf-8"))

        if manifest["schema_version"] != "1" or coverage["schema_version"] != "1":
            raise ValueError('Unsupported result schema version')

        counts = [coverage[key] for key in ("total_lines", "recognized_lines", "unknown_lines", "error_lines", "input_bytes", "accounted_bytes")]

        if any(type(value) is not int or value < 0 for value in counts):
            raise ValueError('Invalid coverage report counts')

        total, recognized, unknown, errors, size, accounted = counts
        complete = unknown == errors == 0
        types = coverage["types"]

        if (coverage["input_sha256"] != manifest["input"]["sha256"]
                or total != manifest["input"]["lines"] or size != manifest["input"]["bytes"]
                or coverage["rules_version"] != manifest["rules_version"]
                or size != accounted or total != recognized + unknown + errors
                or coverage["accounting_complete"] is not True
                or coverage["recognition_complete"] is not complete
                or any(type(n) is not int or n < 0 for n in types.values())
                or sum(types.values()) != total):
            raise ValueError('Coverage metrics disagree with the manifest')

        data = {key: coverage[key] for key in (
            "total_lines", "recognized_lines", "unknown_lines", "error_lines", "input_sha256",
            "input_bytes", "rules_version", "schema_version", "recognition_complete",
        )}
        data.update({
            "source_label": manifest["parameters"].get("source_label") or Path(manifest["input"]["path"]).name,
            "timezone": manifest["parameters"]["timezone"],
            "state": "Распознавание завершено" if complete else "Распознавание не завершено",
            "percentage": f"{recognized / total:.2%}" if total else "Не применимо: пустой файл; 0",
            "types": [{"type": key, "count": count} for key, count in sorted(types.items())],
            "diagnostic_categories": [],
        })
        # Legacy results without a summary remain exportable.
        name = "diagnostic_summary.json"

        if name in manifest["artifacts_sha256"]:
            if AnalysisValidator.file_hash(directory / name, control) != manifest["artifacts_sha256"][name]:
                raise ValueError('Diagnostic summary hash does not match the manifest')

            summary = json.loads((directory / name).read_text(encoding = "utf-8"))
            categories = summary["categories"]

            if (summary["diagnostics_version"] != DiagnosticSummary.DIAGNOSTICS_VERSION
                    or summary["input_sha256"] != coverage["input_sha256"]
                    or summary["rules_version"] != coverage["rules_version"]
                    or summary["total_lines"] != unknown + errors
                    or not set(categories) <= DiagnosticSummary.CATEGORIES.keys()
                    or any(type(n) is not int or n < 0 for n in categories.values())
                    or sum(categories.values()) != unknown + errors):
                raise ValueError('Diagnostic summary disagrees with coverage')

            # Only static category labels and numbers; do not export examples or reasons.
            data["diagnostic_categories"] = [
                {"category": DiagnosticSummary.CATEGORIES[key], "count": count}
                for key, count in sorted(categories.items())
            ]

        return data, manifest
