"""Check observation analytics in a local browser using synthetic data."""

import argparse
import json
import os
import shutil

from pathlib import Path

from tempfile import TemporaryDirectory
from time import monotonic, sleep

from ChromePipe import ChromePipe
from ObservationAnalyticsTests import ObservationAnalyticsTests

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.request.ReportRequest import ReportRequest


class ObservationAnalyticsBrowserCheck:
    """Check both languages, themes, narrow screens, links, and operation without JS."""

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description = "Browser checks for observation analytics")
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
            source.write_text(ObservationAnalyticsTests.fixture(), encoding = 'utf-8')
            env = dict(os.environ)

            for variable in ('TMPDIR', 'TEMP', 'TMP', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME'):
                folder = root / variable.lower()
                folder.mkdir()
                env[variable] = str(folder)

            for language in ('ru', 'en'):
                public = ReportGenerator().generate(ReportRequest((source, source), root / language,
                    report_language = language)).report_path.parent

                for code in ObservationAnalyticsTests.PAGES:
                    page = public / f'analytics/{code}/index.html'
                    script = page.with_name('ObservationAnalyticsBrowserTests.js')
                    shutil.copyfile(project / 'tests/ObservationAnalyticsBrowserTests.js', script)
                    harness = page.with_name('check.html')
                    harness.write_text(page.read_text(encoding = 'utf-8').replace('</body>',
                        '<pre id="browser-checks" hidden>pending</pre>'
                        '<script src="ObservationAnalyticsBrowserTests.js" defer></script></body>'), encoding = 'utf-8')

                    for theme, width in (('dark', 1500), ('light', 1500), ('dark', 760), ('light', 760)):
                        key = '-'.join((language, code, theme, str(width)))

                        with ChromePipe(chrome, root / ('profile-' + key), env, output / 'browser-stderr.log') as browser:
                            checked = browser.check(harness.as_uri() + '?theme=' + theme + '&analytics=' + code,
                                                    width, output, key)

                        results[key] = checked
                        (output / 'results.json').write_text(json.dumps(results, ensure_ascii = False, indent = 2), encoding = 'utf-8')

                        if not checked['passed']:
                            raise AssertionError(key + ': ' + str(checked))

                for code in ObservationAnalyticsTests.PAGES:
                    key = language + '-' + code + '-no-js'

                    with ChromePipe(chrome, root / ('profile-' + key), env, output / 'browser-stderr.log') as browser:
                        results[key] = ObservationAnalyticsBrowserCheck.without_scripts(browser,
                            public / f'analytics/{code}/index.html')

                    (output / 'results.json').write_text(json.dumps(results, ensure_ascii = False, indent = 2), encoding = 'utf-8')

        print(json.dumps(results, ensure_ascii = False))

    @staticmethod
    def without_scripts(browser, page):
        target = browser.command('Target.createTarget', {'url': 'about:blank'})['targetId']
        session = browser.command('Target.attachToTarget', {'targetId': target, 'flatten': True})['sessionId']
        browser.command('Emulation.setScriptExecutionDisabled', {'value': True}, session)
        browser.command('Page.navigate', {'url': page.as_uri()}, session)
        deadline = monotonic() + 10
        expression = """(() => {
          const panels = [...document.querySelectorAll('[data-map-duration-panel]')];
          const controls = document.querySelector('[data-map-duration-controls]');
          return {passed: document.querySelectorAll('.analytics-navigation a').length === 29
            && !!document.querySelector('.analytics-page table, .analytics-page details')
            && (panels.length === 0 || (panels.length === 2 && panels.every(panel => !panel.hidden) && controls?.hidden)), checks: 3};
        })()"""
        result = {'passed': False}

        while monotonic() < deadline:
            result = browser.command('Runtime.evaluate', {'expression': expression, 'returnByValue': True}, session)['result'].get('value', {})

            if result.get('passed'):
                break

            sleep(.05)

        browser.command('Target.closeTarget', {'targetId': target})

        if not result.get('passed'):
            raise AssertionError("Tables and expandable details must remain available without JavaScript")

        return result


if __name__ == '__main__':
    ObservationAnalyticsBrowserCheck.main()
