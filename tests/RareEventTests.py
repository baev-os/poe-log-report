"""Exact rare notices, rule priorities, and visit observations."""

import json
import unittest

from base64 import b64decode
from io import BytesIO

from pathlib import Path
from tempfile import TemporaryDirectory

from zoneinfo import ZoneInfo

from CollectionFixture import CollectionFixture

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.stages.parsing.LogParser import LogParser
from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue


class RareEventTests(unittest.TestCase):
    SAMPLES = {
        ': SyntheticHero has committed suicide.': 'screen.suicide',
        ': The Nameless Seer has appeared nearby.': 'screen.nameless_seer',
        ': A Reflecting Mist has manifested nearby.': 'screen.reflecting_mist',
    }

    @staticmethod
    def parse(raw):
        return list(LogParser.iter_records(BytesIO(raw), ZoneInfo('Asia/Almaty')))

    def test_exact_system_messages_keep_bytes_and_do_not_capture_chat(self):
        for message, code in self.SAMPLES.items():
            with self.subTest(code = code):
                raw = CollectionFixture.line(1, message).replace('\n', '\r\n').encode()
                rows = self.parse(raw)

                self.assertEqual(rows[0]['type'], code)
                self.assertEqual(b64decode(rows[0]['raw_base64']), raw)
                self.assertEqual(rows[0]['fields'], {'character': 'SyntheticHero'} if code == 'screen.suicide' else {})

                matches = [name for name, pattern in RuleCatalogue.MESSAGE_RULES
                           if name != 'reliquary.message' and pattern.fullmatch(message)]

                self.assertEqual(matches, [code])

                for altered in (message + ' extra', message.replace('nearby', 'elsewhere'),
                                message.replace('SyntheticHero', 'Synthetic Hero')):
                    if altered != message:
                        self.assertEqual(self.parse(CollectionFixture.line(1, altered).encode())[0]['status'], 'unknown')

                chat = self.parse(CollectionFixture.line(1, '@From SyntheticPlayer: ' + message).encode())[0]

                self.assertEqual(chat['type'], 'chat.whisper')

    def test_system_notifications_precede_reliquary_message_and_confirm_character(self):
        context = ''.join(CollectionFixture.line(i, text) for i, text in enumerate((
            'Generating level 75 area "ClassicTreasury_Cosmic" with seed 1',
            '[SCENE] Set Source [Voidborn Reliquary]', ': You have entered Voidborn Reliquary.',
            '[LOADING SCREEN] (Voidborn Reliquary) Duration = 1.5 seconds')))

        for message, code in self.SAMPLES.items():
            rows = self.parse((context + CollectionFixture.line(5, message)).encode())

            self.assertEqual(rows[-1]['type'], code)

        rows = self.parse((CollectionFixture.line(1, ': SyntheticHero has committed suicide.')
                           + CollectionFixture.line(2, 'SyntheticHero: Synthetic chat.')).encode())

        self.assertEqual(rows[-1]['type'], 'chat.local')

    def test_export_links_copied_sources_and_snapshots_without_character_inference(self):
        with TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp') as directory:
            root = Path(directory)
            source, other = root / 'synthetic.txt', root / 'other.txt'
            line = CollectionFixture.line
            source.write_text('\n' * 500 + ''.join([
                line(0, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
                line(1, 'Spawning discoverable Hideout HideoutSynthetic'),
                line(2, ': You have entered Dunes.'),
                line(3, ': The Nameless Seer has appeared nearby.'),
                line(4, ': A Reflecting Mist has manifested nearby.'),
                line(5, ': The Nameless Seer has appeared nearby.'),
                line(6, ': Synthetic<hero> has committed suicide.'),
                line(7, ': You have killed 1,000 monsters.'),
                line(8, ': You have died 20 times.'),
                line(9, ': You have killed 1,000 monsters.'),
                line(10, 'Abnormal disconnect: An unexpected disconnection occurred.'),
            ]))
            other.write_text(line(15, ': You have killed 7 monsters.'))

            for language, title in (('ru', 'Гибель от собственного урона'), ('en', 'Death from self-damage')):
                result = ReportGenerator().generate(ReportRequest((source, other, source), root / language,
                                                                  report_language = language))
                public = result.report_path.parent
                data = public.parent / 'project/data'
                flow = json.loads((data / 'map_flow.json').read_text())
                counters = json.loads((data / 'counter_history.json').read_text())

                self.assertEqual(flow['death_count'], 1)

                events = flow['rows'][0]['discoveries']

                self.assertEqual([event['code'] for event in events], ['hideout', 'nameless_seer', 'reflecting_mist'])
                self.assertEqual(events[0]['href'], 'events/page-2.html#line-502')
                self.assertEqual(counters['count'], 4)
                self.assertEqual([sample['count'] for sample in counters['rows']], ['1,000', '20', '1,000', '7'])
                self.assertEqual(counters['rows'][-1]['href'], 'events/page-2.html#line-512')

                html = (public / 'flow/index.html').read_text()

                self.assertIn('Synthetic&lt;hero&gt;', html)
                self.assertNotIn('Synthetic<hero>', html)
                self.assertIn(title, html)
                self.assertIn('Nameless Seer', html)
                self.assertIn('Reflecting Mist', html)
                self.assertIn('../events/page-2.html#line-502', html)

                timeline = (public / 'technical/timeline/2026-09-01/index.html').read_text()

                self.assertIn('id="line-502"', timeline)
                self.assertIn('id="line-507"', timeline)

                for page in ('statistics/index.html', 'technical/index.html'):
                    text = (public / page).read_text()

                    self.assertIn('class="counter-history"', text)
                    self.assertIn('1,000', text)
                    self.assertIn('events/page-2.html#line-512', text)

                manifest = json.loads((public.parent / 'report-manifest.json').read_text())

                self.assertIn('counter_history', manifest['views_sha256'])
