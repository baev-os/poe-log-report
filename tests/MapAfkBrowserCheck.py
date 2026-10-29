import argparse
import json
import os
import re
import shutil
import subprocess
import MapAfkTests

from html import unescape

from pathlib import Path

from tempfile import TemporaryDirectory

from ChromePipe import ChromePipe

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.request.ReportRequest import ReportRequest


class MapAfkBrowserCheck:
    """Check duration modes, visits, and gaps in a local browser."""

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description = "Map AFK checks through file://")
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

        with TemporaryDirectory(dir = project / 'build/tmp') as temporary:
            root = Path(temporary)
            source = root / 'synthetic.txt'
            source.write_text(MapAfkTests.MapAfkTests.fixture())
            env = dict(os.environ)

            for variable in ('TMPDIR', 'TEMP', 'TMP', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME'):
                folder = root / variable.lower()
                folder.mkdir()
                env[variable] = str(folder)

            for language in ('ru', 'en'):
                result = ReportGenerator().generate(ReportRequest((source, source), root / language, report_language = language))
                public = result.report_path.parent
                areas = MapAfkTests.MapAfkTests.data(public, 'area_details')
                dunes = next(page for page in areas['pages'] if page['area_id'] == 'MapWorldsDunes')

                for name, relative in (('pace', 'pace/index.html'), ('gaps', 'pace/index.html'), ('area', dunes['path'])):
                    page = public / relative
                    shutil.copyfile(project / 'tests/MapAfkBrowserTests.js', page.parent / 'AfkBrowserTests.js')
                    harness = page.with_name('check.html')
                    harness.write_text(page.read_text().replace('</body>',
                        '<pre id="browser-checks" hidden>pending</pre><script src="AfkBrowserTests.js" defer></script></body>'))

                    for theme in ('dark', 'light'):
                        key = language + '-' + name + '-' + theme
                        command = [chrome, '--headless', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
                            '--no-first-run', '--disable-background-networking', '--disable-component-update',
                            '--disable-extensions', '--disable-sync', '--host-resolver-rules=MAP * ~NOTFOUND',
                            '--window-size=1500,6000', '--virtual-time-budget=5000',
                            '--user-data-dir=' + str(root / 'profile'), '--dump-dom',
                            '--screenshot=' + str(output / (key + '.png')),
                            harness.as_uri() + '?theme=' + theme + '&capture=' + name]
                        completed = subprocess.run(command, env = ChromePipe.environment(env), capture_output = True, text = True, timeout = 45, check = True)
                        match = re.search(r'<pre id="browser-checks" hidden="">(.*?)</pre>', completed.stdout, re.S)
                        value = unescape(match[1]) if match else ''
                        result = json.loads(value) if value.startswith('{') else {'passed': False, 'error': "No browser response"}
                        results[key] = result
                        (output / 'results.json').write_text(json.dumps(results, ensure_ascii = False, indent = 2) + '\n')

                        if not result['passed']:
                            (output / 'failed.html').write_text(completed.stdout)
                            raise AssertionError(key + ': ' + str(result))

        print(json.dumps(results, ensure_ascii = False))


if __name__ == '__main__':
    MapAfkBrowserCheck.main()
