import json
import unittest

from copy import deepcopy

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod

from poe_log_analyze.stages.composition.DisconnectReturnBuilder import DisconnectReturnBuilder
from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection
from poe_log_analyze.stages.merging.DisconnectReturnLinks import DisconnectReturnLinks


class DisconnectReturnTests(unittest.TestCase):
    """Follow one source's sequence only; never join branches or clock rollbacks."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.selection = ReportPeriodSelection(ReportPeriod(), 'UTC', ExecutionContext())
        self.rows = {1: {'path': 'sessions/1/index.html'}}

    @staticmethod
    def session(line):
        return 1

    @staticmethod
    def event(line, stamp, kind):
        return {'line_number': line, 'timestamp': stamp, 'type': kind, 'status': 'recognized',
                'fields': {'area': 'Synthetic <Area & Name>'}}

    def links(self, rows):
        (self.root / 'lines.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        return DisconnectReturnLinks.read(SimpleNamespace(directory = self.root), list(range(len(rows) + 1)), '1', self.selection.control)

    def test_next_entry_and_repeated_disconnects(self):
        rows = [self.event(1, '2026-09-01T00:00:00+00:00', 'network.abnormal_disconnect'),
                self.event(2, '2026-09-01T00:00:10+00:00', 'network.instance_disconnect'),
                self.event(3, '2026-09-01T00:01:00+00:00', 'area.enter')]
        links = self.links(rows)
        before = deepcopy(links)

        result = DisconnectReturnBuilder.build(links, self, self.selection)

        self.assertEqual(before, links)
        self.assertEqual(result['sample_count'], 2)
        self.assertEqual(result['median_seconds'], 55)
        self.assertEqual(result['rows'][0]['choices'][0]['entry_line'], 3)

    def test_clock_missing_time_no_entry_and_long_break(self):
        links = self.links([self.event(1, '2026-09-01T00:01:00+00:00', 'network.abnormal_disconnect'),
                            self.event(2, '2026-09-01T00:00:00+00:00', 'area.enter'),
                            self.event(3, None, 'network.abnormal_disconnect'),
                            self.event(4, '2026-09-01T00:01:00+00:00', 'area.enter'),
                            self.event(5, '2026-09-01T00:02:00+00:00', 'network.abnormal_disconnect')])

        result = DisconnectReturnBuilder.build(links, self, self.selection)

        self.assertEqual([row['state'] for row in result['rows']], ['clock', 'missing_time', 'no_entry'])

        long = dict(links[0], state = 'observed', entered_at = '2026-09-01T02:00:00+00:00', entry_line = 10, area = 'Synthetic')

        result = DisconnectReturnBuilder.build([long], self, self.selection)

        self.assertEqual(result['states']['long_break'], 1)
        self.assertIsNone(result['median_seconds'])

    def test_alternative_returns_are_ambiguous_and_not_averaged(self):
        links = self.links([self.event(1, '2026-09-01T00:00:00+00:00', 'network.abnormal_disconnect'),
                            self.event(2, '2026-09-01T00:01:00+00:00', 'area.enter')])
        links.append(dict(links[0], entry_line = 5, entered_at = '2026-09-01T00:02:00+00:00'))

        result = DisconnectReturnBuilder.build(links, self, self.selection)

        self.assertEqual(result['count'], 1)
        self.assertEqual(result['states']['ambiguous'], 1)
        self.assertEqual(result['sample_count'], 0)
        self.assertEqual(len(result['rows'][0]['choices']), 2)
        self.assertEqual(DisconnectReturnBuilder.build([], self, self.selection)['count'], 0)
