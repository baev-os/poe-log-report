import unittest
import MapCycleTests

from copy import deepcopy

from poe_log_analyze.stages.composition.analytics.ReturnProfileBuilder import ReturnProfileBuilder


class ReturnProfileTests(unittest.TestCase):
    """Returns follow source entries; first and repeated spans remain distinct."""

    @staticmethod
    def fixture(*, branched = False):
        maps, spans = MapCycleTests.MapCycleTests.fixture()
        maps[0]['visits'].append({'entry_line': 6, 'entered_at': '2026-09-02T00:00:00+00:00',
                                 'ended_at': '2026-09-02T00:05:00+00:00', 'seconds': 300, 'bounded': True})
        spans.sessions.rows[1]['branched'] = branched
        records = [{'line': 2, 'returns': 1, 'excluded': []}, {'line': 8, 'returns': 0, 'excluded': []}]
        details = {'links': {'2': 'maps/runs/2/index.html', '6': 'maps/runs/2/index.html', '8': 'maps/runs/8/index.html'}}
        hideout = {'first_line': 4, 'name': 'Synthetic Hideout', 'area_id': 'HideoutOssuary', 'kind_code': 'hideout',
                   'visits': [{'entry_line': 4}]}
        afk = {'by_visit': {str(line): {'seconds': 300, 'afk_seconds': 0, 'remaining_seconds': 300,
                                       'duration': '00:05:00', 'afk_duration': '00:00:00', 'remaining_duration': '00:05:00'}
                            for line in (2, 6)}}

        return maps, spans, records, details, hideout, afk

    def test_return_distribution_time_and_intermediate_areas(self):
        maps, spans, records, details, hideout, afk = self.fixture()
        before = deepcopy(maps)

        result = ReturnProfileBuilder.build(maps + [hideout], maps, {'rows': records}, spans, afk, details)

        self.assertEqual(maps, before)
        self.assertEqual((result['returned_count'], result['share']), (1, 50))
        self.assertEqual((result['first']['seconds'], result['returned']['seconds']), (300, 300))
        self.assertEqual(result['episodes'][0]['via'][0]['name'], 'Synthetic Hideout')
        self.assertEqual(result['episodes'][0]['span']['seconds'], 300)
        self.assertEqual(result['modes']['without_afk']['returned']['median_seconds'], 300)

    def test_branched_route_is_unknown_and_empty_profile_is_valid(self):
        maps, spans, records, details, hideout, afk = self.fixture(branched = True)

        result = ReturnProfileBuilder.build(maps + [hideout], maps, {'rows': records}, spans, afk, details)

        self.assertIsNone(result['episodes'][0]['span'])
        self.assertEqual(result['episodes'][0]['via'], [])

        empty = ReturnProfileBuilder.build([], [], {'rows': []}, spans, afk, {'links': {}})

        self.assertIsNone(empty['share'])
