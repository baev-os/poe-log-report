import unittest

from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import patch

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.stages.rendering.RenderReport import RenderReport
from poe_log_analyze.stages.verification.LocalHTML import LocalHTML
from poe_log_analyze.stages.verification.LocalResources import LocalResources


class LocalHTMLTests(unittest.TestCase):
    """Check local links, prohibited content, and anchors throughout the report."""

    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.root = self.directory / 'public'
        self.root.mkdir()
        (self.root / 'index.html').touch()
        (self.root / 'ReportInteractions.js').touch()
        (self.root / 'style.css').touch()
        (self.root / 'nested').mkdir()
        (self.root / 'nested/index.html').touch()
        (self.root / 'nested/файл с пробелом.html').touch()
        (self.directory / 'outside.html').touch()

    def test_relative_paths_queries_encoded_names_and_fragments(self):
        page = self.root / 'nested/index.html'
        parser = LocalHTML(self.root, page)
        parser.feed('<a href="../index.html?theme=dark&amp;x=1#day">Day</a>'
                    '<a href="#%D0%B4%D0%B5%D0%BD%D1%8C">Here</a><i id="день"></i>'
                    '<a href="%D1%84%D0%B0%D0%B9%D0%BB%20%D1%81%20%D0%BF%D1%80%D0%BE%D0%B1%D0%B5%D0%BB%D0%BE%D0%BC.html">File</a>'
                    '<link href="../style.css"><script src="../ReportInteractions.js"></script>')
        parser.close()

        self.assertEqual(set(parser.anchors), {(self.root / 'index.html', 'day'), (page, 'день')})
        self.assertEqual(parser.ids, {'день'})

    def test_external_missing_directory_and_escaping_paths_are_rejected(self):
        for reference in ('https://example.org/', '//example.org/index.html', 'file:///index.html',
                          'javascript:alert(1)', 'data:text/plain,x', '../outside.html',
                          '%2e%2e/outside.html', 'missing.html', 'nested/'):
            with self.subTest(reference = reference), self.assertRaises(ValueError):
                LocalHTML(self.root).feed(f'<a href="{reference}">Link</a>')

    def test_shared_resources_keep_relative_targets_specific_to_each_page(self):
        resources = LocalResources(self.root)
        root_page = LocalHTML(resources)
        nested_page = LocalHTML(resources, self.root / 'nested/index.html')
        root_page.feed('<a href="index.html#first">One</a><a href="index.html#second">Two</a>')
        nested_page.feed('<a href="index.html#first">Nested</a>')

        self.assertEqual(root_page.anchors, {(self.root / 'index.html', 'first'),
                                            (self.root / 'index.html', 'second')})
        self.assertEqual(nested_page.anchors, {(self.root / 'nested/index.html', 'first')})

    def test_new_check_does_not_reuse_deleted_resource(self):
        LocalHTML(self.root).feed('<link href="style.css">')
        (self.root / 'style.css').unlink()

        with self.assertRaises(ValueError):
            LocalHTML(self.root).feed('<link href="style.css">')

    def test_links_cannot_escape_through_symlinks(self):
        alias = self.root / 'alias.html'

        try:
            alias.symlink_to(self.directory / 'outside.html')
        except (OSError, NotImplementedError):
            self.skipTest("Symbolic links are unavailable")

        with self.assertRaises(ValueError):
            LocalHTML(self.root).feed('<a href="alias.html">Link</a>')

    def test_duplicate_ids_and_executable_content_remain_rejected(self):
        for html in ('<i id="same"></i><b id="same"></b>', '<a onclick="x()">Link</a>',
                     '<iframe></iframe>', '<object></object>', '<embed>', '<base href="index.html">',
                     '<script></script>', '<script src="style.css"></script>',
                     '<script src="ReportInteractions.js">alert(1)</script>'):
            with self.subTest(html = html), self.assertRaises(ValueError):
                LocalHTML(self.root).feed(html)

    def test_closing_tags_match_standard_parser_in_complete_and_split_input(self):
        documents = [
            '<h2 id="day">Day</h2><a href="#day">Link</a><br/><div><span>Text</span></div>',
            '<svg><![CDATA[<text>]]><text>Text</text></svg><math><mi>x</mi></math>',
            '<x-widget><ns:part>Text</ns:part></x-widget>',
            '<a href="index.html?a=1&amp;b=2#day">&lt;/a&gt;&#xA0;</a>',
        ]

        for tag in ('script', 'style', 'textarea', 'title', 'xmp', 'noembed', 'noframes', 'noscript', 'plaintext'):
            attributes = ' src="ReportInteractions.js"' if tag == 'script' else ''

            for ending in (f'</{tag}>', f'</{tag.upper()}>', f'</{tag} >', f'</{tag}/>', f'</{tag}'):
                documents.append(f'<{tag}{attributes}> \n{ending}<i id="after"></i>')

        for ending in ('</div>', '</DIV>', '</div >', '</div\n>', '</div/>',
                       '</div data-x=">">', '</div foo="bar">', '</div\x00>',
                       '</div', '</div ', '</', '</>', '</ div>', '</!>', '</é>',
                       '<!-- </div> -->', '<![CDATA[</div>]]>', '<?close </div>>'):
            documents.append(f'<div>Text\n{ending}<b id="after">Next</b>')

        for html in documents:
            for chunk_size in (1, 7, len(html)):
                with self.subTest(html = html, chunk_size = chunk_size):
                    expected = self.parse_outcome(html, chunk_size, HTMLParser.parse_endtag)

                    self.assertEqual(self.parse_outcome(html, chunk_size, LocalHTML.parse_endtag), expected)

    def test_closing_tags_preserve_rejections_in_script_and_after_it(self):
        documents = (
            '<script src="ReportInteractions.js"></td>alert(1)</script>',
            '<script src="ReportInteractions.js">&lt;/script&gt;</script>',
            '<script src="ReportInteractions.js"></script><b onclick="x()">Text</b>',
            '<script src="ReportInteractions.js"></SCRIPT ><a href="https://example.org/">Link</a>',
            '<i id="same"></i><script src="ReportInteractions.js"></script><b id="same"></b>',
            '<style>Text</style><iframe></iframe>',
            '<textarea>&lt;b&gt;</textarea><img src="missing.png">',
        )

        for html in documents:
            for chunk_size in (1, 7, len(html)):
                with self.subTest(html = html, chunk_size = chunk_size):
                    expected = self.parse_outcome(html, chunk_size, HTMLParser.parse_endtag)

                    self.assertEqual(expected['error'][0], 'ValueError')
                    self.assertEqual(self.parse_outcome(html, chunk_size, LocalHTML.parse_endtag), expected)

    def parse_outcome(self, html, chunk_size, endtag):
        parser = LocalHTML(self.root)
        error = None

        with patch.object(LocalHTML, 'parse_endtag', endtag), \
                patch.object(parser, 'handle_endtag', wraps = parser.handle_endtag) as ended:
            try:
                for offset in range(0, len(html), chunk_size):
                    parser.feed(html[offset:offset + chunk_size])

                parser.close()
            except ValueError as exception:
                error = (type(exception).__name__, str(exception))

        return {'error': error, 'ids': parser.ids, 'anchors': parser.anchors,
                'in_script': parser.in_script, 'cdata': parser.cdata_elem, 'position': parser.getpos(),
                'lasttag': parser.lasttag, 'starttag': parser.get_starttag_text(),
                'ended': ended.call_args_list}

    def test_missing_fragment_rejects_entire_report(self):
        source = self.directory / 'synthetic.txt'
        source.write_text('2026/09/01 00:00:00 1 abcd [INFO Client 1] : Trade accepted.\n')
        self.render = RenderReport().execute

        for number, reference in enumerate(('#missing', 'maps/index.html#missing', 'style.css#missing')):
            self.extra_link = f'<a href="{reference}">Synthetic link</a>'
            output = self.directory / str(number)

            with patch.object(RenderReport, 'execute', side_effect = self.render_with_extra_link):
                with self.assertRaisesRegex(ValueError, 'HTML identifier'):
                    ReportGenerator().generate(ReportRequest((source,), output))

            self.assertFalse(output.exists())

    def render_with_extra_link(self, *args, **kwargs):
        rendered = self.render(*args, **kwargs)
        page = rendered.directory / 'public/index.html'
        page.write_text(page.read_text() + self.extra_link)

        return rendered
