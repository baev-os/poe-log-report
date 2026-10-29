import json
import unittest

from datetime import datetime, timedelta

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled

from poe_log_analyze.stages.merging.SourceObservationEvidence import SourceObservationEvidence


class SourceObservationEvidenceTests(unittest.TestCase):
    """Source pairs never cross processes, areas, or unknown boundaries."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @staticmethod
    def event(line, second, code, **fields):
        moment = datetime.fromisoformat('2026-09-01T23:50:00+00:00') + timedelta(seconds = second) if second is not None else None
        return {'line_number': line, 'record_id': line, 'timestamp': moment.isoformat() if moment else None,
                'status': 'recognized', 'type': code, 'fields': fields, 'text': 'Synthetic <event & text>',
                'header': {'pid': '1', 'tick': str(line)}}

    def evidence(self, rows, mapping = None, control = None):
        (self.root / 'lines.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        return SourceObservationEvidence.read(SimpleNamespace(directory = self.root),
            list(range(len(rows) + 1)) if mapping is None else mapping, '1', control or ExecutionContext())

    def test_repeated_join_and_zero_duration_api_keep_original_start(self):
        result = self.evidence([
            self.event(1, 0, 'area.enter', area = 'Synthetic'),
            self.event(2, 1, 'screen.area_presence', character = 'SyntheticVisitor', action = 'joined'),
            self.event(3, 2, 'screen.area_presence', character = 'SyntheticVisitor', action = 'joined'),
            self.event(4, 3, 'etrade.request', api_type = '1', request_id = '7'),
            self.event(5, 3, 'etrade.response', request_id = '7', error = '0', milliseconds = '0'),
            self.event(6, 4, 'screen.area_presence', character = 'SyntheticVisitor', action = 'left')])
        presence = next(row for row in result['links'] if row['kind'] == 'presence')

        self.assertEqual((presence['line'], presence['end_line'], presence['state']), (2, 6, 'matched'))
        self.assertEqual(next(row for row in result['links'] if row['kind'] == 'api')['state'], 'matched')
        self.assertEqual(len(result['events']), 6)

    def test_process_tick_clock_gap_and_log_boundaries_reset_all_chains(self):
        for reason in ('process', 'tick', 'clock', 'gap', 'boundary', 'missing_time'):
            with self.subTest(reason = reason):
                rows = [self.event(1, 0, 'area.enter', area = 'Synthetic'),
                        self.event(2, 1, 'screen.level_up', character = 'SyntheticHero', level = '88', **{'class': 'Ranger'}),
                        self.event(3, 2, 'screen.area_presence', character = 'SyntheticVisitor', action = 'joined'),
                        self.event(4, 3, 'etrade.request', api_type = '1', request_id = '7')]
                breaker = self.event(5, 4, 'message.unknown')

                if reason == 'process':
                    breaker['header']['pid'] = '2'
                elif reason == 'tick':
                    breaker['header']['tick'] = '1'
                elif reason in ('clock', 'gap'):
                    breaker['timestamp'] = self.event(5, -1 if reason == 'clock' else 4000, 'message.unknown')['timestamp']
                elif reason == 'boundary':
                    breaker['type'] = 'log.open'
                else:
                    breaker.update(type = 'area.enter', timestamp = None, fields = {'area': 'Synthetic unknown'})

                rows.append(breaker)
                rows.append(self.event(6, 4001 if reason == 'gap' else 5, 'screen.level_up',
                                       character = 'SyntheticHero', level = '89', **{'class': 'Ranger'}))
                result = self.evidence(rows)
                expected = 'clock' if reason == 'tick' else reason

                self.assertTrue(all(row['state'] == expected for row in result['links']))
                self.assertIsNone(result['events'][-1]['previous_level_line'])
                self.assertEqual(result['paths'], [])

    def test_reused_pending_id_is_ambiguous_and_completed_id_can_be_used_again(self):
        result = self.evidence([
            self.event(1, 0, 'etrade.request', api_type = '1', request_id = '7'),
            self.event(2, 1, 'etrade.request', api_type = '2', request_id = '7'),
            self.event(3, 2, 'etrade.response', request_id = '7', error = '0', milliseconds = '1'),
            self.event(4, 3, 'etrade.request', api_type = '1', request_id = '7'),
            self.event(5, 4, 'etrade.response', request_id = '7', error = '0', milliseconds = '2')])

        self.assertEqual([row['state'] for row in result['links']], ['ambiguous', 'ambiguous', 'matched'])

    def test_area_transition_closes_presence_but_preserves_api_request(self):
        result = self.evidence([
            self.event(1, 0, 'area.enter', area = 'Synthetic A'),
            self.event(2, 1, 'screen.area_presence', character = 'SyntheticVisitor', action = 'joined'),
            self.event(3, 2, 'etrade.request', api_type = '1', request_id = '7'),
            self.event(4, 3, 'area.generate', area = 'Synthetic B'),
            self.event(5, 4, 'area.enter', area = 'Synthetic B'),
            self.event(6, 5, 'etrade.response', request_id = '7', error = '0', milliseconds = '1'),
            self.event(7, 6, 'screen.area_presence', character = 'SyntheticVisitor', action = 'left')])

        self.assertEqual([row['state'] for row in result['links']], ['transition', 'matched', 'orphan'])
        self.assertEqual(result['paths'], [[1, 5]])

    def test_global_mapping_preserves_level_deaths_paths_and_unknown_ends(self):
        rows = [self.event(1, 0, 'area.enter', area = 'Synthetic A'),
                self.event(2, 1, 'screen.level_up', character = 'SyntheticHero', level = '88', **{'class': 'Ranger'}),
                self.event(3, 2, 'screen.slain', character = 'SyntheticHero'),
                self.event(4, 3, 'area.enter', area = 'Synthetic B'),
                self.event(5, 4, 'screen.level_up', character = 'SyntheticHero', level = '89', **{'class': 'Ranger'}),
                self.event(6, 5, 'area.enter', area = 'Synthetic A'),
                self.event(7, 6, 'etrade.request', api_type = '1', request_id = '7')]
        result = self.evidence(rows, [0, 11, 22, 33, 44, 55, 66, 77])
        level = next(row for row in result['events'] if row['line'] == 55)

        self.assertEqual((level['previous_level_line'], level['death_lines']), (22, [33]))
        self.assertEqual(result['paths'], [[11, 44], [44, 66], [11, 44, 66]])
        self.assertEqual((result['links'][0]['line'], result['links'][0]['state'], result['links'][0]['ended_at']), (77, 'eof', None))

    def test_unknown_time_context_and_cancelled_empty_reader(self):
        result = self.evidence([
            self.event(1, None, 'etrade.request', api_type = '1', request_id = '7'),
            self.event(2, 0, 'etrade.response', request_id = '7', error = '0', milliseconds = '1'),
            self.event(3, 1, 'screen.area_presence', character = 'SyntheticVisitor', action = 'joined'),
            self.event(4, 2, 'screen.area_presence', character = 'SyntheticVisitor', action = 'left')])

        self.assertEqual([row['state'] for row in result['links']], ['missing_time', 'missing_time'])

        with self.assertRaises(GenerationCancelled):
            self.evidence([], control = ExecutionContext(cancelled = lambda: True))
