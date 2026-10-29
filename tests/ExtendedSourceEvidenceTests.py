import unittest
import SourceObservationEvidenceTests


class ExtendedSourceEvidenceTests(unittest.TestCase):
    """Reset new links at actual boundaries of each source."""

    def setUp(self):
        SourceObservationEvidenceTests.SourceObservationEvidenceTests.setUp(self)

    def test_memory_milestones_and_environment_reset_on_all_boundaries(self):
        event = SourceObservationEvidenceTests.SourceObservationEvidenceTests.event

        for reason in ('process', 'clock', 'gap', 'boundary'):
            with self.subTest(reason = reason):
                rows = [event(1, 0, 'engine.version', version = '1.2.3'),
                        event(2, 1, 'memory.usage', used = '0'), event(3, 2, 'screen.quest_points', count = '1'),
                        event(4, 3, 'startup.stage_start', stage = 'Game')]
                breaker = event(5, 4, 'message.unknown')

                if reason == 'process':
                    breaker['header']['pid'] = '2'
                elif reason == 'clock':
                    breaker['header']['tick'] = '1'
                elif reason == 'gap':
                    breaker['timestamp'] = event(5, 4000, 'message.unknown')['timestamp']
                else:
                    breaker['type'] = 'log.open'

                rows.extend([breaker, event(6, 4001 if reason == 'gap' else 5, 'memory.usage', used = '1'),
                             event(7, 4002 if reason == 'gap' else 6, 'screen.quest_points', count = '2')])
                evidence = SourceObservationEvidenceTests.SourceObservationEvidenceTests.evidence(self, rows)
                memory, milestone = evidence['events'][-2:]

                self.assertIsNone(memory['previous_memory_line'])
                self.assertIsNone(milestone['previous_milestone_line'])
                self.assertEqual(memory['environment'], {})
                self.assertEqual(next(row for row in evidence['links'] if row['kind'] == 'startup')['state'], reason)

    def test_missing_times_and_eof_do_not_complete_startup(self):
        event = SourceObservationEvidenceTests.SourceObservationEvidenceTests.event
        evidence = SourceObservationEvidenceTests.SourceObservationEvidenceTests.evidence(self, [event(1, None, 'startup.stage_start', stage = 'Game'),
                                                                 event(2, 1, 'area.enter', area = 'Synthetic')])

        self.assertEqual(evidence['links'][0]['state'], 'missing_time')

        evidence = SourceObservationEvidenceTests.SourceObservationEvidenceTests.evidence(self, [event(1, 0, 'startup.stage_start', stage = 'Game')])

        self.assertEqual(evidence['links'][0]['state'], 'eof')

    def test_global_mapping_keeps_metadata_proofs_and_predecessors(self):
        event = SourceObservationEvidenceTests.SourceObservationEvidenceTests.event
        rows = [event(1, 0, 'engine.version', version = '1.2.3'), event(2, 1, 'memory.usage', used = '0'),
                event(3, 2, 'memory.usage', used = '1'), event(4, 3, 'screen.quest_points', count = '1'),
                event(5, 4, 'screen.quest_points', count = '2')]
        evidence = SourceObservationEvidenceTests.SourceObservationEvidenceTests.evidence(self, rows, [0, 11, 22, 33, 44, 55])

        self.assertEqual(evidence['events'][2]['previous_memory_line'], 22)
        self.assertEqual(evidence['events'][-1]['previous_milestone_line'], 44)
        self.assertEqual(evidence['events'][-1]['environment']['engine']['line'], 11)
