"""Local-chat confirmation, continuation boundaries, and new exact formats."""

import unittest

from base64 import b64decode
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from zoneinfo import ZoneInfo

from poe_log_analyze.stages.parsing.LogAnalysisService import LogAnalysisService
from poe_log_analyze.stages.parsing.LogParser import LogParser

from ReportFixture import ReportFixture


class VersionSevenTests(unittest.TestCase):
    @staticmethod
    def message(text):
        return f'2026/09/01 12:00:00 123 abcd [INFO Client 42] {text}\r\n'.encode()

    @staticmethod
    def rows(raw):
        return list(LogParser.iter_records(BytesIO(raw), ZoneInfo('Asia/Almaty')))

    def test_local_chat_requires_prior_evidence_and_survives_opening(self):
        raw = b''.join(self.message(text) for text in (
            'SyntheticHero: before confirmation',
            ': SyntheticHero has joined the area.',
            '<TEST> SyntheticHero: example',
            'SyntheticHero: \x00another example',
            'UnknownSpeaker: example',
            'SyntheticHero: \x00\x00invalid',
            'SyntheticHero: invalid\ttext',
            '@From Faustus: example',
            'Faustus: Synthetic dialogue.',
        ))
        raw += b'2026/09/01 12:01:00 ***** LOG FILE OPENING *****\r\n' + self.message('SyntheticHero: new session')
        rows = self.rows(raw)

        self.assertEqual([row['status'] for row in rows], ['unknown', 'recognized', 'recognized', 'recognized', 'unknown', 'unknown', 'unknown', 'recognized', 'recognized', 'recognized', 'recognized'])
        self.assertEqual(rows[2]['type'], 'chat.local')
        self.assertEqual(rows[2]['fields'], {'guild': '<TEST>', 'character': 'SyntheticHero', 'marker': None, 'message': 'example'})
        self.assertEqual(rows[3]['fields']['marker'], '\x00')
        self.assertEqual(rows[3]['fields']['message'], 'another example')
        self.assertEqual(rows[8]['type'], 'dialogue.named')
        self.assertEqual(b''.join(b64decode(row['raw_base64']) for row in rows), raw)
        self.assertEqual(self.rows(self.message('SyntheticHero: another file'))[0]['status'], 'unknown')

    def test_dialogue_paragraph_requires_cr_and_separator_and_preserves_header(self):
        raw = self.message('The Envoy: Synthetic first paragraph.\r') + b'\r\r\nSynthetic second paragraph.\r\n'
        rows = self.rows(raw)

        self.assertEqual([row['rule_id'] for row in rows], ['dialogue.named', 'dialogue.named.paragraph_break', 'dialogue.named.continuation'])
        self.assertEqual([row['record_id'] for row in rows], [1, 1, 1])
        self.assertNotIn('timestamp', rows[2])
        self.assertEqual(b''.join(b64decode(row['raw_base64']) for row in rows), raw)

        for parent, middle, ending in (
            ('The Envoy: Synthetic paragraph.', b'\r\r\n', b'Unrelated\r\n'),
            ('The Envoy: Synthetic paragraph.\r', b'\r\n', b'Unrelated\r\n'),
            ('The Envoy: Synthetic paragraph.\r', b'', b'Unrelated\r\n'),
            ('The Envoy: Synthetic paragraph.\r', b'\r\r\n', b'Invalid\x00text\r\n'),
        ):
            with self.subTest(parent = parent, middle = middle):
                self.assertEqual(self.rows(self.message(parent) + middle + ending)[-1]['status'], 'unknown')

        rows = self.rows(self.message('The Envoy: Synthetic paragraph.\r') + b'\r\r\n' + self.message(': Trade accepted.'))

        self.assertEqual(rows[-1]['type'], 'screen.trade')
        self.assertEqual(rows[-1]['record_id'], 3)

    def test_tree_roots_continuations_are_exact_and_ordered(self):
        raw = self.message(': Tree roots block your path.\r') + b'Perhaps they can be opened\r\r\nat a later time.\r\n'
        rows = self.rows(raw)

        self.assertEqual([row['rule_id'] for row in rows], ['screen.tree_roots_blocked', 'screen.tree_roots_blocked.continuation', 'screen.tree_roots_blocked.ending'])
        self.assertEqual([row['record_id'] for row in rows], [1, 1, 1])
        self.assertEqual(self.rows(b'at a later time.\r\n')[0]['status'], 'unknown')

        rows = self.rows(self.message(': Tree roots block your path.\r') + b'at a later time.\r\nPerhaps they can be opened\r\r\n')

        self.assertEqual([row['status'] for row in rows], ['recognized', 'unknown', 'unknown'])

    def test_new_screen_phrases_and_ssl_error_are_bounded(self):
        phrases = {
            'The Goddess is watching.': 'goddess_watching',
            "Your heart's desire, drenched in blood.": 'heart_desire',
            'Water without motion is but death in disguise.': 'water_motion',
            'Wah get beh?': 'wah_get_beh',
            'Feel the thrill of the void!': 'thrill_void',
            'I will unmake you!': 'unmake',
            'Sink like a stone!': 'sink_stone',
            'What divides the conqueror from the conquered?': 'conqueror',
            'The darkness looms forebodingly...': 'darkness_looms',
            'The room grows still and quiet...': 'room_quiet',
            'The drought stretches on...': 'drought',
            'Let the waters flow forth.': 'waters_flow',
            'The oppressive atmosphere slowly dissipates...': 'atmosphere_dissipates',
        }

        for text, code in phrases.items():
            with self.subTest(code = code):
                self.assertEqual(self.rows(self.message(': ' + text))[0]['type'], 'screen.phrase.' + code)
                self.assertEqual(self.rows(self.message(': ' + text + ' suffix'))[0]['status'], 'unknown')

        converted = ': Item successfully converted to an account-bound microtransaction.'

        self.assertEqual(self.rows(self.message(converted))[0]['type'], 'screen.microtransaction_converted')
        self.assertEqual(self.rows(self.message(converted + ' extra'))[0]['status'], 'unknown')

        error = "Failed to parse site settings data, exception: 'Failed to fetch site settings because: failed to process cURL request because: SSL connect error (schannel: next InitializeSecurityContext failed: SEC_E_INTERNAL_ERROR (0x80090304)'. Will retry after a period of time"
        row = self.rows(self.message(error))[0]

        self.assertEqual(row['type'], 'network.site_settings_ssl_failed')
        self.assertEqual(row['fields'], {'error_code': 'SEC_E_INTERNAL_ERROR', 'hresult': '0x80090304'})

        for invalid in (error + ' extra', error.replace('0x80090304', '0x1'), error.replace('SSL connect error', 'Something else')):
            self.assertEqual(self.rows(self.message(invalid))[0]['status'], 'unknown')

    def test_local_chat_export_in_both_languages(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'synthetic.txt'
            source.write_bytes(self.message(': SyntheticHero has joined the area.') + self.message('SyntheticHero: \x00<script>example</script>'))
            LogAnalysisService.analyze(source, root / 'analysis')

            for language, title in (('ru', 'Локальный чат'), ('en', 'Local chat')):
                entry = ReportFixture.export_report(root / 'analysis', root / language, report_language = language)
                html = (entry.parent / 'conversations/index.html').read_text()

                self.assertIn(title, html)
                self.assertIn('&lt;script&gt;example&lt;/script&gt;', html)
                self.assertNotIn('<script>example</script>', html)
                self.assertNotIn('\x00', html)
