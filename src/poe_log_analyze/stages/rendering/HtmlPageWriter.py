"""Write local HTML pages from templates and prepared data."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError
from markdown import Markdown
from markupsafe import Markup

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.stages.composition.localization.TranslationCatalogue import TranslationCatalogue


class HtmlPageWriter:
    """Escape log data and check cancellation between HTML fragments."""

    def __init__(self, resources: Path, project: Path, language: str, data: dict,
                 catalogue: TranslationCatalogue, control: ExecutionContext, *, label: str = 'HTML'):

        self.resources = resources
        self.project = project
        self.language = language
        self.data = data
        self.catalogue = catalogue
        self.control = control
        self.label = label
        self.pages = 0
        self.markdown = Markdown(extensions = ["tables", "fenced_code", "toc"])
        self.environment = Environment(loader = FileSystemLoader(project / "layouts"),
                                       autoescape = True, undefined = StrictUndefined,
                                       keep_trailing_newline = True, finalize = self.display_value)
        self.environment.globals["translate"] = catalogue.text
        self.environment.globals["diagnostic_reason"] = catalogue.diagnostic_reason
        self.environment.globals["area_detail_href"] = self.area_detail_href
        self.environment.globals["map_run_href"] = self.map_run_href
        self.environment.filters["markdown"] = self.trusted_markdown

    def area_detail_href(self, row: dict) -> str | None:
        """Find the selected area's prepared page without deriving a path from log text."""

        links = self.data.get('area_details', {}).get('links', {})
        kind = row.get('kind_code', 'map')

        return links.get(kind, {}).get(row.get('area_id') or row['name'])

    @staticmethod
    def display_value(value):
        """Empty optional values must not become the word None."""

        return "" if value is None else value

    def map_run_href(self, row: dict) -> str | None:
        """Instance or visit link from the prepared projection index."""

        model = self.data.get('map_run_details', {})
        line = str(row.get('line', row.get('_line')))

        return model.get('links', {}).get(line) or model.get('visit_links', {}).get(line)

    def trusted_markdown(self, text: str) -> Markup:
        """Render markup only from project text; never pass user messages here."""

        self.control.check()
        return Markup(self.markdown.reset().convert(text))

    def write(self, path: str, source: str, *, template: str = "index.html", **front) -> None:
        self.control.check()
        activity = self.label + ': ' + str(front.get('title', path)) + ' · ' + path
        self.control.report(activity, processed = self.pages, unit = 'pages', force = True)
        text = (self.resources / self.catalogue.source(source)).read_text(encoding = "utf-8")

        if text.startswith("---\n"):
            text = text.split("---", 2)[2].lstrip()

        public = self.project.parent / "public"
        destination = public / path

        if not destination.resolve().is_relative_to(public.resolve()):
            raise ValueError('The page path escapes the report directory')

        context = {**front, "content": self.trusted_markdown(text)}
        destination.parent.mkdir(parents = True, exist_ok = True)

        try:
            with destination.open("w", encoding = "utf-8", newline = "\n") as output:
                for chunk in self.environment.get_template(template).generate(
                        ctx = context, data = self.data, language = self.language):
                    self.control.check()
                    output.write(chunk)
        except TemplateError as error:
            raise ValueError(f"Could not render HTML {path}: {error}") from error

        self.pages += 1
        self.control.report(activity, processed = self.pages, unit = 'pages', force = True)
