import json
import unittest
import MapCycleTests

from copy import deepcopy

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.stages.composition.analytics.WindowFocusBuilder import WindowFocusBuilder
from poe_log_analyze.stages.merging.SourceActivityEvidence import SourceActivityEvidence


class WindowFocusTests(unittest.TestCase):
    """Repeats do not shift Lost; unproven endings remain unknown."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @staticmethod
    def event(line, stamp, kind, **fields):
        return {'line_number': line, 'record_id': line, 'timestamp': stamp, 'type': kind,
                'status': 'recognized', 'text': 'Synthetic <event & value>', 'fields': fields}

    def evidence(self, rows):
        (self.root / 'lines.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        return SourceActivityEvidence.read(SimpleNamespace(directory = self.root), list(range(len(rows) + 1)), '1', ExecutionContext())

    def test_repeated_lost_focus_balance_and_input_preservation(self):
        evidence = self.evidence([
            self.event(1, '2026-09-01T23:50:00+00:00', 'area.enter', area = 'Synthetic'),
            self.event(2, '2026-09-01T23:51:00+00:00', 'window.focus', state = 'Lost'),
            self.event(3, '2026-09-01T23:52:00+00:00', 'window.focus', state = 'Lost'),
            self.event(4, '2026-09-01T23:56:00+00:00', 'window.focus', state = 'Gained')])
        _, spans = MapCycleTests.MapCycleTests.fixture()
        before = deepcopy(evidence)

        model = WindowFocusBuilder.build(evidence, spans)

        self.assertEqual(evidence, before)
        self.assertEqual(model['signals'], {'Lost': 2, 'Gained': 1})
        self.assertEqual((model['balance']['seconds'], model['balance']['afk_seconds']), (300, 60))
        self.assertEqual({row['kind']: row['seconds'] for row in model['zones']}, {'hideout': 60, 'map': 240})

    def test_clock_eof_orphan_and_alternatives_have_no_duration(self):
        evidence = self.evidence([
            self.event(1, '2026-09-01T23:51:00+00:00', 'window.focus', state = 'Gained'),
            self.event(2, '2026-09-01T23:52:00+00:00', 'window.focus', state = 'Lost'),
            self.event(3, '2026-09-01T23:50:00+00:00', 'area.enter', area = 'Synthetic'),
            self.event(4, '2026-09-01T23:55:00+00:00', 'window.focus', state = 'Lost')])
        _, spans = MapCycleTests.MapCycleTests.fixture()

        model = WindowFocusBuilder.build(evidence, spans)

        self.assertEqual([row['state'] for row in model['rows']], ['unmatched_gain', 'clock', 'eof'])
        self.assertTrue(all(row['choices'][0]['seconds'] is None for row in model['rows']))

        original = {'line': 2, 'end_line': 4, 'timestamp': '2026-09-01T23:51:00+00:00',
                    'ended_at': '2026-09-01T23:56:00+00:00', 'state': 'matched'}
        evidence = {'events': [], 'focus': [original, dict(original, end_line = 5, ended_at = '2026-09-02T00:00:00+00:00')]}

        self.assertEqual(WindowFocusBuilder.build(evidence, spans)['ambiguous'], 1)
        self.assertEqual(WindowFocusBuilder.build(evidence, spans)['balance']['seconds'], 0)

    def test_gap_boundary_and_missing_timestamps_are_not_paired(self):
        evidence = self.evidence([
            self.event(1, None, 'window.focus', state = 'Lost'),
            self.event(2, '2026-09-01T23:52:00+00:00', 'window.focus', state = 'Gained'),
            self.event(3, '2026-09-01T23:53:00+00:00', 'window.focus', state = 'Lost'),
            self.event(4, '2026-09-02T01:00:00+00:00', 'window.focus', state = 'Gained')])

        self.assertEqual([row['state'] for row in evidence['focus']], ['missing_time', 'gap', 'unmatched_gain'])

    def test_known_window_interval_without_play_session_remains_distinct(self):
        evidence = {'events': [], 'focus': [{'line': 2, 'end_line': 4, 'timestamp': '2026-09-01T23:51:00+00:00',
                    'ended_at': '2026-09-01T23:56:00+00:00', 'state': 'matched'}]}
        _, spans = MapCycleTests.MapCycleTests.fixture()
        spans.sessions.session = lambda line: None

        model = WindowFocusBuilder.build(evidence, spans)

        self.assertEqual(model['elapsed_seconds'], 300)
        self.assertEqual(model['elapsed_summary']['median_seconds'], 300)
        self.assertEqual(model['balance']['seconds'], 0)
        self.assertIsNone(model['rows'][0]['choices'][0]['seconds'])
