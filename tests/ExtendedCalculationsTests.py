import unittest
import ObservationCalculationsTests

from copy import deepcopy
from datetime import date

from poe_log_analyze.core.request.ReportPeriod import ReportPeriod

from poe_log_analyze.stages.composition.analytics.MemoryHistoryBuilder import MemoryHistoryBuilder
from poe_log_analyze.stages.composition.analytics.ClientEnvironmentBuilder import ClientEnvironmentBuilder
from poe_log_analyze.stages.composition.analytics.MilestoneHistoryBuilder import MilestoneHistoryBuilder
from poe_log_analyze.stages.composition.analytics.StartupHistoryBuilder import StartupHistoryBuilder


class ExtendedCalculationsTests(unittest.TestCase):
    """Numbers, units, comparability, and UTC independent of templates."""

    def test_decimal_memory_changes_units_and_undated_snapshots(self):
        fixture = ObservationCalculationsTests.ObservationCalculationsTests
        rows = [fixture.event(3, 'memory.usage', used = '0.1', used_unit = 'MB', os_used = '0', os_unit = 'GB', total = '1', total_unit = 'GB'),
                fixture.event(4, 'memory.usage', None, used = '0.3', used_unit = 'MB', os_used = '0', os_unit = 'GB', total = '1024', total_unit = 'MB')]
        rows[1]['previous_memory_line'] = 3
        _, _, index = fixture.fixture(rows)
        before = deepcopy(index.evidence)

        model = MemoryHistoryBuilder.build(index)

        self.assertEqual(model['rows'][1]['changes']['used'], .2)
        self.assertEqual(model['rows'][1]['changes']['os_used'], 0)
        self.assertIsNone(model['rows'][1]['changes']['total'])
        self.assertEqual(sum(len(row['points']) for row in model['plots']), 3)
        self.assertEqual(index.evidence, before)

    def test_environment_compares_same_destinations_with_minimum_samples(self):
        fixture = ObservationCalculationsTests.ObservationCalculationsTests
        events = []

        for revision, value in (('100', '1.5'), ('101', '2.5')):
            for number in range(5):
                event = fixture.event(len(events) + 3, 'loading.duration', area = 'Synthetic A', seconds = value)
                event['environment'] = {key: {'value': value, 'line': 1} for key, value in
                                        (('engine', '1.2.3'), ('revision', revision), ('backend', 'Vulkan'), ('driver', '1.2.3'))}
                events.append(event)

        _, _, index = fixture.fixture(events)

        model = ClientEnvironmentBuilder.build(index)

        self.assertEqual(len(model['comparisons']), 1)
        self.assertEqual(model['comparisons'][0]['difference'], 1)

        events[-1]['fields']['area'] = 'Synthetic B'

        model = ClientEnvironmentBuilder.build(index)

        self.assertEqual(len(model['comparisons']), 1)
        self.assertIsNone(model['comparisons'][0]['difference'])

        events[-2]['environment'].pop('driver')

        self.assertTrue(any(not row['comparable'] for row in ClientEnvironmentBuilder.build(index)['groups']))

    def test_startup_wall_time_uses_utc_and_clipping_excludes_summary(self):
        fixture = ObservationCalculationsTests.ObservationCalculationsTests
        events = [fixture.event(3, 'startup.stage_start', '2026-10-25T02:45:00+02:00', stage = 'Game'),
                  fixture.event(4, 'area.enter', '2026-10-25T02:45:00+01:00', area = 'Synthetic')]
        _, spans, index = fixture.fixture(events)
        index.evidence['links'] = [{'kind': 'startup', 'line': 3, 'end_line': 4,
                                   'timestamp': events[0]['timestamp'], 'ended_at': events[1]['timestamp'], 'state': 'matched'}]

        self.assertEqual(StartupHistoryBuilder.build(index, spans)['rows'][0]['seconds'], 3600)

        events[0]['timestamp'] = '2026-09-01T23:59:00+00:00'
        events[1]['timestamp'] = '2026-09-02T00:01:00+00:00'
        _, spans, index = fixture.fixture(events, period = ReportPeriod(date(2026, 9, 1), date(2026, 9, 1)))
        index.evidence['links'] = [{'kind': 'startup', 'line': 3, 'end_line': 4,
                                   'timestamp': events[0]['timestamp'], 'ended_at': events[1]['timestamp'], 'state': 'matched'}]

        model = StartupHistoryBuilder.build(index, spans)

        self.assertEqual((model['rows'][0]['seconds'], model['summary']['complete']), (120, 0))
        self.assertIn('clipped', model['rows'][0]['excluded'])
        self.assertEqual(model['slowest'], [])

    def test_clock_forms_are_separate_snapshots_without_interval_or_total(self):
        fixture = ObservationCalculationsTests.ObservationCalculationsTests
        events = [fixture.event(3, 'screen.played_time_days', days = '2', hours = '1', minutes = '0', seconds = '0'),
                  fixture.event(4, 'screen.played_time_minutes', minutes = '1', seconds = '0'),
                  fixture.event(5, 'screen.character_age_hours', hours = '49', minutes = '0', seconds = '0')]
        _, spans, index = fixture.fixture(events)

        model = MilestoneHistoryBuilder.build(index, spans)

        self.assertEqual([row['clock_seconds'] for row in model['rows']], [176400, 60, 176400])
        self.assertTrue(all(row['seconds'] is None and row['previous'] is None for row in model['rows']))
        self.assertNotIn('total', model)
