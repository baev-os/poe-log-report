"""Validated local translations for one export."""

import hashlib
import json
import re

from dataclasses import asdict

from pathlib import Path

from string import Formatter

from poe_log_analyze.core.request.ReportLanguage import ReportLanguage

from poe_log_analyze.stages.parsing.DiagnosticSummary import DiagnosticSummary
from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue
from poe_log_analyze.stages.composition.specification.SpecificationBuilder import SpecificationBuilder


class TranslationCatalogue:
    """Missing service-label translations stop export before HTML is written."""

    VERSION = "1"
    PAGES = ("coverage", "history", "log-specification", "map-flow", "map-statistics",
             "map-statistics-day", "maps", "maps-day", "timeline", "timeline-day")

    def __init__(self, language: str, resources: Path):
        self.language = ReportLanguage(language).code
        self.resources = resources
        paths = [resources / f"reports/locales/{name}.json" for name in ("ru", "en", "rules.en", "rules.ru")]
        blobs = [path.read_bytes() for path in paths]
        ru, en, english_rules, russian_rules = [json.loads(blob) for blob in blobs]

        if any(item["version"] != self.VERSION for item in (ru, en, english_rules, russian_rules)):
            raise ValueError('Unsupported translation catalogue version')

        self.ru, self.messages = ru["messages"], (ru if language == "ru" else en)["messages"]

        if self.ru.keys() != en["messages"].keys():
            raise ValueError('The ru/en key sets do not match')

        for key, value in self.ru.items():
            other = en["messages"][key]

            if not isinstance(value, str) or not value.strip() or not isinstance(other, str) or not other.strip():
                raise ValueError(f"Missing translation: {key}")

            if self.parameters(value) != self.parameters(other):
                raise ValueError(f"Translation parameters do not match: {key}")

        self.legacy_keys = {value: key for messages in (en["messages"], self.ru) for key, value in messages.items()}
        self.spec = asdict(SpecificationBuilder.build_specification((resources / "docs/rules.md").read_text(encoding = "utf-8")))
        self.rules = russian_rules if language == "ru" else english_rules
        rules = self.rules
        self.descriptions = {rule["rule_id"]: rule["description"] for family in self.spec["families"] for rule in family["rules"]}

        if set(rules["descriptions"]) != set(self.descriptions) or set(rules["families"]) != set(RuleCatalogue.RULE_GROUPS):
            raise ValueError('Specification translations do not match the rule catalogue')

        if any(not value.strip() for value in rules["descriptions"].values()):
            raise ValueError('Empty rule description')

        for family in rules["families"].values():
            if not family["section"].strip() or not family["description"].strip():
                raise ValueError('Empty rule-family description')

        for _, pattern in RuleCatalogue.MESSAGE_RULES:
            for field in pattern.groupindex:
                self.text("field." + field)

        for patterns in RuleCatalogue.CONTINUATIONS.values():
            for pattern in patterns:
                for field in pattern.groupindex:
                    self.text("field." + field)

        for page in self.PAGES:
            for folder in ("reports", "reports/ru"):
                if not (resources / folder / (page + ".md")).is_file():
                    raise ValueError(f"Missing report text: {folder}/{page}.md")

        for template in (resources / "site/layouts").rglob("*.html"):
            for key in re.findall(r'\btranslate\("([^"]+)"\)', template.read_text(encoding = "utf-8")):
                self.text(key)

        self.hashes = {path.relative_to(resources).as_posix(): hashlib.sha256(blob).hexdigest()
                       for path, blob in zip(paths, blobs)}

        for page in self.PAGES:
            path = resources / self.source(f"reports/{page}.md")
            self.hashes[path.relative_to(resources).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def parameters(value: str) -> set[str]:
        return {field for _, field, _, _ in Formatter().parse(value) if field is not None}

    def text(self, key: str, **parameters) -> str:
        if key not in self.messages:
            raise ValueError(f"Missing translation: {key}")

        value = self.messages[key]

        return value.format(**parameters) if parameters else value

    def diagnostic_reason(self, reason: str) -> str:
        for prefix, key in (('UTF-8 error in line bytes ', 'diagnostics.encoding_reason'),
                            ('Invalid timestamp: ', 'diagnostics.timestamp_reason'),
                            ('Ошибка UTF-8 в байтах строки ', 'diagnostics.encoding_reason'),
                            ('Некорректная временная отметка: ', 'diagnostics.timestamp_reason')):
            if reason.startswith(prefix):
                return self.text(key, detail = reason[len(prefix):])

        return self.legacy_label(reason)

    def legacy_label(self, value: str) -> str:
        """Compatibility for known labels only; never apply to user text."""

        key = self.legacy_keys.get(value)

        if key:
            return self.text(key)

        if re.search("[А-Яа-яЁё]", value):
            raise ValueError(f"Missing service-label translation: {value}")

        return value

    def source(self, name: str) -> str:
        return name.replace("reports/", "reports/ru/", 1) if self.language == "ru" else name

    def rule_title(self, code: str) -> str:
        descriptions = self.rules["descriptions"]

        if code in descriptions:
            return descriptions[code]

        if "event_title." + code in self.messages:
            return self.text("event_title." + code)

        return code

    def specification(self) -> dict:
        """Localize explanations while preserving patterns, fields, codes, and priorities."""

        spec = self.spec
        spec["version"] = "4"
        spec["report_language"] = self.language

        for family in spec["families"]:
            family.update(self.rules["families"][family["code"]])

            for rule in family["rules"]:
                rule["description"] = self.rule_title(rule["rule_id"])

        for rule in spec["framing"]:
            rule["description"] = self.text("framing." + rule["rule_id"])

        for rule in spec["continuations"]:
            rule["description"] = self.text("spec.continuation", parent = rule["parent"], field = rule["fields"][0])

        for catalogue in spec["catalogues"]:
            catalogue["label"] = self.text("catalogue." + catalogue["code"])

            if catalogue["code"] == "DIAGNOSTIC_CATEGORIES":
                catalogue["values"] = [code + " — " + self.text("diagnostic." + code) for code in DiagnosticSummary.CATEGORIES]
            elif catalogue["code"] == "EVENT_GROUPS":
                catalogue["values"] = [f"{code} — {self.text('group.' + code + '.label')}; prefixes={value['prefixes']!r}; "
                                       f"types={value['types']!r}. {self.text('group.' + code + '.note')}"
                                       for code, value in RuleCatalogue.EVENT_GROUPS.items()]

        spec['groups'] = SpecificationBuilder.group_rules(spec)

        return spec
