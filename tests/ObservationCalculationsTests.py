import unittest
import MapCycleTests

from copy import deepcopy
from datetime import date

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod

from poe_log_analyze.stages.composition.analytics.AreaPresenceBuilder import AreaPresenceBuilder
from poe_log_analyze.stages.composition.analytics.AreaRoutePatternsBuilder import AreaRoutePatternsBuilder
from poe_log_analyze.stages.composition.analytics.LevelProgressBuilder import LevelProgressBuilder
from poe_log_analyze.stages.composition.analytics.MarkerTimingBuilder import MarkerTimingBuilder
from poe_log_analyze.stages.composition.analytics.NetworkHealthBuilder import NetworkHealthBuilder
from poe_log_analyze.stages.composition.analytics.ObservationSamples import ObservationSamples
from poe_log_analyze.stages.composition.analytics.PassiveHistoryBuilder import PassiveHistoryBuilder
from poe_log_analyze.stages.composition.analytics.RecordedActivityIndex import RecordedActivityIndex
from poe_log_analyze.stages.composition.analytics.TradeApiBuilder import TradeApiBuilder


class ObservationCalculationsTests(unittest.TestCase):
    """Zeros, unknown values, period, DST, and exclusions in new projections."""

    @staticmethod
    def event(line, code, stamp = '2026-09-01T23:51:00+00:00', **fields):
        return {'line': line, 'timestamp': stamp, 'code': code, 'fields': fields,
                'entry_line': 2, 'text': 'Synthetic <message & text>'}

    @staticmethod
    def fixture(events = (), *, period = ReportPeriod(), marked = True):
        maps, spans = MapCycleTests.MapCycleTests.fixture(period, marked = marked)
        evidence = {'events': list(events), 'links': [], 'paths': []}
        index = RecordedActivityIndex(evidence, maps, {'links': {}}, spans.sessions, spans.selection)

        return maps, spans, index

    def test_numeric_samples_zero_empty_and_nearest_rank(self):
        stats = ObservationSamples.build([None, 0, 10, 20])

        self.assertEqual((stats['count'], stats['min'], stats['median'], stats['p95']), (3, 0, 10, 20))
        self.assertEqual(ObservationSamples.build(range(1, 21))['p95'], 19)
        self.assertFalse(ObservationSamples.build(range(20))['small_sample'])
        self.assertIsNone(ObservationSamples.build([])['median'])

    def test_network_types_and_resync_units_remain_separate_without_input_mutation(self):
        events = [self.event(3, 'network.instance_latency', milliseconds = '0'),
                  self.event(4, 'network.connected', milliseconds = '500', host = 'synthetic.invalid'),
                  self.event(5, 'network.resync', value = '99')]
        _, _, index = self.fixture(events)
        before = deepcopy(index.evidence)

        model = NetworkHealthBuilder.build(index)

        self.assertEqual(before, index.evidence)

        stats = {row['code']: row for row in model['summaries']}

        self.assertEqual(stats['network.instance_latency']['stats']['median'], 0)
        self.assertEqual(stats['network.connected']['stats']['median'], 500)
        self.assertEqual(stats['network.resync']['stats']['count'], 0)
        self.assertEqual(sum(row['count'] for row in model['days']), 3)

    def test_passive_operations_keep_repeat_messages_and_gold_observations(self):
        events = [self.event(3, 'passive.allocation', skill_id = 'Synthetic', name = 'Synthetic', operation = 'allocated'),
                  self.event(4, 'passive.allocation', skill_id = 'Synthetic', name = 'Synthetic', operation = 'allocated'),
                  self.event(5, 'passive.allocation', skill_id = 'Synthetic', name = 'Synthetic', operation = 'unallocated'),
                  self.event(6, 'settlers.gold_respec', allocated = '5', gold = '100')]
        _, _, index = self.fixture(events)

        model = PassiveHistoryBuilder.build(index)

        self.assertEqual((model['summary']['allocated'], model['summary']['delta'], model['summary']['gold_records']), (2, 1, 1))
        self.assertEqual(len(model['nodes'][0]['evidence']), 3)
        self.assertNotIn('gold_spent', model)

    def test_marker_original_first_return_and_unknown_afk(self):
        maps, spans, _ = self.fixture(marked = False)
        maps[0]['visits'][0].update(level = 80, mechanics = [{'line': 3, 'code': 'blight', 'timestamp': '2026-09-01T23:51:00+00:00'}])
        maps[0]['visits'].append({'entry_line': 5, 'entered_at': '2026-09-01T23:56:00+00:00', 'level': 80,
                                 'mechanics': [{'line': 6, 'code': 'bestiary', 'timestamp': '2026-09-01T23:58:00+00:00'}]})
        explorer = {'rows': [{'line': 2, 'excluded': []}]}

        model = MarkerTimingBuilder.build(maps, explorer, spans, {'links': {'2': 'maps/runs/2/index.html'}})
        records = {row['code']: row for row in model['rows']}

        self.assertEqual((records['blight']['offset_seconds'], records['bestiary']['offset_seconds']), (60, 480))
        self.assertTrue(records['bestiary']['returned'])
        self.assertIsNone(records['blight']['remaining_seconds'])

        maps[0]['branched'] = True

        self.assertTrue(all(row['offset_seconds'] is None for row in MarkerTimingBuilder.build(maps, explorer, spans,
                            {'links': {'2': 'maps/runs/2/index.html'}})['rows']))

    def test_routes_distinguish_type_loop_from_same_instance_and_clipped_median(self):
        events = [self.event(2, 'area.enter', '2026-09-01T23:50:00+00:00', area = 'Synthetic A'),
                  dict(self.event(4, 'area.enter', '2026-09-01T23:55:00+00:00', area = 'Synthetic B'), entry_line = 4),
                  dict(self.event(8, 'area.enter', '2026-09-02T00:10:00+00:00', area = 'Synthetic A'), entry_line = 8)]
        _, spans, index = self.fixture(events, period = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2)))
        context = index.contexts[2]
        index.contexts[4] = dict(context, area_id = 'HideoutOssuary', run_line = 4, visit_line = 4, name = 'Synthetic B')
        index.contexts[8] = dict(context, run_line = 8, visit_line = 8)
        index.evidence['paths'] = [[2, 4], [4, 8], [2, 4, 8]]

        model = AreaRoutePatternsBuilder.build(index, spans)

        self.assertEqual((model['edge_count'], model['chain_count'], model['loop_count'], model['same_instance_count']), (1, 1, 1, 0))
        self.assertTrue(all('clipped' in row['excluded'] for row in model['rows']))

        index.contexts[8]['run_line'] = 2

        self.assertEqual(AreaRoutePatternsBuilder.build(index, spans)['same_instance_count'], 1)

        index.contexts[8]['identity_complete'] = False

        model = AreaRoutePatternsBuilder.build(index, spans)

        self.assertEqual(model['same_instance_count'], 0)
        self.assertTrue(all('identity' in row['excluded'] for row in model['rows']))

    def test_api_orphan_unknown_and_alternatives_excluded_from_samples(self):
        events = [self.event(3, 'etrade.request', api_type = '1', request_id = '7'),
                  self.event(4, 'etrade.response', request_id = '7', error = '0', milliseconds = '0'),
                  self.event(5, 'etrade.response', request_id = '7', error = '4', milliseconds = '900')]
        _, spans, index = self.fixture(events)
        link = {'kind': 'api', 'line': 3, 'end_line': 4, 'timestamp': events[0]['timestamp'],
                'ended_at': events[1]['timestamp'], 'state': 'matched'}
        index.evidence['links'] = [link]

        self.assertEqual(TradeApiBuilder.build(index, spans)['summary']['min'], 0)

        index.evidence['links'].append(dict(link, end_line = 5))

        self.assertEqual(TradeApiBuilder.build(index, spans)['summary']['count'], 0)
        self.assertEqual(TradeApiBuilder.build(index, spans)['rows'][0]['state'], 'ambiguous')

    def test_progress_exact_levels_gaps_repeats_and_source_death_links(self):
        events = [self.event(3, 'screen.level_up', character = 'SyntheticHero', level = '88', **{'class': 'Ranger'}),
                  self.event(5, 'screen.level_up', '2026-09-01T23:52:00+00:00', character = 'SyntheticHero', level = '89', **{'class': 'Ranger'})]
        events[1].update(previous_level_line = 3, death_lines = [4])
        _, spans, index = self.fixture(events)
        row = LevelProgressBuilder.build(index, spans)['rows'][1]

        self.assertEqual((row['state'], row['wall_seconds'], len(row['death_hrefs'])), ('consecutive', 60, 1))

        for level, state in (('88', 'repeated'), ('90', 'gap'), ('87', 'reset')):
            events[1]['fields']['level'] = level

            self.assertEqual(LevelProgressBuilder.build(index, spans)['rows'][1]['state'], state)

        events[1]['fields']['class'] = 'Witch'

        self.assertEqual(LevelProgressBuilder.build(index, spans)['rows'][1]['state'], 'class_changed')

    def test_progress_dst_uses_utc_and_clipped_period_does_not_shift_source(self):
        events = [self.event(3, 'screen.level_up', '2026-10-25T02:45:00+02:00', character = 'SyntheticHero', level = '88', **{'class': 'Ranger'}),
                  self.event(4, 'screen.level_up', '2026-10-25T02:45:00+01:00', character = 'SyntheticHero', level = '89', **{'class': 'Ranger'})]
        events[1]['previous_level_line'] = 3
        _, spans, index = self.fixture(events)

        self.assertEqual(LevelProgressBuilder.build(index, spans)['rows'][1]['wall_seconds'], 3600)

    def test_presence_clips_observed_interval_and_keeps_unknown_end(self):
        events = [self.event(3, 'screen.area_presence', '2026-09-01T23:59:00+00:00', character = 'SyntheticVisitor', action = 'joined'),
                  self.event(5, 'screen.area_presence', '2026-09-02T00:01:00+00:00', character = 'SyntheticVisitor', action = 'left')]
        _, spans, index = self.fixture(events, period = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2)))
        link = {'kind': 'presence', 'line': 3, 'end_line': 5, 'timestamp': events[0]['timestamp'],
                'ended_at': events[1]['timestamp'], 'state': 'matched'}
        index.evidence['links'] = [link]

        model = AreaPresenceBuilder.build(index, spans)

        self.assertEqual((model['joined_count'], model['left_count'], model['rows'][0]['seconds']), (0, 1, 60))
        self.assertEqual(model['summary']['complete'], 0)

        index.evidence['links'] = [dict(link, timestamp = events[1]['timestamp'], ended_at = None, state = 'eof')]

        model = AreaPresenceBuilder.build(index, spans)

        self.assertIsNone(model['rows'][0]['seconds'])

    def test_empty_models_and_cancelled_builders(self):
        maps, spans, index = self.fixture()

        self.assertEqual(NetworkHealthBuilder.build(index)['rows'], [])
        self.assertEqual(PassiveHistoryBuilder.build(index)['nodes'], [])
        self.assertEqual(MarkerTimingBuilder.build([], {'rows': []}, spans, {'links': {}})['rows'], [])
        self.assertEqual(AreaRoutePatternsBuilder.build(index, spans)['rows'], [])
        self.assertEqual(TradeApiBuilder.build(index, spans)['rows'], [])
        self.assertEqual(LevelProgressBuilder.build(index, spans)['rows'], [])
        self.assertEqual(AreaPresenceBuilder.build(index, spans)['rows'], [])

        spans.selection.control = ExecutionContext(cancelled = lambda: True)

        for builder in (NetworkHealthBuilder, PassiveHistoryBuilder, AreaRoutePatternsBuilder,
                        TradeApiBuilder, LevelProgressBuilder, AreaPresenceBuilder):
            with self.assertRaises(GenerationCancelled):
                builder.build(index) if builder in (NetworkHealthBuilder, PassiveHistoryBuilder) else builder.build(index, spans)

        with self.assertRaises(GenerationCancelled):
            MarkerTimingBuilder.build([], {'rows': []}, spans, {'links': {}})
