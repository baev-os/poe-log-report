import hashlib
import json

from collections import Counter

from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue

class DiagnosticSummary:
    """Count exact repeats; keep bounded samples and the complete remainder in JSONL."""

    DIAGNOSTICS_VERSION = "1"

    CATEGORIES = {
        "encoding": "Ошибка UTF-8",
        "timestamp": "Некорректная временная отметка",
        "control": "Неизвестный текст с управляющими символами",
        "message": "Неизвестное сообщение с заголовком",
        "unframed": "Строка без распознанного заголовка или продолжения",
        "other_error": "Другая ошибка разбора",
    }


    def __init__(self):
        self.groups = {}
        self.categories = Counter()

    def add(self, record: dict) -> None:
        """Account for each problematic line once without guessing its gameplay meaning."""

        if record["status"] == "recognized":
            return

        text = record.get("text")
        header = RuleCatalogue.HEADER.fullmatch(text) if text is not None else None
        payload = header["message"] if header else text

        if record["type"] == "encoding.error":
            category = "encoding"
        elif record["type"] == "timestamp.error":
            category = "timestamp"
        elif record["status"] == "error":
            category = "other_error"
        elif any(ord(char) < 32 or ord(char) == 127 for char in payload):
            category = "control"
        else:
            category = "message" if header else "unframed"

        # The key excludes the header; content is neither normalized nor truncated.
        identity = [category, record["status"], record["type"], record["reason"],
                    payload if payload is not None else record["raw_base64"]]
        key = hashlib.sha256(json.dumps(identity, ensure_ascii = False).encode()).hexdigest()
        number = record["line_number"]

        if key not in self.groups:
            self.groups[key] = {
                "group_id": key, "category": category, "status": record["status"],
                "reason": record["reason"], "count": 0, "first_line": number,
                "last_line": number, "sample_lines": [],
                "example_text": payload[:512] if payload is not None else None,
                "example_truncated": payload is not None and len(payload) > 512,
            }

        group = self.groups[key]
        group["count"] += 1
        group["last_line"] = number

        if len(group["sample_lines"]) < 10:
            group["sample_lines"].append(number)

        self.categories[category] += 1

    def result(self, input_sha256: str, rules_version: str) -> dict:
        """Return a deterministic queue with frequent repeats first."""

        return {
            "diagnostics_version": DiagnosticSummary.DIAGNOSTICS_VERSION,
            "input_sha256": input_sha256, "rules_version": rules_version,
            "total_lines": sum(self.categories.values()),
            "categories": dict(sorted(self.categories.items())),
            "groups": sorted(self.groups.values(), key = lambda g: (-g["count"], g["group_id"])),
        }
