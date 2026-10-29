import unittest
import MapCycleTests

from poe_log_analyze.stages.composition.analytics.SessionEdgesBuilder import SessionEdgesBuilder


class SessionEdgesTests(unittest.TestCase):
    """Original boundaries, confirmed endings, and sessions without maps."""

    @staticmethod
    def fixture(*, incomplete = False):
        maps, spans = MapCycleTests.MapCycleTests.fixture()
        spans.sessions.rows[1].update(start = 'Synthetic start', branches = [{
            'started_at': '2026-09-01T23:50:00+00:00', 'ended_at': '2026-09-02T00:10:00+00:00',
            'incomplete': incomplete, 'reason': 'eof' if incomplete else 'game.closing'}])

        return maps[:1], spans

    def test_first_and_last_edges_and_area_distribution(self):
        maps, spans = self.fixture()

        result = SessionEdgesBuilder.build(maps, spans)

        self.assertEqual(result['leading']['median_seconds'], 0)
        self.assertEqual(result['trailing']['median_seconds'], 900)
        self.assertEqual(result['rows'][0]['trailing']['zones'][0]['kind'], 'hideout')
        self.assertEqual(result['no_map_sessions'], 0)

    def test_eof_missing_exit_branch_and_no_maps(self):
        maps, spans = self.fixture(incomplete = True)

        result = SessionEdgesBuilder.build(maps, spans)

        self.assertIsNone(result['trailing']['median_seconds'])
        self.assertIn('incomplete', result['rows'][0]['trailing']['excluded'])

        maps[0]['visits'][0]['bounded'] = False

        self.assertIsNone(SessionEdgesBuilder.build(maps, spans)['rows'][0]['trailing'])
        self.assertEqual(SessionEdgesBuilder.build([], spans)['no_map_sessions'], 1)

        spans.sessions.rows[1]['branched'] = True

        self.assertEqual(SessionEdgesBuilder.build(maps, spans)['branched_sessions'], 1)
