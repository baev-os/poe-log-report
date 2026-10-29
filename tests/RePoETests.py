"""Catalogue comparison using synthetic data without network access or game exports."""

import hashlib
import unittest

from copy import deepcopy

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import patch

from poe_log_analyze.stages.parsing.LogAnalysisService import LogAnalysisService

from poe_log_analyze.tooling.RePoEComparison import RePoEComparison

from RepoeFixture import RepoeFixture


class RePoETests(unittest.TestCase):
    """Distinguish proven keys from string matches and immutable status."""

    def test_area_id_name_ambiguity_and_observed_level(self):
        idx = RePoEComparison.indexes(RepoeFixture.tables())
        generated = RepoeFixture.row('area.generate', {'area': 'AreaA', 'level': '83'})
        before = deepcopy(generated)
        result = RePoEComparison.interpret(generated, idx)

        self.assertEqual(result['match'], 'found')
        self.assertEqual(result['log_level'], 83)
        self.assertFalse(result['default_level_matches'])
        self.assertEqual(generated, before)

        entered = RePoEComparison.interpret(RepoeFixture.row('area.enter', {'area': 'Synthetic Area'}), idx)

        self.assertEqual(entered['match'], 'ambiguous_name')
        self.assertEqual(len(entered['candidates']), 2)

    def test_passive_id_is_not_graph_hash_and_name_conflict_is_visible(self):
        idx = RePoEComparison.indexes(RepoeFixture.tables())
        result = RePoEComparison.interpret(RepoeFixture.row('passive.allocation', {'skill_id': 'skill_a', 'name': 'Old Name'}), idx)

        self.assertFalse(result['name_matches'])
        self.assertEqual(result['candidate_names'], ['New Name'])

        wrong = RePoEComparison.interpret(RepoeFixture.row('passive.allocation', {'skill_id': '123', 'name': 'New Name'}), idx)

        self.assertEqual(wrong['match'], 'missing')
        self.assertIsNone(RePoEComparison.interpret(RepoeFixture.row('action.instant_failed.field', {'action_type_id': '123'}), idx))

    def test_flavour_and_audio_candidates_do_not_recognize_unknown(self):
        idx = RePoEComparison.indexes(RepoeFixture.tables())

        for text, source in ((': Synthetic flavour', 'flavour.json'), ('Last part.', 'audio.json')):
            record = RepoeFixture.row('message.unknown', {}, status = 'unknown', text = text)
            result = RePoEComparison.interpret(record, idx)

            self.assertEqual(result['candidates'][0]['file'], source)
            self.assertNotIn('query', result)
            self.assertEqual(record['status'], 'unknown')

        record = RepoeFixture.row('message.unknown', {}, status = 'unknown', text = 'Last part. extra')

        self.assertEqual(RePoEComparison.interpret(record, idx)['match'], 'missing')

    def test_multiline_audio_requires_complete_adjacent_sequence_and_speaker(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'Client.txt'
            header = b'2026/09/01 10:00:00 1 abcd [INFO Client 42] Izaro: First part.\r\r\n'
            source.write_bytes(header + b'\r\r\nLast part.\r\n')
            LogAnalysisService.analyze(source, root / 'good')
            result = RePoEComparison.compare(root / 'good', RePoEComparison.indexes(RepoeFixture.tables()))

            self.assertEqual(result['audio_blocks'], [{'key': 'speech_key', 'first_line': 1,
                                             'last_line': 3, 'unknown_lines': []}])
            self.assertEqual(result, RePoEComparison.compare(root / 'good', RePoEComparison.indexes(RepoeFixture.tables())))

            for number, middle in enumerate((b'unrelated\n', b'\xff\n')):
                source.write_bytes(header + middle + b'Last part.\r\n')
                output = root / f'bad{number}'
                LogAnalysisService.analyze(source, output)

                self.assertEqual(RePoEComparison.compare(output, RePoEComparison.indexes(RepoeFixture.tables()))['audio_blocks'], [])

            wrong = RepoeFixture.tables()
            wrong['audio.json']['speech_key']['npcs'][0]['name'] = 'Other Speaker'

            self.assertEqual(RePoEComparison.compare(root / 'good', RePoEComparison.indexes(wrong))['audio_blocks'], [])

            ledger = root / 'good/lines.jsonl'
            ledger.write_bytes(ledger.read_bytes().replace(b'First part.', b'Other part.'))

            with self.assertRaisesRegex(ValueError, 'Registry hash'):
                RePoEComparison.compare(root / 'good', RePoEComparison.indexes(RepoeFixture.tables()))

    def test_modified_snapshot_is_rejected(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / 'data.json'
            path.write_bytes(b'{}')
            expected = hashlib.sha256(b'{}').hexdigest()

            self.assertEqual(RePoEComparison.verified_bytes(path, expected), b'{}')

            path.write_bytes(b'[]')

            with self.assertRaisesRegex(ValueError, '[Hh]ash'):
                RePoEComparison.verified_bytes(path, expected)

    def test_snapshot_download_checks_hash_and_publishes_atomically(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock = {'files': [{'path': 'data/example.json', 'url': 'https://example.test/data.json',
                              'sha256': hashlib.sha256(b'{}').hexdigest()}]}
            target = root / 'snapshot'

            with patch('poe_log_analyze.tooling.RePoEComparison.urlopen', return_value = BytesIO(b'[]')):
                with self.assertRaisesRegex(ValueError, 'Download hash'):
                    RePoEComparison.fetch_snapshot(lock, target)

            self.assertFalse(target.exists())
            self.assertFalse(list(root.glob('.repoe-*')))

            with patch('poe_log_analyze.tooling.RePoEComparison.urlopen', return_value = BytesIO(b'{}')):
                RePoEComparison.fetch_snapshot(lock, target)

            self.assertEqual((target / 'data/example.json').read_bytes(), b'{}')

            with self.assertRaises(FileExistsError):
                RePoEComparison.fetch_snapshot(lock, target)
