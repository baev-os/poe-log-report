import argparse
import json
import os
import shutil

from datetime import date, timedelta

from pathlib import Path

from tempfile import TemporaryDirectory
from time import monotonic, sleep
from urllib.parse import unquote, urlsplit

from ChromePipe import ChromePipe
from ReportVariantsTests import ReportVariantsTests

from poe_log_analyze.Bootstrap import Bootstrap
from poe_log_analyze.core.request.ReportOutputs import ReportOutputs
from poe_log_analyze.core.request.ReportRequest import ReportRequest
from poe_log_analyze.stages.rendering.BasicReportWriter import BasicReportWriter


class BasicReportBrowserCheck:
    """Local browser: basic sections of both sites, themes, scaling, and sorting."""

    @staticmethod
    def source_text():
        records = [ReportVariantsTests.source_text()]

        for index in range(75):
            day = (date(2026, 9, 2) + timedelta(days = index)).strftime('%Y/%m/%d')

            for stamp, message in (('12:00:00', 'Client-Safe Instance ID = 1'),
                    ('12:00:01', f'Generating level 83 area "MapWorldsBeach" with seed {index + 100}'),
                    ('12:00:02', ': You have entered Synthetic Beach.'),
                    ('12:10:00', 'Abnormal disconnect: Synthetic end')):
                records.append(f'{day} {stamp} 1 abcd [INFO Client 1] {message}\n')

        return ''.join(records)

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description = "Browser checks for the basic report")
        parser.add_argument('--output', type = Path, required = True)
        args = parser.parse_args()
        project = Path(__file__).resolve().parents[1]
        output = args.output.resolve()

        if not output.is_relative_to(project / 'build'):
            raise ValueError("Check results must be inside the project build directory")

        output.mkdir(parents = True, exist_ok = True)
        chrome = shutil.which('google-chrome') or shutil.which('chromium')
        results = {}

        with TemporaryDirectory(dir = project / 'build/tmp') as temporary:
            root = Path(temporary)
            source = root / 'synthetic.log'
            source.write_text(BasicReportBrowserCheck.source_text(), encoding = 'utf-8')
            env = dict(os.environ)

            for variable in ('TMPDIR', 'TEMP', 'TMP', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME'):
                folder = root / variable.lower()
                folder.mkdir()
                env[variable] = str(folder)

            for language in ('ru', 'en'):
                result = Bootstrap.report_generator().generate(ReportRequest((source,), root / language,
                    report_language = language, outputs = ReportOutputs(True, True, True, True)))
                report = result.report_path.parent.parent

                with ChromePipe(chrome, root / ('profile-' + language), env, output / 'browser-stderr.log') as browser:
                    for profile, prefix in (('basic', 'basic/public'), ('extended', 'extended/public/basic')):
                        for page, kind in zip(BasicReportWriter.PAGES, ('graphs', 'characters', 'maps', 'calendar', 'conversations')):
                            path = report / prefix / page
                            shutil.copyfile(project / 'tests/BasicReportBrowserTests.js', path.with_name('BasicReportBrowserTests.js'))
                            harness = path.with_name('check.html')
                            harness.write_text(path.read_text(encoding = 'utf-8').replace('</body>',
                                '<pre id="browser-checks" hidden>pending</pre><script src="BasicReportBrowserTests.js" defer></script></body>'), encoding = 'utf-8')
                            settings = (('light', 1500), ('dark', 1500), ('light', 760), ('dark', 760)) if profile == 'basic' else (('light', 1500),)

                            for theme, width in settings:
                                key = '-'.join((language, profile, kind, theme, str(width)))
                                checked = browser.check(harness.as_uri() + '?kind=' + kind + '&theme=' + theme, width, output, key)
                                results[key] = checked
                                (output / 'results.json').write_text(json.dumps(results, ensure_ascii = False, indent = 2), encoding = 'utf-8')

                                if not checked['passed']:
                                    raise AssertionError(key + ': ' + str(checked))

                            if kind in ('graphs', 'characters', 'maps', 'calendar'):
                                key = '-'.join((language, profile, kind, 'pointer'))
                                results[key] = BasicReportBrowserCheck.pointer_check(browser, path, kind)

                        if profile == 'extended':
                            results[language + '-extended-character-pointer'] = BasicReportBrowserCheck.pointer_check(
                                browser, report / 'extended/public/characters/index.html', 'characters')

                        for page in BasicReportWriter.PAGES:
                            key = language + '-' + profile + '-' + page.replace('/', '-') + '-no-js'
                            results[key] = BasicReportBrowserCheck.without_scripts(browser, report / prefix / page)

                    for theme, width in (('light', 1500), ('dark', 1500), ('light', 760), ('dark', 760)):
                        basic_style = BasicReportBrowserCheck.page_style(browser, report / 'basic/public/index.html', theme, width)
                        extended_style = BasicReportBrowserCheck.page_style(browser, report / 'extended/public/index.html', theme, width)

                        if basic_style != extended_style:
                            raise AssertionError(str((basic_style, extended_style)))

                        results[f'{language}-shared-style-{theme}-{width}'] = {'passed': True, 'checks': len(basic_style)}

                    for profile, page in (('basic', 'basic/public/characters/index.html'),
                                          ('extended', 'extended/public/index.html'),
                                          ('extended', 'extended/public/basic/characters/index.html')):
                        key = language + '-download-' + page.replace('/', '-')
                        results[key] = BasicReportBrowserCheck.pdf_download(browser, report / page,
                            report / 'pdf' / profile / 'report.pdf', root / key)

        (output / 'results.json').write_text(json.dumps(results, ensure_ascii = False, indent = 2), encoding = 'utf-8')
        print(json.dumps({'scenarios': len(results), 'checks': sum(row['checks'] for row in results.values()),
                          'passed': all(row['passed'] for row in results.values())}))

    @staticmethod
    def page_style(browser, page, theme, width):
        target = browser.command('Target.createTarget', {'url': 'about:blank'})['targetId']
        session = browser.command('Target.attachToTarget', {'targetId': target, 'flatten': True})['sessionId']
        browser.command('Emulation.setDeviceMetricsOverride', {'width': width, 'height': 1000,
                     'deviceScaleFactor': 1, 'mobile': False}, session)
        browser.command('Page.navigate', {'url': page.as_uri() + '?theme=' + theme}, session)
        deadline = monotonic() + 10

        while monotonic() < deadline:
            ready = browser.command('Runtime.evaluate', {'expression': "document.readyState === 'complete' && !!document.querySelector('.report-menu')",
                'returnByValue': True}, session)['result'].get('value')

            if ready:
                break

            sleep(.05)

        measured = browser.command('Runtime.evaluate', {'expression': '''(() => {
            const result = {};
            for (const selector of ['body','h1','.report-menu','.report-brand','.report-menu nav a:not([aria-current])','.theme-toggle','.report-pdf']) {
                const style = getComputedStyle(document.querySelector(selector));
                result[selector] = ['fontFamily','fontSize','lineHeight','color','backgroundColor','borderRadius','padding'].map(key => style[key]);
            }
            return result;
        })()''', 'returnByValue': True}, session)['result'].get('value')
        browser.command('Target.closeTarget', {'targetId': target})

        if not measured:
            raise AssertionError("Could not compare report styles")

        return measured

    @staticmethod
    def pdf_download(browser, page, expected, directory):
        directory.mkdir()
        browser.command('Browser.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': str(directory)})
        target = browser.command('Target.createTarget', {'url': 'about:blank'})['targetId']
        session = browser.command('Target.attachToTarget', {'targetId': target, 'flatten': True})['sessionId']
        browser.command('Page.navigate', {'url': page.as_uri()}, session)
        deadline = monotonic() + 10

        while monotonic() < deadline:
            ready = browser.command('Runtime.evaluate', {'expression':
                "document.readyState === 'complete' && !!document.querySelector('a.report-pdf[download]')",
                'returnByValue': True}, session)['result'].get('value')

            if ready:
                break

            sleep(.05)

        point = browser.command('Runtime.evaluate', {'expression': """(() => {
            const link=document.querySelector('a.report-pdf');
            link.scrollIntoView({behavior:'instant',block:'center'});
            const box=link.getBoundingClientRect();return {x:box.x+box.width/2,y:box.y+box.height/2};
        })()""", 'returnByValue': True}, session)['result'].get('value')
        browser.command('Runtime.evaluate', {'expression':
            'new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))', 'awaitPromise': True}, session)

        for event in ('mousePressed', 'mouseReleased'):
            browser.command('Input.dispatchMouseEvent', {'type': event, 'button': 'left', 'clickCount': 1, **point}, session)
        downloaded = directory / 'report.pdf'
        deadline = monotonic() + 10
        location = ''
        viewer = False

        while monotonic() < deadline and not downloaded.is_file():
            state = browser.command('Runtime.evaluate', {'expression': """({location:location.href,
                viewer:document.contentType==='application/pdf'||!!document.querySelector('embed[type="application/pdf"]')})""",
                'returnByValue': True}, session)['result'].get('value', {})
            location, viewer = state.get('location', ''), state.get('viewer', False)

            if viewer and Path(unquote(urlsplit(location).path)).resolve() == expected.resolve():
                break

            sleep(.05)

        saved = downloaded.is_file() and downloaded.read_bytes() == expected.read_bytes()
        opened = viewer and Path(unquote(urlsplit(location).path)).resolve() == expected.resolve()

        if not saved and not opened:
            raise AssertionError("The button must download the current report PDF: " + str({
                'location': location, 'files': [(path.name, path.stat().st_size) for path in directory.iterdir()]}))

        browser.command('Target.closeTarget', {'targetId': target})

        return {'passed': True, 'checks': 2, 'mode': 'download' if saved else 'viewer'}

    @staticmethod
    def pointer_check(browser, page, kind):
        """Real CDP hover checks the SVG hit area rather than only the handler."""

        target = browser.command('Target.createTarget', {'url': 'about:blank'})['targetId']
        session = browser.command('Target.attachToTarget', {'targetId': target, 'flatten': True})['sessionId']
        browser.command('Emulation.setDeviceMetricsOverride', {'width': 1200, 'height': 900,
                     'deviceScaleFactor': 1, 'mobile': False}, session)
        browser.command('Page.navigate', {'url': page.as_uri()}, session)
        selector = {'graphs': '.cumulative-chart .chart-hit', 'characters': '.character-chart .chart-hit',
                    'maps': '.map-pie path', 'calendar': '[data-calendar-day]'}[kind]
        encoded = json.dumps(selector)
        deadline = monotonic() + 10

        while monotonic() < deadline:
            ready = browser.command('Runtime.evaluate', {'expression':
                "document.readyState === 'complete' && !!document.querySelector(" + encoded + ')',
                'returnByValue': True}, session)['result'].get('value')

            if ready:
                break

            sleep(.05)

        geometry = browser.command('Runtime.evaluate', {'expression': '''(() => {
            const node = [...document.querySelectorAll(SELECTOR)].sort((a,b) => (b.getTotalLength?.() || 0) - (a.getTotalLength?.() || 0))[0];
            node.scrollIntoView({behavior:'instant',block:'center',inline:'center'});
            const box = node.getBoundingClientRect();
            if (node.matches('[data-calendar-day]')) return {x:box.right-6,y:box.bottom-6,id:node.hash.slice(1)};
            let point = node.getPointAtLength(node.getTotalLength() * .55);
            if (node.matches('.map-pie path')) {
                outer: for (let x=30; x<210; x+=10) for (let y=30; y<210; y+=10) {
                    if (node.isPointInFill(new DOMPoint(x,y))) {point = new DOMPoint(x,y);break outer;}
                }
            }
            const screen = point.matrixTransform(node.getScreenCTM());
            return {x:screen.x,y:screen.y};
        })()'''.replace('SELECTOR', encoded), 'returnByValue': True}, session)['result'].get('value')

        if not geometry:
            raise AssertionError(str(page) + ": pointer geometry is unavailable")

        point = {'x': geometry['x'], 'y': geometry['y']}
        browser.command('Runtime.evaluate', {'expression':
            'new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))', 'awaitPromise': True}, session)
        browser.command('Input.dispatchMouseEvent', {'type': 'mouseMoved', **point}, session)

        if kind == 'calendar':
            for event in ('mousePressed', 'mouseReleased'):
                browser.command('Input.dispatchMouseEvent', {'type': event, 'button': 'left', 'clickCount': 1, **point}, session)

            expression = 'document.getElementById(' + json.dumps(geometry['id']) + ').open'
        else:
            expression = '''(() => {const tip=document.getElementById('chart-measurement-tooltip');
                const box=tip.getBoundingClientRect();return !tip.hidden && tip.textContent.includes(' · ')
                && box.x>=0 && box.right<=innerWidth && box.y>=0 && box.bottom<=innerHeight;})()'''

        passed = browser.command('Runtime.evaluate', {'expression': expression, 'returnByValue': True}, session)['result'].get('value')
        diagnostic = browser.command('Runtime.evaluate', {'expression': '''(() => {
            const tip=document.getElementById('chart-measurement-tooltip');
            return {tip:tip?.textContent,hidden:tip?.hidden,element:document.elementFromPoint(X,Y)?.outerHTML.slice(0,240),scroll:scrollY};
        })()'''.replace('X,Y', str(point['x']) + ',' + str(point['y'])), 'returnByValue': True}, session)['result'].get('value')

        if kind != 'calendar':
            browser.command('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Escape'}, session)
            hidden = browser.command('Runtime.evaluate', {'expression':
                "document.getElementById('chart-measurement-tooltip').hidden", 'returnByValue': True}, session)['result'].get('value')
            passed = passed and hidden

        browser.command('Target.closeTarget', {'targetId': target})

        if not passed:
            raise AssertionError(str(page) + ": pointer hover/click failed: " + str(point) + ' ' + str(diagnostic))

        return {'passed': True, 'checks': 2 if kind == 'calendar' else 6}

    @staticmethod
    def without_scripts(browser, page):
        target = browser.command('Target.createTarget', {'url': 'about:blank'})['targetId']
        session = browser.command('Target.attachToTarget', {'targetId': target, 'flatten': True})['sessionId']
        browser.command('Emulation.setScriptExecutionDisabled', {'value': True}, session)
        browser.command('Page.navigate', {'url': page.as_uri()}, session)
        expression = """(() => ({passed: document.querySelectorAll('.basic-menu nav a').length === 5
            && !!document.querySelector('main h1') && !document.querySelector('a[href*="technical/"]')
            && [...document.querySelectorAll('[data-daily-controls], [data-chat-controls]')].every(node => node.hidden)
            && [...document.querySelectorAll('[data-message]')].every(node => node.closest('details.chat-group'))
            && [...document.querySelectorAll('[data-calendar-day]')].every(node => node.matches('a.calendar-day')), checks: 6}))()"""
        deadline = monotonic() + 10
        result = {'passed': False}

        while monotonic() < deadline:
            result = browser.command('Runtime.evaluate', {'expression': expression, 'returnByValue': True}, session)['result'].get('value', {})

            if result.get('passed'):
                break

            sleep(.05)

        browser.command('Target.closeTarget', {'targetId': target})

        if not result.get('passed'):
            raise AssertionError(str(page) + ': ' + str(result))

        return result


if __name__ == '__main__':
    BasicReportBrowserCheck.main()
