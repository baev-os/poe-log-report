import base64
import json
import os
import select
import subprocess
import time

from pathlib import Path


class ChromePipe:
    """Local Linux Chrome over a pipe with explicit window size and real check timing."""

    def __init__(self, chrome: str, profile: Path, environment: dict, log: Path):
        self.log = log.open('w')
        # FDs 3/4 are the Chrome interface; pass argv without shell-code interpolation.
        self.process = subprocess.Popen(['bash', '-c', 'exec 3<&0 4>&1; exec "$@"', 'browser', chrome,
            '--headless', '--ozone-platform=headless', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
            '--no-first-run', '--disable-background-networking', '--disable-component-update',
            '--disable-extensions', '--disable-sync', '--host-resolver-rules=MAP * ~NOTFOUND',
            '--remote-debugging-pipe', '--user-data-dir=' + str(profile)],
            stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = self.log, env = environment)
        self.number = 0
        self.buffer = b''

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        try:
            self.command('Browser.close')
        except (OSError, ValueError, TimeoutError):
            self.process.terminate()

        try:
            self.process.wait(timeout = 5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()

        self.process.stdin.close()
        self.process.stdout.close()
        self.log.close()

    def command(self, method: str, params: dict | None = None, session: str | None = None) -> dict:
        self.number += 1
        request = {'id': self.number, 'method': method, 'params': params or {}}

        if session:
            request['sessionId'] = session

        self.process.stdin.write(json.dumps(request).encode() + b'\0')
        self.process.stdin.flush()
        deadline = time.monotonic() + 10

        while time.monotonic() < deadline:
            if b'\0' not in self.buffer:
                ready, _, _ = select.select([self.process.stdout], [], [], max(0, deadline - time.monotonic()))

                if not ready:
                    break

                chunk = os.read(self.process.stdout.fileno(), 65536)

                if not chunk:
                    raise ValueError("Chrome closed the test channel")

                self.buffer += chunk
                continue

            message, self.buffer = self.buffer.split(b'\0', 1)
            response = json.loads(message)

            if response.get('id') == self.number:
                if 'error' in response:
                    raise ValueError(str(response['error']))

                return response.get('result', {})

        raise TimeoutError("Chrome did not respond: " + method)

    def check(self, url: str, width: int, output: Path, key: str) -> dict:
        target = self.command('Target.createTarget', {'url': 'about:blank'})['targetId']
        session = self.command('Target.attachToTarget', {'targetId': target, 'flatten': True})['sessionId']
        self.command('Emulation.setDeviceMetricsOverride', {'width': width, 'height': 2200,
                     'deviceScaleFactor': 1, 'mobile': False}, session)
        self.command('Page.navigate', {'url': url}, session)
        deadline = time.monotonic() + 20
        result = None

        while time.monotonic() < deadline:
            response = self.command('Runtime.evaluate', {'expression': "document.getElementById('browser-checks')?.textContent",
                                    'returnByValue': True}, session)
            value = response.get('result', {}).get('value')

            if isinstance(value, str) and value.startswith('{'):
                result = json.loads(value)
                break

            time.sleep(.05)

        if result is None:
            result = {'passed': False, 'error': "No response from the browser scenario"}

        screenshot = self.command('Page.captureScreenshot', {'format': 'png'}, session)
        (output / (key + '.png')).write_bytes(base64.b64decode(screenshot['data']))

        if not result['passed']:
            html = self.command('Runtime.evaluate', {'expression': 'document.documentElement.outerHTML', 'returnByValue': True}, session)
            (output / 'failed.html').write_text(html['result']['value'])

        self.command('Target.closeTarget', {'targetId': target})

        return result
