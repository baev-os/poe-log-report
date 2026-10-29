import re

from html.parser import HTMLParser
from pathlib import Path

from urllib.parse import unquote, urlsplit

from poe_log_analyze.stages.verification.LocalResources import LocalResources

class LocalHTML(HTMLParser):
    """Validate local resources and reject executable report content."""

    _SIMPLE_END_TAG = re.compile(r'</([a-z][a-z0-9]*)>')

    def __init__(self, root: Path | LocalResources, page: Path | None = None, *, script_roots: tuple[Path, ...] | None = None):
        super().__init__()

        self.resources = root if isinstance(root, LocalResources) else LocalResources(root)
        self.root = self.resources.root
        self.page = (page or self.root / "index.html").resolve()
        self.directory = self.page.parent
        self.script_roots = script_roots or (self.root,)
        self.in_script = False
        self.ids = set()
        self.anchors = set()

    def parse_endtag(self, i: int) -> int:
        """Parse ordinary closing tags; delegate other forms to HTMLParser."""

        match = self._SIMPLE_END_TAG.match(self.rawdata, i)

        if match is None:
            return super().parse_endtag(i)

        # Follow HTMLParser: call the handler and leave CDATA/RCDATA mode.
        self.handle_endtag(match.group(1))
        self.clear_cdata_mode()

        return match.end()

    def handle_starttag(self, tag, attrs):
        if tag in ("iframe", "object", "embed", "base"):
            raise ValueError('Invalid element in HTML report')

        if tag == 'script':
            source = dict(attrs).get('src', '')
            script = self.resources.file(self.directory, source)
            allowed = {folder / name for folder in self.script_roots for name in (
                'vendor/bootstrap.bundle.min.js', 'ReportInteractions.js', 'ReportSearch.js',
                'MapExplorer.js', 'SessionComparison.js', 'ComparisonDisplay.js', 'MapRunComparison.js',
                'BasicReport.js', 'ChartTooltip.js', 'ReportTheme.js')}

            if script not in allowed or not source:
                raise ValueError('Invalid script in HTML report')

            self.in_script = True

        for key, value in attrs:
            if key == "id":
                if value in self.ids:
                    raise ValueError('Duplicate HTML identifier')

                self.ids.add(value)

            if key.startswith("on"):
                raise ValueError('Executable attribute in HTML report')

            if key in ("href", "src"):
                url = urlsplit(value or "")

                if url.scheme or url.netloc:
                    raise ValueError('Report resources must exist within the local site')

                path = self.resources.file(self.directory, unquote(url.path) if url.path else self.page.name)

                if url.fragment:
                    self.anchors.add((path, unquote(url.fragment)))

    def handle_data(self, data):
        if self.in_script and data.strip():
            raise ValueError('Inline code is prohibited in HTML reports')

    def handle_endtag(self, tag):
        if tag == 'script':
            self.in_script = False
