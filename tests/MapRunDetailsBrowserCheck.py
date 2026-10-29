import argparse
import json
import os
import shutil
import MapRunDetailsTests

from pathlib import Path

from tempfile import TemporaryDirectory

from ChromePipe import ChromePipe

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.request.ReportRequest import ReportRequest


class MapRunDetailsBrowserCheck:
    """Check run cards and links in Chrome through file:// in both languages."""

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description = "Browser checks for map-run details")
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
            source.write_bytes(MapRunDetailsTests.MapRunDetailsTests.fixture().encode())
            env = dict(os.environ)

            for variable in ('TMPDIR', 'TEMP', 'TMP', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME'):
                folder = root / variable.lower()
                folder.mkdir()
                env[variable] = str(folder)

            for language in ('ru', 'en'):
                result = ReportGenerator().generate(ReportRequest((source, source), root / language, report_language = language))
                public = result.report_path.parent
                run = MapRunDetailsTests.MapRunDetailsTests.returned(MapRunDetailsTests.MapRunDetailsTests.data(public))
                page = public / run['path']
                shutil.copyfile(project / 'tests/MapRunDetailsBrowserTests.js', page.parent / 'MapRunDetailsBrowserTests.js')
                harness = page.with_name('check.html')
                harness.write_text(page.read_text().replace('</body>',
                    '<pre id="browser-checks" hidden>pending</pre><script src="MapRunDetailsBrowserTests.js" defer></script></body>'))

                for theme, width in (('dark', 1500), ('light', 1500), ('dark', 760), ('light', 760)):
                    key = language + '-' + theme + '-' + str(width)
                    query = '&direct=yes#visit-' + str(run['visits'][1]['line']) if width == 760 else ''

                    with ChromePipe(chrome, root / ('profile-' + key), env, output / 'browser-stderr.log') as browser:
                        result = browser.check(harness.as_uri() + '?theme=' + theme + query, width, output, key)

                    results[key] = result
                    (output / 'results.json').write_text(json.dumps(results, ensure_ascii = False, indent = 2) + '\n')

                    if not result['passed']:
                        raise AssertionError(key + ': ' + str(result))

        print(json.dumps(results, ensure_ascii = False))


if __name__ == '__main__':
    MapRunDetailsBrowserCheck.main()
