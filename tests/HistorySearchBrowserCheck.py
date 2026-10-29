import argparse
import json
import os
import re
import shutil
import subprocess

from html import unescape

from pathlib import Path

from tempfile import TemporaryDirectory

from SearchIndexTests import SearchIndexTests

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.request.ReportRequest import ReportRequest


class HistorySearchBrowserCheck:
    """Check local search chunks with real Chrome and no HTTP server."""

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description = "Search checks through file:// in Chrome")
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
            source.write_bytes(SearchIndexTests.source_text().encode() + b'\xff\n' + b'\n' * 650)
            env = dict(os.environ)

            for variable, directory in (('TMPDIR', 'tmp'), ('TEMP', 'tmp'), ('TMP', 'tmp'),
                                        ('XDG_CONFIG_HOME', 'config'), ('XDG_CACHE_HOME', 'cache'), ('XDG_DATA_HOME', 'data')):
                env[variable] = str(root / directory)
                (root / directory).mkdir(exist_ok = True)

            for language in ('ru', 'en'):
                result = ReportGenerator().generate(ReportRequest((source, source), root / language,
                                                                report_language = language))
                public = result.report_path.parent
                shutil.copyfile(project / 'tests/ReportSearchBrowserTests.js', public / 'search/BrowserTests.js')
                html = (public / 'search/index.html').read_text()
                html = html.replace('</body>', '<pre id="browser-checks">pending</pre>'
                                    '<script src="BrowserTests.js" defer></script></body>')
                harness = public / 'search/check.html'
                harness.write_text(html)
                command = [chrome, '--headless', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
                           '--no-first-run', '--no-default-browser-check', '--disable-background-networking',
                           '--disable-component-update', '--disable-extensions', '--disable-sync',
                           '--metrics-recording-only', '--host-resolver-rules=MAP * ~NOTFOUND',
                           '--window-size=1500,1100', '--hide-scrollbars', '--virtual-time-budget=60000',
                           '--user-data-dir=' + str(root / 'profile'), '--dump-dom',
                           '--screenshot=' + str(output / (language + '.png')), harness.as_uri()]
                completed = subprocess.run(command, env = env, capture_output = True, text = True, timeout = 60, check = True)
                match = re.search(r'<pre id="browser-checks">(.*?)</pre>', completed.stdout, re.S)
                value = unescape(match[1]) if match else ''

                if not value.startswith('{'):
                    (output / (language + '-failed.html')).write_text(completed.stdout)
                    raise AssertionError("The browser check did not complete: " + value)

                results[language] = json.loads(value)
                (output / 'browser.json').write_text(json.dumps(results, ensure_ascii = False, indent = 2) + '\n')

                if not results[language]['passed']:
                    (output / (language + '-failed.html')).write_text(completed.stdout)
                    raise AssertionError(results[language]['error'])

        print(json.dumps(results, ensure_ascii = False))


if __name__ == '__main__':
    HistorySearchBrowserCheck.main()
