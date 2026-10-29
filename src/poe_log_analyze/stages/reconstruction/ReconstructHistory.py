from pathlib import Path

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod

from poe_log_analyze.runtime.AreaKind import AreaKind

from poe_log_analyze.stages.preparation.AnalysisValidator import AnalysisValidator
from poe_log_analyze.stages.reconstruction.MapActivityBuilder import MapActivityBuilder
from poe_log_analyze.stages.reconstruction.PlaytimeBuilder import PlaytimeBuilder
from poe_log_analyze.stages.reconstruction.SourceHistory import SourceHistory


class ReconstructHistory:
    """Reconstruct each source separately before merging and renumbering."""

    def execute(self, directories: tuple[Path, ...], require_complete: bool,
                control: ExecutionContext, *, period: ReportPeriod = ReportPeriod(),
                comparison_period: ReportPeriod | None = None) -> tuple[SourceHistory, ...]:

        results = []
        zone = None

        for number, directory in enumerate(directories, 1):
            control.report(f'Reconstruct source {number} of {len(directories)}: validate analysis', force = True)

            if (directory/'collection.json').exists():
                raise ValueError('Nested collections are not supported')

            manifest_digest = AnalysisValidator.file_hash(directory / "manifest.json", control)
            data, manifest = AnalysisValidator.report_data(directory, control)

            if require_complete and not data['recognition_complete']:
                raise ValueError('Recognition is incomplete; no strict HTML report was created')

            if zone is not None and zone != data['timezone']:
                raise ValueError('Shared history requires one time zone')

            zone = data['timezone']
            digest = manifest['artifacts_sha256']['lines.jsonl']
            control.report(f'Source {number}: reconstruct maps', force = True)
            model = MapActivityBuilder.build_map_activity(directory/'lines.jsonl', zone, digest, control,
                                                        period = period, comparison_period = comparison_period)
            control.report(f'Source {number}: reconstruct other areas', force = True)
            all_areas = MapActivityBuilder.build_map_activity(directory/'lines.jsonl', zone, digest, control, include_areas = True)

            for key, day in all_areas['by_date'].items():
                extra = [run for run in day['runs'] if AreaKind.code(run) not in ('map', 'arena')]
                model['by_date'].setdefault(key, {'date': key, 'runs': [], 'seconds': 0})['runs'].extend(extra)

            control.report(f'Source {number}: measure playtime', force = True)
            activity = PlaytimeBuilder.build_activity(directory/'lines.jsonl', digest, control)
            results.append(SourceHistory(directory, data, manifest, model, activity,
                manifest_digest))

        return tuple(results)
