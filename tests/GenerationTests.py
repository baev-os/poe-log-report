import json
import unittest

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import FrozenInstanceError
from io import StringIO

from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from unittest.mock import patch, Mock

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.process.GenerationProcess import GenerationProcess
from poe_log_analyze.core.process.GenerationStatus import GenerationStatus
from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.plan.ReportPlan import ReportPlan
from poe_log_analyze.core.request.ReportRequest import ReportRequest
from poe_log_analyze.core.plan.ReportStage import ReportStage
from poe_log_analyze.core.ReportWorkspace import ReportWorkspace

from poe_log_analyze.cli.AnalysisCli import AnalysisCli

from poe_log_analyze.stages.preparation.AnalysisSummaryReader import AnalysisSummaryReader
from poe_log_analyze.stages.preparation.AnalysisValidator import AnalysisValidator


class GenerationTests(unittest.TestCase):
    """State transitions, real routes, and the result-saving boundary."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'synthetic.txt'
        self.source.write_bytes(b'synthetic unknown\n\n')
        self.snapshots = []
        self.terminal_staging = []
        self.addCleanup(self.assert_terminal_cleanup)
        self.stop = Event()
        self.cancel_stage = None
        self.cancel_status = None
        self.output = self.root / 'result'

    def observe(self, snapshot):
        self.snapshots.append(snapshot)

        if snapshot.status == self.cancel_status or (
            self.cancel_stage is not None and snapshot.stage is None and
            snapshot.completed and snapshot.completed[-1] == self.cancel_stage):
            self.stop.set()

        if snapshot.status in (GenerationStatus.CANCELLED, GenerationStatus.FAILED):
            self.terminal_staging.extend(self.root.glob('.pipeline-*'))

    def assert_terminal_cleanup(self):
        self.assertFalse(self.terminal_staging, "A terminal status was received before cleanup")

    def context(self):
        return ExecutionContext(cancelled = self.stop.is_set, state_changed = self.observe)

    def test_all_routes_finish_in_the_declared_order(self):
        for mode in ReportMode:
            with self.subTest(mode = mode):
                self.snapshots = []
                output = self.root / mode.value
                inputs = (self.source,) if mode != ReportMode.EXPORT else (self.root / 'analysis',)

                result = ReportGenerator().generate(ReportRequest(inputs, output, mode = mode), self.context())

                self.assertEqual(self.snapshots[-1].status, GenerationStatus.SUCCEEDED)
                self.assertEqual(self.snapshots[-1].completed, ReportPlan(mode).stages)
                self.assertEqual([s.stage for s in self.snapshots if s.stage], list(ReportPlan(mode).stages))
                self.assertTrue(result.directory.is_dir())

                if mode != ReportMode.ANALYSIS:
                    self.assertTrue(result.report_path.is_file())
                else:
                    self.source.unlink()  # Export uses saved artifacts only.

    def test_cancellation_after_each_stage_cleans_before_terminal_status(self):
        for stage in ReportStage:
            with self.subTest(stage = stage):
                self.snapshots = []
                self.stop.clear()
                self.cancel_stage = stage

                with self.assertRaises(GenerationCancelled):
                    ReportGenerator().generate(ReportRequest((self.source,), self.output), self.context())

                self.assertFalse(self.output.exists())
                self.assertFalse(list(self.root.glob('.pipeline-*')))
                self.assertEqual(self.snapshots[-1].status, GenerationStatus.CANCELLED)
                self.assertEqual(self.snapshots[-2].status, GenerationStatus.CANCELLING)
                self.assertNotIn(GenerationStatus.PUBLISHING, [s.status for s in self.snapshots])

    def test_cancel_before_start_does_no_work(self):
        self.stop.set()
        generator = ReportGenerator()

        with patch.object(generator._preparation, 'execute') as prepare:
            with self.assertRaises(GenerationCancelled):
                generator.generate(ReportRequest((self.source,), self.output), self.context())

            prepare.assert_not_called()

        self.assertEqual(self.snapshots[-1].status, GenerationStatus.CANCELLED)

    def test_failure_in_every_stage_stops_and_cleans(self):
        for name in ('preparation', 'parsing', 'reconstruction', 'merging', 'composition', 'rendering', 'verification'):
            with self.subTest(stage = name):
                self.snapshots = []
                generator = ReportGenerator()

                with patch.object(getattr(generator, '_' + name), 'execute', side_effect = RuntimeError('synthetic')):
                    with self.assertRaisesRegex(RuntimeError, 'synthetic'):
                        generator.generate(ReportRequest((self.source,), self.output), self.context())

                self.assertFalse(self.output.exists())
                self.assertEqual(self.snapshots[-1].status, GenerationStatus.FAILED)

    def test_publication_failure_is_failed_and_cleans(self):
        with patch.object(ReportWorkspace, 'publish', side_effect = OSError('synthetic')):
            with self.assertRaises(OSError):
                ReportGenerator().generate(ReportRequest((self.source,), self.output, mode = ReportMode.ANALYSIS), self.context())

        self.assertFalse(self.output.exists())
        self.assertEqual(self.snapshots[-1].status, GenerationStatus.FAILED)

    def test_cancel_after_publication_boundary_finishes_successfully(self):
        self.cancel_status = GenerationStatus.PUBLISHING

        result = ReportGenerator().generate(ReportRequest((self.source,), self.output, mode = ReportMode.ANALYSIS), self.context())

        self.assertTrue(self.stop.is_set())
        self.assertTrue((result.directory / 'lines.jsonl').is_file())
        self.assertEqual(self.snapshots[-1].status, GenerationStatus.SUCCEEDED)

    def test_publication_rejects_foreign_report(self):
        with self.assertRaises(ValueError):
            with ReportWorkspace(self.output, ReportMode.FULL) as workspace:
                workspace.analysis_directory.mkdir(parents = True)
                workspace.publish(self.source, None)

        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob('.pipeline-*')))

    def test_competing_result_is_preserved(self):
        with self.assertRaises(FileExistsError):
            with ReportWorkspace(self.output, ReportMode.ANALYSIS) as workspace:
                workspace.analysis_directory.mkdir()
                self.output.mkdir()
                (self.output / 'keep').write_text('existing')
                workspace.publish(None, None)

        self.assertEqual((self.output / 'keep').read_text(), 'existing')
        self.assertFalse(list(self.root.glob('.pipeline-*')))

    def test_fsm_rejects_skips_repeats_and_early_publication(self):
        process = GenerationProcess(ReportPlan(ReportMode.ANALYSIS))

        with self.assertRaises(RuntimeError):
            process.begin_stage(ReportStage.PREPARATION)

        process.start()

        for operation in (process.start, process.begin_publication,
                          lambda: process.begin_stage(ReportStage.PARSING),
                          lambda: process.complete_stage(ReportStage.PREPARATION)):
            with self.assertRaises(RuntimeError):
                operation()

        process.begin_stage(ReportStage.PREPARATION)

        with self.assertRaises(RuntimeError):
            process.begin_stage(ReportStage.PREPARATION)

        process.complete_stage(ReportStage.PREPARATION)

        with self.assertRaises(RuntimeError):
            process.complete_stage(ReportStage.PREPARATION)

        with self.assertRaises(RuntimeError):
            process.begin_publication()

    def test_terminal_states_are_immutable(self):
        for terminal in (GenerationStatus.CANCELLED, GenerationStatus.FAILED, GenerationStatus.SUCCEEDED):
            process = GenerationProcess(ReportPlan(ReportMode.ANALYSIS))
            process.start()

            if terminal == GenerationStatus.CANCELLED:
                process.request_cancel()
                process.confirm_cancelled()
            elif terminal == GenerationStatus.FAILED:
                process.fail()
            else:
                for stage in ReportPlan(ReportMode.ANALYSIS).stages:
                    process.begin_stage(stage)
                    process.complete_stage(stage)

                process.begin_publication()

                with self.assertRaises(RuntimeError):
                    process.request_cancel()

                process.succeed()

            snapshot = process.snapshot

            for operation in (process.start, process.request_cancel, process.confirm_cancelled,
                              process.begin_publication, process.succeed, process.fail):
                with self.assertRaises(RuntimeError):
                    operation()

                self.assertEqual(process.snapshot, snapshot)

            with self.assertRaises(FrozenInstanceError):
                snapshot.status = GenerationStatus.RUNNING

    def test_request_validates_immutable_inputs_language_and_mode(self):
        request = ReportRequest((self.source,), self.output)

        with self.assertRaises(FrozenInstanceError):
            request.timezone = 'UTC'

        for kwargs in ({'report_language': 'invalid'}, {'mode': 'invalid'}):
            with self.assertRaises(ValueError):
                ReportRequest((self.source,), self.output, **kwargs)

        with self.assertRaises(ValueError):
            ReportRequest([], self.output)
    def test_summary_reads_finished_collection_without_sources_or_writes(self):
        output = self.root / "collection"
        command = ReportRequest((self.source, self.source), output, mode = ReportMode.ANALYSIS, require_complete = True)

        created = ReportGenerator().generate(command, ExecutionContext())
        self.source.unlink()
        before = {path.relative_to(output): (path.read_bytes(), path.stat().st_mtime_ns)
                  for path in output.rglob("*") if path.is_file()}

        summary = AnalysisSummaryReader().execute(output)

        self.assertEqual(summary, created.summary)
        self.assertEqual((summary.sources, summary.total_lines, summary.unknown_lines), (2, 4, 2))
        self.assertFalse(summary.recognition_complete)

        for manifest in output.glob("sources/*/manifest.json"):
            self.assertTrue(json.loads(manifest.read_text())["parameters"]["require_complete"])

        after = {path.relative_to(output): (path.read_bytes(), path.stat().st_mtime_ns)
                 for path in output.rglob("*") if path.is_file()}

        self.assertEqual(before, after)

    def test_missing_summary_does_not_create_directory(self):
        missing = self.root / "missing"

        with self.assertRaises(FileNotFoundError):
            AnalysisSummaryReader().execute(missing)

        self.assertFalse(missing.exists())

    def test_malformed_summary_is_rejected(self):
        output = self.root / "analysis"

        ReportGenerator().generate(ReportRequest((self.source,), output, mode = ReportMode.ANALYSIS), ExecutionContext())
        path = output / "coverage.json"
        data = json.loads(path.read_text())
        data["total_lines"] = True
        path.write_text(json.dumps(data))

        with self.assertRaises(ValueError):
            AnalysisSummaryReader().execute(output)

    def test_strict_cli_keeps_diagnostics_and_returns_two(self):
        output = self.root / "strict"

        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            status = AnalysisCli.main(["--input", str(self.source), "--output", str(output), "--require-complete"])

        self.assertEqual(status, 2)
        self.assertTrue((output / "diagnostics.jsonl").is_file())
        self.assertEqual(AnalysisSummaryReader().execute(output).unknown_lines, 1)


    def test_cleanup_failure_is_failed_instead_of_cancelled(self):
        self.cancel_stage = ReportStage.PARSING
        self.original_exit = ReportWorkspace.__exit__

        with patch.object(ReportWorkspace, '__exit__', autospec = True, side_effect = self.cleanup_then_fail):
            with self.assertRaisesRegex(OSError, 'cleanup'):
                ReportGenerator().generate(ReportRequest((self.source,), self.output), self.context())

        self.assertEqual(self.snapshots[-1].status, GenerationStatus.FAILED)
        self.assertNotIn(GenerationStatus.CANCELLED, [s.status for s in self.snapshots])
        self.assertFalse(list(self.root.glob('.pipeline-*')))

    def cleanup_then_fail(self, workspace, exc_type, exc, traceback):
        self.original_exit(workspace, exc_type, exc, traceback)
        raise OSError('synthetic cleanup')

    def test_observer_failure_does_not_turn_saved_result_into_failure(self):
        with self.assertLogs('poe_log_analyze.core.process.GenerationProcess', level = 'ERROR'):
            result = ReportGenerator().generate(ReportRequest((self.source,), self.output, mode = ReportMode.ANALYSIS),
                ExecutionContext(state_changed = self.broken_observer))

        self.assertTrue((result.directory / 'lines.jsonl').is_file())

    def broken_observer(self, snapshot):
        raise RuntimeError('synthetic observer')

    def test_changed_saved_manifest_prevents_publication(self):
        saved = self.root / 'saved'

        ReportGenerator().generate(ReportRequest((self.source,), saved, mode = ReportMode.ANALYSIS))
        self.saved_manifest = saved / 'manifest.json'
        self.source.unlink()
        generator = ReportGenerator()
        self.original_render = generator._rendering.execute

        with patch.object(generator._rendering, 'execute', side_effect = self.render_then_change_manifest):
            with self.assertRaisesRegex(ValueError, 'analysis manifest changed'):
                generator.generate(ReportRequest((saved,), self.output, mode = ReportMode.EXPORT), self.context())

        self.assertFalse(self.output.exists())
        self.assertEqual(self.snapshots[-1].status, GenerationStatus.FAILED)

    def render_then_change_manifest(self, *args, **kwargs):
        rendered = self.original_render(*args, **kwargs)
        self.saved_manifest.write_text(self.saved_manifest.read_text() + '\n')

        return rendered

    def test_source_alias_preserves_canonical_label(self):
        alias = self.root / 'alias.txt'

        try:
            alias.symlink_to(self.source)
        except (OSError, NotImplementedError):
            self.skipTest("Symbolic links are unavailable")

        result = ReportGenerator().generate(ReportRequest((alias,), self.output))
        manifest = json.loads((result.directory / 'manifest.json').read_text())

        self.assertEqual(manifest['parameters']['source_label'], self.source.stem)

    def test_manifest_change_during_reconstruction_is_detected(self):
        saved = self.root / 'saved'

        ReportGenerator().generate(ReportRequest((self.source,), saved, mode = ReportMode.ANALYSIS))
        self.saved_manifest = saved / 'manifest.json'
        self.original_validation = AnalysisValidator.report_data

        with patch.object(AnalysisValidator, 'report_data', side_effect = self.validate_then_change_manifest):
            with self.assertRaisesRegex(ValueError, 'analysis manifest changed'):
                ReportGenerator().generate(ReportRequest((saved,), self.output, mode = ReportMode.EXPORT), self.context())

        self.assertFalse(self.output.exists())
        self.assertEqual(self.snapshots[-1].status, GenerationStatus.FAILED)

    def validate_then_change_manifest(self, *args, **kwargs):
        data = self.original_validation(*args, **kwargs)
        self.saved_manifest.write_text(self.saved_manifest.read_text() + '\n')

        return data

    def test_cancel_during_html_stream_cleans_partial_pages(self):
        saved = self.root / 'saved'

        ReportGenerator().generate(ReportRequest((self.source,), saved, mode = ReportMode.ANALYSIS))

        with patch('jinja2.Template.generate', self.cancelled_html_stream):
            with self.assertRaises(GenerationCancelled):
                ReportGenerator().generate(ReportRequest((saved,), self.output, mode = ReportMode.EXPORT), self.context())

        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob('.pipeline-*')))
        self.assertEqual(self.snapshots[-1].status, GenerationStatus.CANCELLED)

    def cancelled_html_stream(self, **context):
        yield '<html>'
        self.stop.set()
        yield 'отмена во время записи страницы'
