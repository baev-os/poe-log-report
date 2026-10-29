import argparse
import json
import os
import re
import shutil
import subprocess
import MapPaceTests
import MapAfkTests
import SessionTimelineTests

from html import unescape

from pathlib import Path

from tempfile import TemporaryDirectory

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.request.ReportRequest import ReportRequest


class MapExplorerBrowserCheck:
    """Local selection and comparison checks in both languages and themes."""

    @staticmethod
    def fixture():
        line = MapPaceTests.MapPaceTests.line
        text = MapAfkTests.MapAfkTests.fixture().replace(
            line(10, ': AFK mode is now ON. Autoreply "Synthetic"'),
            line(5, 'Sister Cassia: Synthetic observation.') +
            line(10, ': AFK mode is now ON. Autoreply "Synthetic"'))
        text = text.replace('Synthetic <City & Square>', 'Synthetic <City & Square> <script>window.injected=1</script>')
        third = ''.join(line(second, message, '2026-09-03T12:00:00') for second, message in (
            (0, 'Client-Safe Instance ID = 3'), (0, 'Generating level 81 area "MapWorldsDunes" with seed 3'),
            (1, ': You have entered Dunes.'), (2, ': 3 Items identified')))
        zero = ''.join(line(second, message, '2026-09-04T12:00:00') for second, message in (
            (0, 'Client-Safe Instance ID = 4'), (0, 'Generating level 80 area "MapWorldsBeach" with seed 4'),
            (1, ': You have entered Synthetic Zero.'), (1, 'Generating level 1 area "HideoutOssuary" with seed 4'),
            (2, ': You have entered Synthetic Hideout.'), (3, 'Closing game gracefully')))

        return text + third + zero

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description = "Map-selection checks through file:// in Chrome")
        parser.add_argument('--output', type = Path, required = True)
        args = parser.parse_args()
        project = Path(__file__).resolve().parents[1]
        output = args.output.resolve()

        if not output.is_relative_to(project / 'build'):
            raise ValueError("Check results must be inside the project build directory")

        output.mkdir(parents = True, exist_ok = True)
        chrome = shutil.which('google-chrome') or shutil.which('chromium')

        if chrome is None:
            raise ValueError("The browser check requires Chrome or Chromium")

        results = {}

        with TemporaryDirectory(dir = project / 'build/tmp') as temporary:
            root = Path(temporary)
            source = root / 'synthetic.txt'
            source.write_text(MapExplorerBrowserCheck.fixture())
            env = dict(os.environ)

            for variable in ('TMPDIR', 'TEMP', 'TMP', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME'):
                folder = root / variable.lower()
                folder.mkdir()
                env[variable] = str(folder)

            for language in ('ru', 'en'):
                result = ReportGenerator().generate(ReportRequest((source, source), root / language, report_language = language))
                public = result.report_path.parent
                shutil.copyfile(project / 'tests/MapExplorerBrowserTests.js', public / 'explore/BrowserTests.js')
                html = (public / 'explore/index.html').read_text().replace('</body>',
                    '<pre id="browser-checks">pending</pre><script src="BrowserTests.js" defer></script></body>')
                harness = public / 'explore/check.html'
                harness.write_text(html)

                for theme in ('dark', 'light'):
                    key = language + '-' + theme
                    command = [chrome, '--headless', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
                               '--no-first-run', '--no-default-browser-check', '--disable-background-networking',
                               '--disable-component-update', '--disable-extensions', '--disable-sync',
                               '--host-resolver-rules=MAP * ~NOTFOUND', '--window-size=1500,4500',
                               '--virtual-time-budget=15000', '--user-data-dir=' + str(root / 'profile'),
                               '--dump-dom', '--screenshot=' + str(output / (key + '.png')), harness.as_uri() + '?theme=' + theme]
                    completed = subprocess.run(command, env = env, capture_output = True, text = True, timeout = 45, check = True)
                    match = re.search(r'<pre id="browser-checks">(.*?)</pre>', completed.stdout, re.S)
                    value = unescape(match[1]) if match else ''

                    if not value.startswith('{'):
                        (output / (key + '-failed.html')).write_text(completed.stdout)
                        raise AssertionError("The browser check did not complete: " + value)

                    results[key] = json.loads(value)
                    (output / 'browser.json').write_text(json.dumps(results, ensure_ascii = False, indent = 2) + '\n')

                    if not results[key]['passed']:
                        (output / (key + '-failed.html')).write_text(completed.stdout)
                        raise AssertionError(results[key]['error'])

            source.write_text(SessionTimelineTests.SessionTimelineTests.fixture())
            day_result = ReportGenerator().generate(ReportRequest((source,), root / 'day'))
            page = day_result.report_path.parent / 'maps/2026-09-02/index.html'
            command = [chrome, '--headless', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
                       '--no-first-run', '--disable-background-networking', '--disable-extensions',
                       '--host-resolver-rules=MAP * ~NOTFOUND', '--window-size=1500,1600',
                       '--virtual-time-budget=1000', '--user-data-dir=' + str(root / 'profile'),
                       '--screenshot=' + str(output / 'day.png'), page.as_uri()]
            subprocess.run(command, env = env, capture_output = True, text = True, timeout = 45, check = True)

        print(json.dumps(results, ensure_ascii = False))


if __name__ == '__main__':
    MapExplorerBrowserCheck.main()
