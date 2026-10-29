import argparse
import base64
import json
import os
import shutil

from datetime import datetime, timedelta

from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep

from ChromePipe import ChromePipe

from poe_log_analyze.Bootstrap import Bootstrap
from poe_log_analyze.core.request.ReportOutputs import ReportOutputs
from poe_log_analyze.core.request.ReportRequest import ReportRequest


class WeeklyIntensityBrowserCheck:
    """File://, both themes/languages, pointer, keyboard, and continuous bands."""

    @staticmethod
    def source_text():
        records = []
        base = datetime(2026, 9, 7)

        for week in range(2):
            for day, hour in enumerate((7, 9, 12, 17, 19, 20, 14)):
                start = base + timedelta(days = 7 * week + day, hours = hour)
                messages = [(0, 'Client-Safe Instance ID = 42'),
                            (1, 'Generating level 83 area "MapWorldsDunes" with seed 123'),
                            (2, ': You have entered Synthetic Dunes.')]
                messages.extend((minute * 60, ': Trade accepted.') for minute in range(15, 91 + day * 10, 15))
                messages.append(((95 + day * 10) * 60, 'Abnormal disconnect: Synthetic end'))

                for seconds, message in messages:
                    stamp = (start + timedelta(seconds = seconds)).strftime('%Y/%m/%d %H:%M:%S')
                    records.append(f'{stamp} 1 abcd [INFO Client 42] {message}\n')

        return ''.join(records)

    @staticmethod
    def evaluate(browser, session, expression):
        result = browser.command('Runtime.evaluate', {'expression': expression, 'returnByValue': True}, session)

        if 'exceptionDetails' in result:
            raise AssertionError(result['exceptionDetails'])

        return result['result'].get('value')

    @classmethod
    def check(cls, browser, path, theme, width, output, key):
        target = browser.command('Target.createTarget', {'url': 'about:blank'})['targetId']
        session = browser.command('Target.attachToTarget', {'targetId': target, 'flatten': True})['sessionId']

        try:
            browser.command('Emulation.setDeviceMetricsOverride', {'width': width, 'height': 1000,
                'deviceScaleFactor': 1, 'mobile': False}, session)
            browser.command('Page.navigate', {'url': path.as_uri() + '?theme=' + theme}, session)
            deadline = monotonic() + 10

            while monotonic() < deadline:
                if cls.evaluate(browser, session, "document.readyState === 'complete' && !!document.querySelector('[data-intensity-hit][data-chart-tip]')"):
                    break

                sleep(.05)
            else:
                raise AssertionError("The chart did not load")

            measurements = cls.evaluate(browser, session, '''(() => {
                const svg = document.querySelector('.weekly-intensity-chart');
                const hits = [...svg.querySelectorAll('[data-intensity-hit]')];
                const first = hits[150];
                first.scrollIntoView({behavior: 'instant', block: 'center', inline: 'center'});
                const box = first.getBoundingClientRect();
                return {rows: svg.querySelectorAll('[data-intensity-row]').length,
                    stops: svg.querySelectorAll('stop').length, hits: hits.length,
                    bodyWidth: document.documentElement.scrollWidth, width: window.innerWidth,
                    theme: document.documentElement.dataset.bsTheme,
                    x: box.x + box.width / 2, y: box.y + box.height / 2, expected: first.dataset.chartTip};
            })()''')
            assert measurements['rows'] == 7 and measurements['hits'] == 2016, measurements
            assert measurements['stops'] == 2023, measurements
            assert measurements['bodyWidth'] <= measurements['width'] + 1, measurements
            assert measurements['theme'] == theme, measurements
            browser.command('Runtime.evaluate', {'expression': 'new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))',
                'awaitPromise': True}, session)
            browser.command('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': measurements['x'], 'y': measurements['y']}, session)
            tooltip = cls.evaluate(browser, session, '''(() => {
                const tip = document.querySelector('.chart-tooltip');
                const box = tip.getBoundingClientRect();
                return {hidden: tip.hidden, text: tip.textContent, x: box.x, right: box.right,
                    y: box.y, bottom: box.bottom, height: window.innerHeight};
            })()''')
            diagnostic = cls.evaluate(browser, session, 'document.elementFromPoint(' + str(measurements['x']) + ',' + str(measurements['y']) + ')?.outerHTML.slice(0, 300)')
            assert not tooltip['hidden'] and tooltip['text'] == measurements['expected'], (key, measurements, tooltip, diagnostic)
            assert tooltip['x'] >= 0 and tooltip['right'] <= width + 1, tooltip
            assert tooltip['y'] >= 0 and tooltip['bottom'] <= tooltip['height'] + 1, tooltip
            focused = cls.evaluate(browser, session, '''(() => {
                const hit = document.querySelector('[data-intensity-hit]');
                hit.focus();
                hit.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowRight', bubbles: true}));
                return document.activeElement === hit.nextElementSibling && !document.querySelector('.chart-tooltip').hidden;
            })()''')
            assert focused
            assert cls.evaluate(browser, session, '''(() => {
                document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key: 'End', bubbles: true}));
                const result = document.activeElement === document.querySelector('[data-intensity-row]').lastElementChild;
                document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
                return result && document.querySelector('.chart-tooltip').hidden;
            })()''')

            if key in ('ru-basic-dark-1500', 'en-extended-light-760'):
                cls.evaluate(browser, session, "document.querySelector('.weekly-intensity').scrollIntoView({behavior: 'instant', block: 'center'})")
                shot = browser.command('Page.captureScreenshot', {'format': 'png'}, session)['data']
                (output / (key + '.png')).write_bytes(base64.b64decode(shot))

            browser.command('Emulation.setScriptExecutionDisabled', {'value': True}, session)
            browser.command('Page.reload', {}, session)
            deadline = monotonic() + 10
            fallback = False

            while monotonic() < deadline:
                fallback = cls.evaluate(browser, session, "document.querySelectorAll('.weekly-intensity-chart stop').length === 2023 && document.querySelectorAll('[data-intensity-hit] title').length === 2016")

                if fallback:
                    break

                sleep(.05)

            assert fallback
            return {'passed': True, 'checks': 12}
        finally:
            browser.command('Target.closeTarget', {'targetId': target})

    @classmethod
    def main(cls):
        parser = argparse.ArgumentParser(description = "Continuous weekly heatmap and export themes")
        parser.add_argument('--output', type = Path, required = True)
        args = parser.parse_args()
        project = Path(__file__).resolve().parents[1]
        output = args.output.resolve()

        if not output.is_relative_to(project / 'build'):
            raise ValueError("Test data must be inside build")

        output.mkdir(parents = True, exist_ok = True)
        results = {}

        with TemporaryDirectory(dir = project / 'build/tmp') as temporary:
            root = Path(temporary)
            source = root / 'synthetic.log'
            source.write_text(cls.source_text(), encoding = 'utf-8')
            env = dict(os.environ)

            for variable in ('TMPDIR', 'TEMP', 'TMP', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME'):
                directory = root / variable.lower()
                directory.mkdir()
                env[variable] = str(directory)

            for language in ('ru', 'en'):
                result = Bootstrap.report_generator().generate(ReportRequest((source,), root / language,
                    report_language = language, outputs = ReportOutputs(True, True, True, True), pdf_dark = language == 'ru'))
                report = result.report_path.parent.parent
                shutil.copyfile(report / 'pdf/basic/report.pdf', output / ('sample-' + language + '.pdf'))
                shutil.copyfile(report / 'basic/public/images/activity-overview.png', output / ('areas-' + language + '.png'))

                with ChromePipe(shutil.which('google-chrome') or shutil.which('chromium'), root / ('profile-' + language),
                                env, output / ('chrome-' + language + '.log')) as browser:
                    for kind, page in (('basic', 'basic/public/index.html'), ('embedded', 'extended/public/basic/index.html'),
                                       ('extended', 'extended/public/playtime/index.html')):
                        for theme in ('dark', 'light'):
                            for width in (1500, 760):
                                key = f'{language}-{kind}-{theme}-{width}'
                                results[key] = cls.check(browser, report / page, theme, width, output, key)

        (output / 'results.json').write_text(json.dumps(results, ensure_ascii = False, indent = 2) + '\n')
        print(json.dumps({'scenarios': len(results), 'checks': sum(row['checks'] for row in results.values()),
                          'passed': True}, ensure_ascii = False))


if __name__ == '__main__':
    WeeklyIntensityBrowserCheck.main()
