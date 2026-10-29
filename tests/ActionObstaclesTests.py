import json
import unittest
import RemainingMonstersTests
import WindowFocusTests

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.stages.composition.analytics.ActionObstaclesBuilder import ActionObstaclesBuilder
from poe_log_analyze.stages.merging.SourceActivityEvidence import SourceActivityEvidence


class ActionObstaclesTests(unittest.TestCase):
    """Repeats are linked by source predecessors rather than equal timestamps."""

    def test_trusted_predecessors_form_series_and_forks_stay_marked(self):
        index, _ = RemainingMonstersTests.RemainingMonstersTests.fixture()
        index.evidence['events'] = index.evidence['events'][:3]

        for row in index.evidence['events']:
            row.update(code = 'screen.stash_full', previous_line = 3 if row['line'] > 3 else None)

        result = ActionObstaclesBuilder.build(index, {'rows': []})

        self.assertEqual((result['count'], len(result['groups'])), (3, 1))
        self.assertTrue(result['groups'][0]['branched'])
        self.assertIsNone(result['groups'][0]['seconds'])

        index.evidence['events'][2]['previous_line'] = 4

        result = ActionObstaclesBuilder.build(index, {'rows': []})

        self.assertFalse(result['groups'][0]['branched'])
        self.assertEqual(result['groups'][0]['seconds'], 0)

    def test_unlinked_equal_timestamps_and_gap_context_are_separate(self):
        index, _ = RemainingMonstersTests.RemainingMonstersTests.fixture()

        for row in index.evidence['events']:
            row.update(code = 'screen.item_no_room', previous_line = None)

        gap = {'session_id': '1', 'from_line': 3, 'line': 6, 'started_at': '2026-09-01T23:53:00+00:00',
               'ended_at': '2026-09-01T23:55:00+00:00', 'start': 'Synthetic start', 'end': 'Synthetic end',
               'duration': '00:02:00', 'from_href': 'events/index.html#line-2', 'to_href': 'events/index.html#line-8',
               'from_name': 'Synthetic A', 'to_name': 'Synthetic B'}

        result = ActionObstaclesBuilder.build(index, {'rows': [gap]})

        self.assertEqual(len(result['groups']), 4)
        self.assertEqual(result['unknown_context'], 1)
        self.assertEqual(result['gaps'][0]['lines'], [3, 4, 5])

    def test_source_tracker_does_not_continue_series_across_area_change(self):
        event = WindowFocusTests.WindowFocusTests.event
        rows = [event(1, '2026-09-01T00:00:00+00:00', 'area.enter', area = 'Synthetic'),
                event(2, '2026-09-01T00:00:10+00:00', 'screen.stash_full'),
                event(3, '2026-09-01T00:00:20+00:00', 'screen.stash_full'),
                event(4, '2026-09-01T00:00:30+00:00', 'area.generate'),
                event(5, '2026-09-01T00:00:40+00:00', 'screen.stash_full')]

        with TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp') as temporary:
            root = Path(temporary)
            (root / 'lines.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
            evidence = SourceActivityEvidence.read(SimpleNamespace(directory = root), list(range(6)), '1', ExecutionContext())

            self.assertEqual([row['previous_line'] for row in evidence['events']], [None, 2, None])
            self.assertIsNone(evidence['events'][-1]['entry_line'])
