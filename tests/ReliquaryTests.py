"""Chest context and free text without consuming neighboring records."""

import json
import unittest

from base64 import b64decode
from io import BytesIO

from pathlib import Path
from tempfile import TemporaryDirectory

from zoneinfo import ZoneInfo

from poe_log_analyze.runtime.GameAreaCatalogue import GameAreaCatalogue

from poe_log_analyze.stages.parsing.LogParser import LogParser
from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue
from poe_log_analyze.stages.parsing.CollectionAnalysisService import CollectionAnalysisService

from ReportFixture import ReportFixture


class ReliquaryTests(unittest.TestCase):
    @staticmethod
    def line(message, tick = 100, pid = 1, level = 'INFO'):
        return f'2026/09/01 12:00:00 {tick} abcd [{level} Client {pid}] {message}\r\n'.encode()

    @classmethod
    def context(cls, area_id = 'ClassicTreasury_Cosmic', name = 'Voidborn Reliquary'):
        return b''.join(cls.line(text) for text in (
            f'Generating level 75 area "{area_id}" with seed 1',
            f'[SCENE] Set Source [{name}]', f': You have entered {name}.',
            f'[LOADING SCREEN] ({name}) Duration = 1.5 seconds'))

    @staticmethod
    def rows(raw):
        return list(LogParser.iter_records(BytesIO(raw), ZoneInfo('Asia/Almaty')))

    def test_multiline_message_keeps_bytes_and_one_parent_until_header(self):
        raw = self.context() + self.line(': Synthetic gift <script>alert(1)</script>')
        raw += b'Synthetic second line\r\nSynthetic third line\n'
        raw += self.line(': 3 Items identified') + b'Unrelated trailing text'
        rows = self.rows(raw)

        self.assertEqual([row['type'] for row in rows[4:]], [
            'reliquary.message', 'reliquary.message.field', 'reliquary.message.field',
            'screen.items_identified', 'unknown'])
        self.assertEqual([row['record_id'] for row in rows[4:7]], [5, 5, 5])
        self.assertNotIn('timestamp', rows[5])
        self.assertNotIn('timestamp', rows[6])
        self.assertEqual(b''.join(b64decode(row['raw_base64']) for row in rows), raw)
        self.assertEqual(rows[-1]['byte_end'], len(raw))

    def test_exact_area_ids_exclude_campaign_and_heist_and_require_each_step(self):
        for area_id, name in RuleCatalogue.RELIQUARY_AREAS.items():
            self.assertEqual(GameAreaCatalogue.lookup(area_id)['name'], name)
            self.assertEqual(self.rows(self.context(area_id, name) + self.line(': Synthetic gift'))[-1]['type'], 'reliquary.message')

        for area_id, name in (('1_5_7', 'The Reliquary'), ('2_10_7', 'The Reliquary'),
                              ('HeistReliquary1', 'Reliquary'), ('Unknown', 'Voidborn Reliquary')):
            self.assertEqual(self.rows(self.context(area_id, name) + self.line(': Synthetic gift'))[-1]['status'], 'unknown')

        parts = self.context().splitlines(keepends = True)

        for skipped in range(len(parts)):
            raw = b''.join(part for index, part in enumerate(parts) if index != skipped)

            self.assertEqual(self.rows(raw + self.line(': Synthetic gift'))[-1]['status'], 'unknown')

        self.assertEqual(self.rows(self.line(': Synthetic gift'))[-1]['status'], 'unknown')

    def test_resets_at_context_boundaries_and_consumes_only_one_message(self):
        for boundary in (
            self.line('Generating level 1 area "Hideout" with seed 2'),
            self.line('[SCENE] Set Source [Other]'), self.line(': You have entered Other.'),
            self.line('[LOADING SCREEN] (Other) Duration = 1 seconds'),
            self.line('Abnormal disconnect: An unexpected disconnection occurred.'),
            self.line('Closing game gracefully'),
            self.line('Connecting to instance server at 127.0.0.1:6112'),
            b'2026/09/01 12:00:00 ***** LOG FILE OPENING *****\r\n',
            b'\xff\n', self.line('Synthetic unknown text'),
            self.line(': Trade accepted.').replace(b'2026/09/01', b'2026/02/30'),
            self.line(': Trade accepted.', pid = 2), self.line(': Trade accepted.', tick = 99),
        ):
            with self.subTest(boundary = boundary):
                self.assertEqual(self.rows(self.context() + boundary + self.line(': Synthetic gift'))[-1]['status'], 'unknown')

        raw = self.context() + self.line(': You have entered Other.')
        raw += self.line(': You have entered Voidborn Reliquary.')
        raw += self.line('[LOADING SCREEN] (Voidborn Reliquary) Duration = 1 seconds')

        self.assertEqual(self.rows(raw + self.line(': Synthetic gift'))[-1]['status'], 'unknown')

        raw = self.context() + self.line(': Synthetic first gift') + self.line(': Synthetic second gift')

        self.assertEqual([row['status'] for row in self.rows(raw)[-2:]], ['recognized', 'unknown'])
        self.assertNotEqual(self.rows(self.context() + self.line(': Synthetic gift', level = 'WARN'))[-1]['type'], 'reliquary.message')

    def test_system_rules_keep_priority_and_known_chest_phrases_use_context(self):
        raw = self.context().replace(self.line('[SCENE] Set Source [Voidborn Reliquary]'),
                                     self.line('[SCENE] Set Source [(null)]') + self.line('[SCENE] Set Source [Voidborn Reliquary]'))

        self.assertEqual(self.rows(raw + self.line(': Synthetic gift'))[-1]['type'], 'reliquary.message')

        rows = self.rows(self.context() + self.line(': 3 Items identified') + self.line(': Synthetic gift'))

        self.assertEqual([row['type'] for row in rows[-2:]], ['screen.items_identified', 'reliquary.message'])

        for code in RuleCatalogue.RELIQUARY_PHRASES:
            phrase = RuleCatalogue.SCREEN_PHRASES[code.removeprefix('screen.phrase.')]

            self.assertEqual(self.rows(self.line(': ' + phrase))[-1]['type'], code)
            self.assertEqual(self.rows(self.context() + self.line(': ' + phrase))[-1]['type'], 'reliquary.message')

    def test_continuation_stops_at_blank_control_error_or_new_log(self):
        for boundary in (b'\r\n', b'bad\x00text\r\n', b'\xff\n',
                         b'2026/09/01 12:00:00 ***** LOG FILE OPENING *****\r\n',
                         self.line('Synthetic next header'),
                         self.line('Synthetic invalid date').replace(b'2026/09/01', b'2026/02/30')):
            rows = self.rows(self.context() + self.line(': Synthetic gift') + boundary + b'Unrelated text\n')

            self.assertEqual(rows[-1]['status'], 'unknown')

        rows = self.rows(self.context() + self.line(': Synthetic gift') + b'Last line without newline')

        self.assertEqual(rows[-1]['type'], 'reliquary.message.field')

    def test_character_evidence_survives_opening_but_not_another_file(self):
        proof = self.line(': SyntheticHero (Duelist) is now level 2')
        reopening = b'2026/09/01 12:00:00 ***** LOG FILE OPENING *****\r\n'
        chat = self.line('SyntheticHero: Synthetic chat')
        rows = self.rows(chat + proof + reopening + chat)

        self.assertEqual(rows[0]['status'], 'unknown')
        self.assertEqual(rows[-1]['type'], 'chat.local')
        self.assertEqual(self.rows(chat)[0]['status'], 'unknown')

    def test_export_preserves_whole_event_escaping_languages_and_deduplication(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, copy = root / 'one.txt', root / 'copy.txt'
            source.write_bytes(self.context() + self.line(': Synthetic gift <script>crashed</script>')
                               + b'Synthetic continuation\r\n' + self.line(': Trade accepted.'))
            copy.write_bytes(source.read_bytes())

            CollectionAnalysisService.analyze_collection([source, copy], root / 'analysis')

            for language in ('ru', 'en'):
                output = root / language

                entry = ReportFixture.export_report(root / 'analysis', output, report_language = language)
                timeline = json.loads((output / 'project/data/timeline.json').read_text())
                events = [event for day in timeline['by_date'].values() for event in day['events'] if event['type'] == 'reliquary.message']

                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]['message']['fields']['message'], 'Synthetic gift <script>crashed</script>\nSynthetic continuation')

                for relative in ('events/index.html', 'technical/timeline/2026-09-01/index.html'):
                    html = (entry.parent / relative).read_text()

                    self.assertIn('&lt;script&gt;crashed&lt;/script&gt;', html)
                    self.assertIn('Synthetic continuation', html)
                    self.assertNotIn('<script>crashed', html)

                    if relative.startswith('technical/'):
                        self.assertIn('&lt;script&gt;crashed&lt;/script&gt;\nSynthetic continuation', html)

                issues = json.loads((output / 'project/data/issues.json').read_text())

                self.assertEqual(issues['count'], 0)

                analysis = json.loads((output / 'project/data/analysis.json').read_text())

                self.assertEqual(analysis['unknown_lines'], 0)
                self.assertIn('reliquary.message.continuation', (entry.parent / 'technical/specification/index.html').read_text())
