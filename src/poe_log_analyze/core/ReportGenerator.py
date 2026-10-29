from dataclasses import replace
from typing import Any

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.process.GenerationProcess import GenerationProcess
from poe_log_analyze.core.process.GenerationStatus import GenerationStatus
from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.plan.ReportPlan import ReportPlan
from poe_log_analyze.core.request.ReportRequest import ReportRequest
from poe_log_analyze.core.result.ReportResult import ReportResult
from poe_log_analyze.core.plan.ReportStage import ReportStage
from poe_log_analyze.core.ReportWorkspace import ReportWorkspace

from poe_log_analyze.stages.composition.ComposeReport import ComposeReport
from poe_log_analyze.stages.merging.MergeHistory import MergeHistory
from poe_log_analyze.stages.parsing.ParseLogs import ParseLogs
from poe_log_analyze.stages.preparation.PrepareInputs import PrepareInputs
from poe_log_analyze.stages.preparation.PreparedInputs import PreparedInputs
from poe_log_analyze.stages.preparation.ResultDirectories import ResultDirectories
from poe_log_analyze.stages.reconstruction.ReconstructHistory import ReconstructHistory
from poe_log_analyze.stages.rendering.RenderReport import RenderReport
from poe_log_analyze.stages.verification.VerifyReport import VerifyReport


class ReportGenerator:
    """One coordinator: explicit typed calls with a state machine enforcing their order."""

    def __init__(self, preparation: PrepareInputs | None = None, parsing: ParseLogs | None = None,
                 reconstruction: ReconstructHistory | None = None, merging: MergeHistory | None = None,
                 composition: ComposeReport | None = None, rendering: RenderReport | None = None,
                 verification: VerifyReport | None = None) -> None:

        self._preparation = preparation or PrepareInputs()
        self._parsing = parsing or ParseLogs()
        self._reconstruction = reconstruction or ReconstructHistory()
        self._merging = merging or MergeHistory()
        self._composition = composition or ComposeReport()
        self._rendering = rendering or RenderReport()
        self._verification = verification or VerifyReport()

    def generate(self, request: ReportRequest, control: ExecutionContext | None = None) -> ReportResult:
        supplied = control or ExecutionContext()
        process = GenerationProcess(ReportPlan(request.mode), supplied.state_changed)
        control = replace(supplied, on_cancel = process.request_cancel)

        process.start()

        try:
            self._begin(process, ReportStage.PREPARATION, control)
            prepared = self._preparation.execute(request, control)
            process.complete_stage(ReportStage.PREPARATION)

            with ReportWorkspace(prepared.output, request.mode, request.replace_report) as workspace:
                result = self._execute(request, prepared, workspace, process, control)
        except GenerationCancelled:
            if process.snapshot.status != GenerationStatus.CANCELLING:
                process.request_cancel()

            process.confirm_cancelled()
            raise
        except BaseException:
            process.fail()
            raise

        process.succeed()

        return result

    def _execute(self, request: ReportRequest, prepared: PreparedInputs, workspace: ReportWorkspace,
                 process: GenerationProcess, control: ExecutionContext) -> ReportResult:

        summary = None
        directories = prepared.paths

        if request.mode != ReportMode.EXPORT:
            self._begin(process, ReportStage.PARSING, control)
            parsed = self._parsing.execute(prepared.paths, workspace.analysis_directory, request, control)
            summary = parsed.summary
            directories = tuple(ResultDirectories.result_directories(parsed.directory))

            process.complete_stage(ReportStage.PARSING)

        report = None

        if request.mode != ReportMode.ANALYSIS:
            extended = request.outputs is None or request.outputs.extended or request.outputs.extended_pdf
            comparison_period = request.comparison_period if extended else None

            self._begin(process, ReportStage.RECONSTRUCTION, control)
            histories = self._reconstruction.execute(directories, request.require_complete, control,
                period = request.period, comparison_period = comparison_period)
            process.complete_stage(ReportStage.RECONSTRUCTION)

            self._begin(process, ReportStage.MERGING, control)
            unified = self._merging.execute(histories, workspace.root / "history", control, extended = extended)
            process.complete_stage(ReportStage.MERGING)

            self._begin(process, ReportStage.COMPOSITION, control)
            content = self._composition.execute(unified, control, request.report_language,
                period = request.period, comparison_period = comparison_period, extended = extended)
            process.complete_stage(ReportStage.COMPOSITION)

            self._begin(process, ReportStage.RENDERING, control)
            options: dict[str, Any] = {'outputs': request.outputs} if request.outputs is not None else {}

            if request.pdf_dark:
                options['pdf_dark'] = True

            rendered = self._rendering.execute(workspace.report_directory, content, control,
                                               request.report_language, generate_pdf = request.generate_pdf, **options)
            process.complete_stage(ReportStage.RENDERING)

            self._begin(process, ReportStage.VERIFICATION, control)
            report = self._verification.execute(rendered, histories, request.require_complete, control)
            process.complete_stage(ReportStage.VERIFICATION)

        control.check()
        process.begin_publication()

        # Once publication is accepted, cancellation cannot interrupt saving and cleanup.
        return workspace.publish(report, summary)

    @staticmethod
    def _begin(process: GenerationProcess, stage: ReportStage, control: ExecutionContext) -> None:
        control.check()
        process.begin_stage(stage)
        control.report(stage.value, force = True)
