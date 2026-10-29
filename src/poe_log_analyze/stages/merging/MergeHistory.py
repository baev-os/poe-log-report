from copy import deepcopy
from pathlib import Path
from typing import Any

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.stages.merging.SharedHistory import SharedHistory
from poe_log_analyze.stages.merging.SharedIntervals import SharedIntervals
from poe_log_analyze.stages.merging.SharedVisits import SharedVisits
from poe_log_analyze.stages.merging.SharedSessions import SharedSessions
from poe_log_analyze.stages.merging.DisconnectReturnLinks import DisconnectReturnLinks
from poe_log_analyze.stages.merging.SourceActivityEvidence import SourceActivityEvidence
from poe_log_analyze.stages.merging.SourceObservationEvidence import SourceObservationEvidence
from poe_log_analyze.stages.merging.UnifiedHistory import UnifiedHistory
from poe_log_analyze.stages.merging.UnifiedLedgerWriter import UnifiedLedgerWriter
from poe_log_analyze.stages.reconstruction.SourceHistory import SourceHistory


class MergeHistory:
    """Exclude confirmed prefixes and renumber line references."""

    def execute(self, inputs: tuple[SourceHistory, ...], scratch: Path,
                control: ExecutionContext, *, extended: bool = True) -> UnifiedHistory:

        scratch.mkdir(parents = True, exist_ok = True)
        ledger = UnifiedLedgerWriter(scratch / 'lines.jsonl', control)
        history = SharedHistory(control)
        models, sources, runs, intervals, versions = [], [], [], [], set()
        session_records = []
        disconnect_returns = []
        activity_evidence = []
        observation_evidence = []
        loading_routes = {}
        technical_context: dict[int, dict[str, Any]] = {}
        zone = inputs[0].data['timezone']

        for number, source in enumerate(inputs, 1):
            control.check()
            directory, data, manifest = source.directory, source.data, source.manifest
            model, activity, digest = deepcopy(source.model), source.activity, source.digest
            versions.add(data['rules_version'])
            selected = [run for day in model['by_date'].values() for run in day['runs']]
            selected_intervals = deepcopy(activity['intervals'])
            prefix = history.register(directory/'lines.jsonl', digest, data['input_sha256'], str(number))
            skip = prefix['lines'] if prefix else 0
            mapping = ledger.append(directory/'lines.jsonl', skip, int(prefix['same_as'])-1 if prefix else None, expected_sha256 = digest)

            if extended:
                disconnect_returns.extend(DisconnectReturnLinks.read(source, mapping, str(number), control))
                activity_evidence.append(SourceActivityEvidence.read(source, mapping, str(number), control))
                observation_evidence.append(SourceObservationEvidence.read(source, mapping, str(number), control))

            # Links were established in the source; shared loading numbers eliminate copies.
            for route in model.pop('loading_routes', []):
                control.check()
                renamed = {**route, **{key: mapping[route[key]] if route[key] is not None else None
                                      for key in ('line', 'from_line', 'to_line')}}
                loading_routes[renamed['line']] = renamed

            for context in model.pop('technical_context', []):
                control.check()
                line = mapping[context['line']]
                area = context['area']
                load = context['loading']
                item = technical_context.setdefault(line, {
                    'line': line, 'previous_line': mapping[context['previous_line']] if context['previous_line'] else None,
                    'area': {**area, 'line': mapping[area['line']]} if area else None, 'loading': {}})

                if load is not None:
                    item['loading'][mapping[load['line']]] = {**load, 'line': mapping[load['line']]}

            selected = deepcopy(selected)

            for run in selected:
                run['origin'] = {'source': str(number), 'run_id': run['id'], 'first_line': run['first_line'],
                                 'last_line': max(v['end_line'] for v in run['visits'])}
                run['uncertain_line_numbers'] = [mapping[n] for n in run['uncertain_line_numbers']]

                for key in ('first_line', 'generation_line', 'boundary_line'):
                    run[key] = mapping[run[key]]

                for visit in run['visits']:
                    visit['origin'] = {'source': str(number), 'first_line': visit['entry_line'], 'last_line': visit['end_line']}

                    for key in ('entry_line', 'generation_line', 'end_line'):
                        visit[key] = mapping[visit[key]]

                    for event in [*visit['mechanics'], *visit['death_messages'], *visit['discoveries'], *visit['mercenaries']]:
                        event['line'] = mapping[event['line']]

                    for scope in ('period_observations', 'comparison_observations'):
                        for events in visit.get(scope, {}).values():
                            for event in events:
                                event['line'] = mapping[event['line']]

                for death in run['death_messages']:
                    death['line'] = mapping[death['line']]

            for interval in selected_intervals:
                for afk in interval.get('afk_intervals', []):
                    afk['first_line'], afk['last_line'] = mapping[afk['first_line']], mapping[afk['last_line']]

                interval['origin'] = {'source': str(number), 'first_line': interval['first_line'], 'last_line': interval['last_line']}
                ranges = SharedSessions.line_ranges(mapping, interval['first_line'], interval['last_line'], control)
                interval['first_line'], interval['last_line'] = mapping[interval['first_line']], mapping[interval['last_line']]
                session_records.append({**interval, 'line_ranges': ranges})

            runs.extend(selected)
            intervals.extend(selected_intervals)

            for key in ('diagnostic_events', 'outside_entries'):
                model[key] = [{**item, 'line': mapping[item['line']]} for item in model.get(key, [])]

            models.append(model)
            sources.append({'input_sha256': data['input_sha256'], 'total_lines': data['total_lines'],
                            'skipped_prefix_lines': skip, 'artifacts_sha256': manifest['artifacts_sha256'],
                            'manifest_sha256': source.manifest_sha256})

        measurements = SharedIntervals(history)
        runs = SharedVisits(measurements).merge(runs)
        intervals = measurements.activity(intervals)
        data = ledger.coverage(zone, ', '.join(sorted(versions)))
        data.update(collection = len(inputs)>1, sources = sources, overlap = history.summary)

        return UnifiedHistory(ledger.path, ledger.ledger_hash.hexdigest(), data, models, runs, intervals, inputs,
                              sessions = SharedSessions.merge(session_records, measurements),
                              disconnect_returns = DisconnectReturnLinks.merge(disconnect_returns, measurements),
                              activity_evidence = SourceActivityEvidence.merge(activity_evidence, measurements),
                              observation_evidence = SourceObservationEvidence.merge(observation_evidence, measurements),
                              loading_routes = list(loading_routes.values()),
                              technical_context = [{**item, 'loading': list(item['loading'].values())}
                                                 for item in technical_context.values()])
