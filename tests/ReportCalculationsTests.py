"""Basic mode skips detailed calculations while preserving the same data."""

import json
import unittest
import BasicSummaryTests
import ReportVariantsTests

from contextlib import ExitStack
from datetime import date

from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import patch

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.request.ReportOutputs import ReportOutputs
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.stages.composition.ComposeReport import ComposeReport
from poe_log_analyze.stages.composition.CharacterDeathBuilder import CharacterDeathBuilder
from poe_log_analyze.stages.composition.MapPaceBuilder import MapPaceBuilder
from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection
from poe_log_analyze.stages.composition.events.BasicEventHistoryBuilder import BasicEventHistoryBuilder
from poe_log_analyze.stages.merging.MergeHistory import MergeHistory
from poe_log_analyze.stages.merging.SourceObservationEvidence import SourceObservationEvidence
from poe_log_analyze.stages.reconstruction.ReconstructHistory import ReconstructHistory
from poe_log_analyze.stages.preparation.ResultDirectories import ResultDirectories


class ReportCalculationsTests(unittest.TestCase):
    """HTML/PDF selection, slices, copies, cancellation, and complete-export compatibility."""

    @classmethod
    def setUpClass(cls):
        cls.temp = TemporaryDirectory(dir = Path('build/tmp').resolve(), prefix = 'report-calculations-')
        cls.root = Path(cls.temp.name)
        source = cls.root / 'synthetic.log'
        source.write_text(ReportVariantsTests.ReportVariantsTests.source_text() + BasicSummaryTests.BasicSummaryTests.source_text(), encoding = 'utf-8')
        branch = cls.root / 'branch.log'
        branch.write_text(source.read_text(encoding = 'utf-8') +
                          '2026/09/04 12:02:00 1 abcd [INFO Client 1] : Hero has been slain.\n' +
                          '2026/09/04 12:03:00 1 abcd [INFO Client 1] Abnormal disconnect: Synthetic end\n', encoding = 'utf-8')
        cls.analysis = ReportGenerator().generate(ReportRequest((source, source, branch), cls.root / 'analysis',
            mode = ReportMode.ANALYSIS)).directory
        source.unlink()
        branch.unlink()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def calculate(self, root, period, language, extended):
        control = ExecutionContext()
        directories = tuple(ResultDirectories.result_directories(self.analysis))
        histories = ReconstructHistory().execute(directories, False, control, period = period)
        history = MergeHistory().execute(histories, root, control, extended = extended)
        content = ComposeReport().execute(history, control, language, period = period, extended = extended)

        if not extended:
            self.assertFalse(content.event_rows.exists())
            self.assertNotIn('events', content.views)
            self.assertNotIn('map_pace', content.views)

        return content.views['basic']

    def test_basic_values_equal_full_projection_for_languages_periods_and_branches(self):
        periods = (ReportPeriod(), ReportPeriod(date(2026, 9, 1), date(2026, 9, 1)),
                   ReportPeriod(date(2026, 9, 4), date(2026, 9, 4)),
                   ReportPeriod(date(2026, 10, 1), date(2026, 10, 2)))

        for index, period in enumerate(periods):
            for language in ('ru', 'en'):
                with self.subTest(period = period, language = language):
                    root = self.root / f'parity-{index}-{language}'
                    full = self.calculate(root / 'full', period, language, True)
                    basic = self.calculate(root / 'basic', period, language, False)

                    self.assertEqual(basic, full)

    def test_all_basic_selections_skip_extended_work(self):
        methods = (
            'stages.merging.SourceActivityEvidence.SourceActivityEvidence.read',
            'stages.merging.SourceObservationEvidence.SourceObservationEvidence.read',
            'stages.merging.DisconnectReturnLinks.DisconnectReturnLinks.read',
            'stages.composition.events.EventHistoryBuilder.EventHistoryBuilder.build',
            'stages.composition.sessions.SessionHistoryBuilder.SessionHistoryBuilder.visits',
            'stages.composition.sessions.SessionTimelineBuilder.SessionTimelineBuilder.build',
            'stages.composition.MapPaceBuilder.MapPaceBuilder.build',
            'stages.composition.MapRunMetrics.MapRunMetrics.statistics',
            'stages.composition.MapExplorerBuilder.MapExplorerBuilder.build',
            'stages.composition.TimelineBuilder.TimelineBuilder.build_timeline',
            'stages.composition.PeriodComparisonBuilder.PeriodComparisonBuilder.build',
            'stages.composition.MapRunDetailsBuilder.MapRunDetailsBuilder.build',
            'stages.composition.analytics.MapPoolBuilder.MapPoolBuilder.build',
            'stages.composition.analytics.MeasurementCoverageBuilder.MeasurementCoverageBuilder.build',
            'stages.composition.AfkStatisticsBuilder.AfkStatisticsBuilder.append',
            'stages.composition.AfkStatisticsBuilder.AfkStatisticsBuilder.days',
        )

        with ExitStack() as stack:
            for method in methods:
                stack.enter_context(patch('poe_log_analyze.' + method, side_effect = AssertionError(method)))

            for mask in (1, 2, 3):
                with self.subTest(mask = mask):
                    outputs = ReportOutputs(bool(mask & 1), bool(mask & 2), False, False)

                    result = ReportGenerator().generate(ReportRequest((self.analysis,), self.root / f'basic-{mask}',
                        mode = ReportMode.EXPORT, outputs = outputs,
                        period = ReportPeriod(date(2026, 9, 1), date(2026, 9, 4)),
                        comparison_period = ReportPeriod(date(2026, 8, 1), date(2026, 8, 4))))

                    self.assertTrue(result.report_path.is_file())

    def test_each_extended_output_and_legacy_export_require_full_calculations(self):
        selections = (ReportOutputs(False, False, True, False), ReportOutputs(False, False, False, True), None)

        for index, outputs in enumerate(selections):
            with self.subTest(outputs = outputs):
                with patch.object(SourceObservationEvidence, 'read', wraps = SourceObservationEvidence.read) as evidence, \
                     patch.object(MapPaceBuilder, 'build', wraps = MapPaceBuilder.build) as pace, \
                     patch('poe_log_analyze.stages.rendering.RenderReport.RenderReport.execute',
                           side_effect = RuntimeError('Расчёты завершены')):
                    with self.assertRaisesRegex(RuntimeError, 'Расчёты завершены'):
                        ReportGenerator().generate(ReportRequest((self.analysis,), self.root / f'extended-{index}',
                            mode = ReportMode.EXPORT, outputs = outputs))

                self.assertTrue(evidence.called)
                self.assertTrue(pace.called)
                self.assertFalse((self.root / f'extended-{index}').exists())

    def test_basic_full_run_preserves_analysis_for_later_extended_export(self):
        source = self.root / 'new-synthetic.log'
        source.write_text(ReportVariantsTests.ReportVariantsTests.source_text(), encoding = 'utf-8')

        result = ReportGenerator().generate(ReportRequest((source,), self.root / 'full-basic', outputs = ReportOutputs(True, False)))
        source.unlink()
        saved = result.directory
        period = ReportPeriod()
        basic = json.loads((result.report_path.parent.parent / 'project/data/basic.json').read_text(encoding = 'utf-8'))

        histories = ReconstructHistory().execute((saved,), False, ExecutionContext())

        history = MergeHistory().execute(histories, self.root / 'later-history', ExecutionContext())

        detailed = ComposeReport().execute(history, ExecutionContext(), 'en', period = period)

        self.assertEqual(basic, detailed.views['basic'])
        self.assertIn('measurement_coverage', detailed.views)

    def cancel_on_basic_events(self, update):
        if update.stage == 'Basic report: conversations, characters, and dates':
            self.cancelled = True

    def test_cancellation_in_basic_reader_preserves_current_report(self):
        target = self.root / 'current' / 'report'
        source = self.root / 'cancel-synthetic.log'
        source.write_text(ReportVariantsTests.ReportVariantsTests.source_text(), encoding = 'utf-8')
        request = ReportRequest((source,), target, outputs = ReportOutputs(True, False), replace_report = True)

        result = ReportGenerator().generate(request)
        before = {path.relative_to(target): path.read_bytes() for path in target.rglob('*') if path.is_file()}
        self.cancelled = False

        with self.assertRaises(GenerationCancelled):
            ReportGenerator().generate(request, ExecutionContext(cancelled = lambda: self.cancelled,
                                                                 progress = self.cancel_on_basic_events))

        self.assertEqual(before, {path.relative_to(target): path.read_bytes() for path in target.rglob('*') if path.is_file()})
        self.assertTrue(result.report_path.is_file())

    def test_basic_reader_checks_registry_hash_and_line_sequence(self):
        ledger = self.root / 'changed.jsonl'
        row = {'line_number': 1, 'status': 'unknown', 'type': 'unknown', 'text': 'Synthetic', 'timestamp': None}
        ledger.write_text(json.dumps(row) + '\n', encoding = 'utf-8')
        selection = ReportPeriodSelection(ReportPeriod(), 'UTC', ExecutionContext())
        deaths = CharacterDeathBuilder([], selection)

        with self.assertRaisesRegex(ValueError, 'registry changed'):
            BasicEventHistoryBuilder.build(ledger, '0' * 64, deaths, selection)

        row['line_number'] = 3
        ledger.write_text(json.dumps(row) + '\n', encoding = 'utf-8')

        with self.assertRaisesRegex(ValueError, 'line sequence'):
            BasicEventHistoryBuilder.build(ledger, '0' * 64, deaths, selection)
