"""Two languages from one analysis: equal data, original text, and complete offline export."""

import hashlib
import json
import re
import shutil
import unittest

from dataclasses import FrozenInstanceError

from pathlib import Path

from tempfile import TemporaryDirectory
from unittest.mock import Mock

from poe_log_analyze.cli.ReportCli import ReportCli

from poe_log_analyze.stages.parsing.CollectionAnalysisService import CollectionAnalysisService

from poe_log_analyze.core.request.ReportRequest import ReportRequest
from poe_log_analyze.core.request.ReportLanguage import ReportLanguage
from poe_log_analyze.core.result.ReportResult import ReportResult

from poe_log_analyze.runtime.AreaKind import AreaKind
from poe_log_analyze.runtime.RuntimeResources import RuntimeResources

from ReportFixture import ReportFixture

from poe_log_analyze.stages.composition.localization.EventMessagePresenter import EventMessagePresenter
from poe_log_analyze.stages.composition.localization.TranslationCatalogue import TranslationCatalogue

from CollectionFixture import CollectionFixture


class LocalizationTests(unittest.TestCase):
    """Localized presentation does not change recognition or measured intervals."""

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_language_is_validated_and_command_is_immutable(self):
        with self.assertRaisesRegex(ValueError, "en or ru"):
            ReportRequest((self.root / "synthetic.txt",), self.root, report_language = "de")

        command = ReportRequest((self.root / "synthetic.txt",), self.root, report_language = "en")

        with self.assertRaises(FrozenInstanceError):
            command.report_language = "ru"

        with self.assertRaisesRegex(ValueError, "en or ru"):
            ReportFixture.export_report(self.root, self.root / "output", report_language = "../../en")

        self.assertFalse((self.root / "output").exists())

    def test_english_is_default_and_russian_remains_explicitly_selectable(self):
        handler = Mock()
        handler.generate.return_value = ReportResult(self.root, None, None)

        status = ReportCli(handler).run(['--result', str(self.root), '--output', str(self.root / 'report')])
        request = handler.generate.call_args.args[0]

        self.assertEqual(status, 0)
        self.assertEqual(request.report_language, 'en')
        self.assertEqual(ReportLanguage().code, 'en')
        self.assertEqual(ReportRequest((self.root,), self.root).report_language, 'en')

        ReportCli(handler).run(['--result', str(self.root), '--output', str(self.root / 'report'),
                                '--report-language', 'ru'])

        self.assertEqual(handler.generate.call_args.args[0].report_language, 'ru')

    def test_report_pages_and_rule_descriptions_use_the_selected_language(self):
        root = RuntimeResources.resource_root()
        english = TranslationCatalogue('en', root)
        russian = TranslationCatalogue('ru', root)

        self.assertEqual(english.source('reports/maps.md'), 'reports/maps.md')
        self.assertEqual(russian.source('reports/maps.md'), 'reports/ru/maps.md')
        self.assertFalse(re.search('[А-Яа-яЁё]', (root / english.source('reports/maps.md')).read_text()))
        self.assertTrue(re.search('[А-Яа-яЁё]', (root / russian.source('reports/maps.md')).read_text()))
        self.assertFalse(re.search('[А-Яа-яЁё]', english.rule_title('area.enter')))
        self.assertTrue(re.search('[А-Яа-яЁё]', russian.rule_title('area.enter')))

    def test_all_rules_fields_and_templates_have_both_languages(self):
        root = RuntimeResources.resource_root()
        ru = TranslationCatalogue("ru", root).specification()
        en = TranslationCatalogue("en", root).specification()

        self.assertEqual(ru["rule_count"], 296)

        for left, right in zip(ru["families"], en["families"]):
            self.assertEqual(left["code"], right["code"])
            self.assertFalse(re.search("[А-Яа-яЁё]", right["description"]))

            for a, b in zip(left["rules"], right["rules"]):
                self.assertTrue(b["description"])
                self.assertEqual({k: v for k, v in a.items() if k != "description"},
                                 {k: v for k, v in b.items() if k != "description"})

        self.assertEqual(AreaKind.code({"kind": "Карта"}), "map")
        self.assertEqual(AreaKind.code({"kind": "any display label", "kind_code": "map"}), "map")

    def test_missing_translation_fails_without_russian_fallback(self):
        root = RuntimeResources.resource_root()
        shutil.copytree(root / "reports", self.root / "reports")
        path = self.root / "reports/locales/en.json"
        data = json.loads(path.read_text(encoding = "utf-8"))
        del data["messages"]["page.maps"]
        path.write_text(json.dumps(data), encoding = "utf-8")

        with self.assertRaisesRegex(ValueError, "ru/en key sets"):
            TranslationCatalogue("en", self.root)

    def test_known_message_translation_keeps_fields_and_original(self):
        message = {"code": "area.enter", "recognized": True, "fields": {"area": "<Dunes>"},
                   "original": ": You have entered <Dunes>."}
        ru = EventMessagePresenter(TranslationCatalogue("ru", RuntimeResources.resource_root())).present(message)
        en = EventMessagePresenter(TranslationCatalogue("en", RuntimeResources.resource_root())).present(message)

        self.assertEqual(ru["text"], "Вход в область: <Dunes>")
        self.assertEqual(ru["original"], message["original"])
        self.assertEqual(en["text"], message["original"])
        self.assertEqual(ru["parameters"][0]["value"], "<Dunes>")

        for language in ("ru", "en"):
            presenter = EventMessagePresenter(TranslationCatalogue(language, RuntimeResources.resource_root()))

            for code, recognized in (("chat.whisper", True), ("message.unknown", False)):
                unknown = {"code": code, "recognized": recognized, "fields": {}, "original": "Точный текст <script>"}

                self.assertEqual(presenter.present(unknown)["text"], unknown["original"])

    def test_same_saved_analysis_in_both_languages_preserves_metrics_and_raw(self):
        log = self.root / "Client с пробелами.log"
        messages = [(0, 'Generating level 83 area "MapWorldsDunes" with seed 123'),
                    (1, ': You have entered Dunes.'), (2, '@From TestPlayer: hello <script>bad</script>'),
                    (3, '@To TestPlayer: reply'), (4, ': Trade accepted.'),
                    (5, 'Generating level 83 area "MapWorldsMemoryVault1" with seed 124'),
                    (6, ": You have entered Machinist's Vault."), (7, 'Unhandled exception: synthetic fault')]
        original = ''.join(CollectionFixture.line(t, text) for t, text in messages).replace('\n', '\r\n').encode()
        log.write_bytes(original)
        analysis = self.root / "analysis"

        CollectionAnalysisService.analyze_collection([log, log], analysis)
        before = {p.relative_to(analysis): hashlib.sha256(p.read_bytes()).hexdigest() for p in analysis.rglob('*') if p.is_file()}
        log.unlink()

        for language in ("ru", "en"):
            ReportFixture.export_report(analysis, self.root / language, report_language = language)

        self.assertEqual(before, {p.relative_to(analysis): hashlib.sha256(p.read_bytes()).hexdigest() for p in analysis.rglob('*') if p.is_file()})

        for name in ("analysis", "maps", "map_statistics", "map_flow", "timeline", "daily_playtime", "activity", "statistics_summary"):
            ru, en = [json.loads((self.root / lang / f"project/data/{name}.json").read_text(encoding = "utf-8")) for lang in ("ru", "en")]

            self.assertEqual(self.measured_values(ru), self.measured_values(en), name)

        ru, en = [json.loads((self.root / lang / "project/data/maps.json").read_text(encoding = "utf-8")) for lang in ("ru", "en")]

        self.assertEqual(ru["seconds"], 4)
        self.assertEqual(en["map_count"], 1)
        self.assertEqual(en["by_date"]["2026-09-01"]["runs"][0]["kind"], "Map")

        for path in (self.root / "en/public").rglob("*.html"):
            html = path.read_text(encoding = "utf-8")

            self.assertIn('lang="en"', html)
            self.assertFalse(re.search("[А-Яа-яЁё]", html), str(path))

        chat = (self.root / "en/public/conversations/index.html").read_text(encoding = "utf-8")

        self.assertIn("hello &lt;script&gt;bad&lt;/script&gt;", chat)
        self.assertNotIn("<script>bad", chat)

        events = (self.root / "en/public/events/index.html").read_text(encoding = "utf-8")

        self.assertIn(": You have entered Dunes.", events)
        self.assertIn(": Trade accepted.", events)
        self.assertIn("September", (self.root / "en/public/maps/index.html").read_text(encoding = "utf-8"))

        manifest = json.loads((self.root / "en/report-manifest.json").read_text(encoding = "utf-8"))

        self.assertEqual(manifest["report_language"], "en")
        self.assertTrue(manifest["translations_sha256"])

        ReportFixture.export_report(analysis, self.root / "en-repeat", report_language = "en")

        for path in (self.root / "en/public").rglob('*'):
            if path.is_file():
                self.assertEqual(path.read_bytes(), (self.root / "en-repeat/public" / path.relative_to(self.root / "en/public")).read_bytes())

    @staticmethod
    def measured_values(value):
        if isinstance(value, dict):
            return {k: LocalizationTests.measured_values(v) for k, v in value.items()
                    if k != 'presentation' and (not isinstance(v, str) or k.endswith('_at') or k in ('date', 'timestamp', 'utc', 'input_sha256'))}

        if isinstance(value, list):
            return [LocalizationTests.measured_values(v) for v in value]

        return value
