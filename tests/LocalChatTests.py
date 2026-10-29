import json
import unittest

from base64 import b64decode
from io import BytesIO

from pathlib import Path
from tempfile import TemporaryDirectory

from zoneinfo import ZoneInfo

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.stages.parsing.LogParser import LogParser


class LocalChatTests(unittest.TestCase):
    """Tagged local chat requires no name guessing and does not extend context."""

    @staticmethod
    def line(message, level = 'INFO'):
        return f'2026/09/01 12:00:00 1 abcd [{level} Client 42] {message}\r\n'.encode()

    @staticmethod
    def parse(raw):
        return list(LogParser.iter_records(BytesIO(raw), ZoneInfo('Asia/Almaty')))

    def test_tagged_message_preserves_fields_and_bytes_without_prior_character(self):
        for guild, marker in (('<TEST>', ''), ('<ТЕСТ>', '\x00')):
            raw = self.line(f'{guild} SyntheticGuest: {marker}Synthetic message: <b>example</b>')
            row = self.parse(raw)[0]

            self.assertEqual(row['type'], 'chat.local')
            self.assertEqual(row['fields'], {'guild': guild, 'character': 'SyntheticGuest',
                                            'marker': marker or None,
                                            'message': 'Synthetic message: <b>example</b>'})
            self.assertEqual(b64decode(row['raw_base64']), raw)

    def test_tag_does_not_confirm_untagged_messages_or_other_files(self):
        raw = (self.line('SyntheticGuest: before') + self.line('<TEST> SyntheticGuest: tagged')
               + self.line('SyntheticGuest: after')
               + b'2026/09/01 12:01:00 ***** LOG FILE OPENING *****\r\n'
               + self.line('SyntheticGuest: new session'))
        rows = self.parse(raw)

        self.assertEqual([row['type'] for row in rows],
                         ['message.unknown', 'chat.local', 'message.unknown', 'log.open', 'message.unknown'])
        self.assertEqual(b''.join(b64decode(row['raw_base64']) for row in rows), raw)
        self.assertEqual(self.parse(self.line('SyntheticGuest: other file'))[0]['status'], 'unknown')

    def test_malformed_tags_headers_names_controls_and_npc_signatures_are_not_chat(self):
        messages = ('<> SyntheticGuest: text', '< > SyntheticGuest: text', '<<TEST>> SyntheticGuest: text',
                    '<TEST>SyntheticGuest: text', '<TEST> Synthetic Guest: text',
                    '<TEST> 123Guest: text', '<TEST> SyntheticGuest:text',
                    '<TEST> SyntheticGuest: \x00\x00text', '<TEST> SyntheticGuest: bad\ttext',
                    '<TE\x00ST> SyntheticGuest: text', '<TEST> Faustus: text',
                    '<TEST> CreateSwapChain: text', 'UnconfirmedGuest: text')

        for message in messages:
            with self.subTest(message = message):
                self.assertEqual(self.parse(self.line(message))[0]['status'], 'unknown')

        for level in ('DEBUG', 'WARN', 'ERROR', 'CRIT'):
            with self.subTest(level = level):
                self.assertEqual(self.parse(self.line('<TEST> SyntheticGuest: text', level))[0]['status'], 'unknown')

        self.assertEqual(self.parse(b'<TEST> SyntheticGuest: no header\n')[0]['status'], 'unknown')
        self.assertEqual(self.parse(self.line('Faustus: Synthetic dialogue.'))[0]['type'], 'dialogue.named')

    def test_ru_en_export_escapes_tagged_chat_and_deduplicates_copies(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'synthetic.txt'
            original = self.line('<TEST> SyntheticGuest: \x00<script>synthetic</script>')
            source.write_bytes(original)

            for language, title in (('ru', 'Локальный чат'), ('en', 'Local chat')):
                result = ReportGenerator().generate(ReportRequest((source, source), root / language,
                                                                  report_language = language, require_complete = True))
                public = result.report_path.parent
                chats = json.loads((public.parent / 'project/data/conversations.json').read_text())

                self.assertEqual(chats['count'], 1)

                html = (public / 'conversations/index.html').read_text()

                self.assertIn(title, html)
                self.assertIn('&lt;script&gt;synthetic&lt;/script&gt;', html)
                self.assertNotIn('<script>synthetic</script>', html)
                self.assertNotIn('\x00', html)
                self.assertIn('&lt;TEST&gt;', (public / 'events/index.html').read_text())

            self.assertEqual(source.read_bytes(), original)
