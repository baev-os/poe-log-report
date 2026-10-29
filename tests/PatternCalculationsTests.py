import unittest
import ObservationCalculationsTests
import SourceObservationEvidenceTests

from copy import deepcopy
from datetime import date

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod

from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection
from poe_log_analyze.stages.composition.analytics.SourceSpanIndex import SourceSpanIndex
from poe_log_analyze.stages.composition.analytics.FilterHistoryBuilder import FilterHistoryBuilder
from poe_log_analyze.stages.composition.analytics.MapPoolBuilder import MapPoolBuilder
from poe_log_analyze.stages.composition.analytics.MarkerOrderBuilder import MarkerOrderBuilder
from poe_log_analyze.stages.composition.analytics.AcquisitionHistoryBuilder import AcquisitionHistoryBuilder
from poe_log_analyze.stages.composition.analytics.FaultIntervalsBuilder import FaultIntervalsBuilder


class PatternCalculationsTests(unittest.TestCase):
    """Unknown values, zeros, exact source paths, DST, and no mutations."""

    def setUp(self):
        SourceObservationEvidenceTests.SourceObservationEvidenceTests.setUp(self)

    def test_filter_failure_does_not_replace_confirmed_hash_and_boundaries_reset(self):
        helper = SourceObservationEvidenceTests.SourceObservationEvidenceTests
        events = [helper.event(1, 0, 'filter.reloaded', filter_id = 'Synthetic', result = 'true', hash = 'a'),
                  helper.event(2, 1, 'filter.reloaded', filter_id = 'Synthetic', result = 'false', hash = 'b'),
                  helper.event(3, 2, 'filter.reloaded', filter_id = 'Synthetic', result = 'true', hash = 'a'),
                  helper.event(4, 3, 'log.open'),
                  helper.event(5, 4, 'filter.reloaded', filter_id = 'Synthetic', result = 'true', hash = 'c')]
        evidence = helper.evidence(self, events)

        self.assertEqual(evidence['events'][2]['previous_filter_line'], 1)
        self.assertIsNone(evidence['events'][-1]['previous_filter_line'])

        _, _, index = ObservationCalculationsTests.ObservationCalculationsTests.fixture()
        index.evidence = evidence

        self.assertEqual([row['change'] for row in FilterHistoryBuilder.build(index)['rows']], ['first', 'unconfirmed', 'same', 'first'])

    def test_fault_clock_pid_gap_and_eof_are_censored_and_not_joined(self):
        helper = SourceObservationEvidenceTests.SourceObservationEvidenceTests

        for reason in ('pid', 'tick', 'clock', 'gap'):
            rows = [helper.event(1, 0, 'render.device_failed'), helper.event(2, 1, 'area.enter', area = 'Synthetic')]
            breaker = helper.event(3, 2, 'message.unknown')

            if reason == 'pid':
                breaker['header']['pid'] = '2'
            elif reason == 'tick':
                breaker['header']['tick'] = '1'
            elif reason == 'clock':
                breaker['timestamp'] = helper.event(3, -1, 'message.unknown')['timestamp']
            else:
                breaker['timestamp'] = helper.event(3, 4000, 'message.unknown')['timestamp']

            rows.append(breaker)
            rows.append(helper.event(4, 4001 if reason == 'gap' else 3, 'render.device_failed'))
            records = helper.evidence(self, rows)['fault_intervals']

            self.assertTrue(all(item['left_censored'] or item['right_censored'] for item in records))

    def test_source_span_filters_same_clock_other_branch_and_clips_dst(self):
        selection = ReportPeriodSelection(ReportPeriod(), 'Europe/Berlin', ExecutionContext())
        rows = [{'started_at': '2026-10-25T02:30:00+02:00', 'ended_at': '2026-10-25T02:30:00+01:00',
                 'afk_intervals': [], 'origins': [{'source': str(source), 'first_line': 1, 'last_line': 20}]}
                for source in (1, 2)]
        before = deepcopy(rows)
        result = SourceSpanIndex(rows, selection).measure({'source': '1', 'first_line': 2, 'last_line': 19}, rows[0]['started_at'], rows[0]['ended_at'])

        self.assertEqual((result['seconds'], result['elapsed_seconds'], result['clipped']), (3600, 3600, False))
        self.assertEqual(rows, before)

        selection = ReportPeriodSelection(ReportPeriod(date(2026, 9, 2), date(2026, 9, 2)), 'UTC', ExecutionContext())
        result = SourceSpanIndex([], selection).measure({'source': '1', 'first_line': 1, 'last_line': 2}, '2026-09-01T23:59:00+00:00', '2026-09-02T00:01:00+00:00')

        self.assertEqual((result['elapsed_seconds'], result['clipped'], result['seconds']), (60, True, None))

    def test_cards_preserve_names_and_zero_is_not_unknown(self):
        helper = ObservationCalculationsTests.ObservationCalculationsTests
        _, _, index = helper.fixture([helper.event(3, 'screen.card_drawn', card = 'Synthetic A'),
                                      helper.event(4, 'screen.card_drawn', card = 'Synthetic A'),
                                      helper.event(5, 'screen.items_identified', count = '0')])
        before = deepcopy(index.evidence)

        model = AcquisitionHistoryBuilder.build(index)

        self.assertEqual((model['card_count'], model['unique_cards'], model['repeated_cards']), (2, 1, 1))
        self.assertEqual(model['cards'][0]['share'], 100)
        self.assertTrue(all(row['artifact'] == '' for row in model['groups'] if row['code'] == 'screen.card_drawn'))
        self.assertEqual(model['rows'][-1]['quantity'], 0)
        self.assertEqual(index.evidence, before)

    def test_marker_repeats_returns_epochs_and_branches_keep_source_order(self):
        helper = ObservationCalculationsTests.ObservationCalculationsTests
        events = [helper.event(3, 'dialogue.named'), helper.event(4, 'dialogue.named', '2026-09-01T23:52:00+00:00')]
        events[0].update(marker_code = 'blight', marker_epoch = 3)
        events[1].update(marker_code = 'blight', marker_epoch = 3, entry_line = 7)
        _, spans, index = helper.fixture(events)
        index.contexts[7] = {**index.contexts[2], 'visit_line': 7}
        explorer = {'rows': [{'line': 2, 'name': 'Synthetic', 'excluded': []}]}

        model = MarkerOrderBuilder.build(index, explorer, spans)

        self.assertEqual((model['rows'][0]['codes'], model['rows'][0]['returned'], model['rows'][0]['same_visit']),
                         (['blight', 'blight'], True, False))

        events[1]['marker_epoch'] = 4

        self.assertEqual(MarkerOrderBuilder.build(index, explorer, spans)['rows'], [])

        events[1]['marker_epoch'] = 3
        index.contexts[7]['branched'] = True

        model = MarkerOrderBuilder.build(index, explorer, spans)

        self.assertEqual((model['rows'], model['ambiguous_maps'], len(model['signals'])), ([], 1, 2))

    def test_empty_calculations_and_cancellation(self):
        helper = ObservationCalculationsTests.ObservationCalculationsTests
        _, spans, index = helper.fixture()

        self.assertIsNone(MapPoolBuilder.build({'rows': []}, spans)['summary']['top1'])
        self.assertEqual(MarkerOrderBuilder.build(index, {'rows': []}, spans)['rows'], [])
        self.assertEqual(FilterHistoryBuilder.build(index)['rows'], [])
        self.assertEqual(FaultIntervalsBuilder.build(index, SourceSpanIndex([], spans.selection))['rows'], [])

        index.selection.control = ExecutionContext(cancelled = lambda: True)

        for builder in (FilterHistoryBuilder, AcquisitionHistoryBuilder):
            with self.assertRaises(GenerationCancelled):
                builder.build(index)

        with self.assertRaises(GenerationCancelled):
            MapPoolBuilder.build({'rows': []}, spans)

        with self.assertRaises(GenerationCancelled):
            MarkerOrderBuilder.build(index, {'rows': []}, spans)
