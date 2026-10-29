"""Escaping, trusted Markdown, and strict template errors."""

import unittest

from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import Mock

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.stages.rendering.HtmlPageWriter import HtmlPageWriter


class HtmlPageWriterTests(unittest.TestCase):
    """User text must not become markup or template code."""

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / "report/project"
        (self.project / "layouts").mkdir(parents = True)
        (self.root / "explanation.md").write_text("# Объяснение\n\n**Жирный текст**", encoding = "utf-8")
        self.catalogue = Mock()
        self.catalogue.source.return_value = "explanation.md"
        self.writer = HtmlPageWriter(self.root, self.project, "ru", {}, self.catalogue, ExecutionContext())

    def test_user_text_is_escaped_once_and_markdown_is_rendered(self):
        (self.project / "layouts/index.html").write_text(
            '<p title="{{ ctx.title }}">{{ ctx.title }}</p>{{ ctx.content }}', encoding = "utf-8")
        value = '<script>"& {{ 7 * 7 }}</script>'
        self.writer.write("index.html", "explanation.md", title = value)
        html = (self.root / "report/public/index.html").read_text(encoding = "utf-8")

        self.assertIn("&lt;script&gt;&#34;&amp; {{ 7 * 7 }}&lt;/script&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertNotIn("&amp;lt;", html)
        self.assertIn("<strong>Жирный текст</strong>", html)

    def test_missing_value_and_template_are_errors(self):
        with self.assertRaisesRegex(ValueError, "HTML"):
            self.writer.write("index.html", "explanation.md")

        (self.project / "layouts/index.html").write_text('{{ data.missing }}', encoding = "utf-8")

        with self.assertRaisesRegex(ValueError, "HTML"):
            self.writer.write("index.html", "explanation.md")

    def test_page_cannot_escape_public_directory(self):
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.writer.write("../../outside/index.html", "explanation.md")

        self.assertFalse((self.root / "outside/index.html").exists())
