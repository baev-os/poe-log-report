import argparse
import json
import os
import shutil
import MapRunComparisonTests
import SessionComparisonTests

from pathlib import Path

from tempfile import TemporaryDirectory

from ChromePipe import ChromePipe

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.request.ReportRequest import ReportRequest


class MapRunComparisonBrowserCheck:
    """A/B run acceptance and regression checks for the shared session-comparison scale."""

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description = "Browser checks for map-run comparison")
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
            env = dict(os.environ)

            for variable in ('TMPDIR', 'TEMP', 'TMP', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME'):
                folder = root / variable.lower()
                folder.mkdir()
                env[variable] = str(folder)

            for kind, test in (('runs', MapRunComparisonTests.MapRunComparisonTests),
                               ('sessions', SessionComparisonTests.SessionComparisonTests)):
                source = root / (kind + '.txt')
                source.write_bytes(test.fixture().encode())

                for language in ('ru', 'en'):
                    result = ReportGenerator().generate(ReportRequest((source, source), root / (kind + '-' + language),
                                                                     report_language = language))
                    public = result.report_path.parent
                    identities = list(test.data(public)['by_run' if kind == 'runs' else 'by_session'])
                    direct = ('&a=' + identities[5 if kind == 'runs' else 1] + '&b=' + identities[0]
                              + '&direct=yes&mode=without_afk')
                    page = public / ('maps/compare/index.html' if kind == 'runs' else 'sessions/compare/index.html')
                    script = 'MapRunComparisonBrowserTests.js' if kind == 'runs' else 'SessionComparisonBrowserTests.js'
                    shutil.copyfile(project / 'tests' / script, page.parent / script)
                    harness = page.with_name('check.html')
                    harness.write_text(page.read_text().replace('</body>',
                        '<pre id="browser-checks" hidden>pending</pre><script src="' + script + '" defer></script></body>'))

                    for theme, width in (('dark', 1500), ('light', 1500), ('dark', 760), ('light', 760)):
                        key = kind + '-' + language + '-' + theme + '-' + str(width)
                        query = direct if width == 760 else '&a=unknown&b=invalid'

                        with ChromePipe(chrome, root / ('profile-' + key), env, output / 'browser-stderr.log') as browser:
                            checked = browser.check(harness.as_uri() + '?theme=' + theme + query, width, output, key)

                        results[key] = checked
                        (output / 'results.json').write_text(json.dumps(results, ensure_ascii = False, indent = 2) + '\n')

                        if not checked['passed']:
                            raise AssertionError(key + ': ' + str(checked))

        print(json.dumps(results, ensure_ascii = False))


if __name__ == '__main__':
    MapRunComparisonBrowserCheck.main()
