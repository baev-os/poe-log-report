import argparse
import json
import os
import shutil
import MapRunDetailsTests

from datetime import date

from pathlib import Path

from tempfile import TemporaryDirectory

from ChromePipe import ChromePipe

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod
from poe_log_analyze.core.request.ReportRequest import ReportRequest


class PeriodOverviewBrowserCheck:
    """Synthetic file:// overview: two pages, themes, languages, and widths."""

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description = "Browser checks for the period overview")
        parser.add_argument('--output', type = Path, required = True)
        args = parser.parse_args()
        project = Path(__file__).resolve().parents[1]
        output = args.output.resolve()

        if not output.is_relative_to(project / 'build'):
            raise ValueError("Check results must be inside the project build directory")

        output.mkdir(parents = True, exist_ok = True)
        chrome = shutil.which('google-chrome') or shutil.which('chromium')

        if chrome is None:
            raise ValueError("Chrome or Chromium must be installed")

        results = {}
        (output / 'results.json').write_text('{}\n')

        with TemporaryDirectory(dir = project / 'build/tmp') as temporary:
            root = Path(temporary)
            source = root / 'synthetic.txt'
            source.write_text(MapRunDetailsTests.MapRunDetailsTests.fixture())
            env = dict(os.environ)

            for variable in ('TMPDIR', 'TEMP', 'TMP', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME'):
                folder = root / variable.lower()
                folder.mkdir()
                env[variable] = str(folder)

            for language in ('ru', 'en'):
                result = ReportGenerator().generate(ReportRequest((source, source), root / language,
                    report_language = language, period = ReportPeriod(date(2026, 9, 1), date(2026, 9, 2)),
                    comparison_period = ReportPeriod(date(2026, 8, 31), date(2026, 9, 1))))
                public = result.report_path.parent

                for theme, width in (('dark', 1500), ('light', 1500), ('dark', 760), ('light', 760)):
                    page = public / ('index.html' if width == 1500 else 'playtime/index.html')
                    shutil.copyfile(project / 'tests/PeriodOverviewBrowserTests.js', page.parent / 'PeriodOverviewBrowserTests.js')
                    harness = page.with_name('check.html')
                    harness.write_text(page.read_text().replace('</body>',
                        '<pre id="browser-checks" hidden>pending</pre><script src="PeriodOverviewBrowserTests.js" defer></script></body>'))
                    key = language + '-' + theme + '-' + str(width)

                    with ChromePipe(chrome, root / ('profile-' + key), env, output / 'browser-stderr.log') as browser:
                        checked = browser.check(harness.as_uri() + '?theme=' + theme + '#period-overview', width, output, key)

                    results[key] = checked
                    (output / 'results.json').write_text(json.dumps(results, ensure_ascii = False, indent = 2) + '\n')

                    if not checked['passed']:
                        raise AssertionError(key + ': ' + str(checked))

        print(json.dumps(results, ensure_ascii = False))


if __name__ == '__main__':
    PeriodOverviewBrowserCheck.main()
