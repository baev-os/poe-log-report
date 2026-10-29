from poe_log_analyze.runtime.AreaKind import AreaKind

from poe_log_analyze.stages.composition.analytics.MeasuredSpanIndex import MeasuredSpanIndex
from poe_log_analyze.stages.composition.MapPaceBuilder import MapPaceBuilder
from poe_log_analyze.stages.composition.MapObservationStatisticsBuilder import MapObservationStatisticsBuilder
from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder


class MarkerTimingBuilder:
    """The first recorded marker is not treated as the start or end of a mechanic."""

    @classmethod
    def build(cls, original, explorer, spans, details) -> dict:
        spans.selection.control.check()
        selected = {row['line']: row for row in explorer['rows']}
        rows = []

        for run in original:
            spans.selection.control.check()

            if AreaKind.code(run) != 'map' or run['first_line'] not in selected:
                continue

            evidence = {}

            for visit in run['visits']:
                for field in ('mechanics', 'discoveries', 'mercenaries'):
                    for event in visit.get(field, []):
                        spans.selection.control.check()
                        code = 'mercenaries' if field == 'mercenaries' else event['code']
                        evidence.setdefault(code, {})[event['line']] = (event, visit)

            for code, items in sorted(evidence.items()):
                if not any(spans.selection.period.contains(event.get('timestamp'), spans.selection.zone_name)
                           for event, visit in items.values()):
                    continue

                ordered = sorted(items.values(), key = lambda pair: pair[0]['line'])
                event, visit = ordered[0]
                record = selected[run['first_line']]
                branched = bool(run.get('branched') or any(item.get('branches') for item in run['visits']))
                span, offset, visit_offset = None, None, None
                start, end = run.get('started_at'), event.get('timestamp')

                if not branched and start and end and spans.moment(end) >= spans.moment(start):
                    span = spans.measure(spans.sessions.session(run['first_line']), start, end)
                    offset = (spans.moment(end) - spans.moment(start)).total_seconds()

                    if visit.get('entered_at') and spans.moment(end) >= spans.moment(visit['entered_at']):
                        visit_offset = (spans.moment(end) - spans.moment(visit['entered_at'])).total_seconds()

                excluded = list(record['excluded'])

                if branched and 'branched' not in excluded:
                    excluded.append('branched')

                if span is None or not span['covered'] or span['overlapping']:
                    excluded.append('incomplete')

                if span is not None and span['clipped']:
                    excluded.append('clipped')

                levels = {item.get('level') for item in run['visits']}
                level = int(next(iter(levels))) if len(levels) == 1 and None not in levels else None
                rows.append({'line': run['first_line'], 'name': run['name'], 'area_id': run.get('area_id'), 'level': level,
                             'code': code, 'label_key': MapObservationStatisticsBuilder.LABELS[code],
                             'href': details['links'][str(run['first_line'])], 'first_href': None if branched else LogHistoryBuilder.line_href(event['line']),
                             'evidence': [LogHistoryBuilder.line_href(item['line']) for item, source_visit in ordered],
                             'returned': None if branched else visit['entry_line'] != run['first_line'],
                             'outside': not spans.selection.period.contains(end, spans.selection.zone_name),
                             'offset_seconds': offset, 'offset_duration': MapPaceBuilder.duration(offset),
                             'visit_offset_duration': MapPaceBuilder.duration(visit_offset), 'span': span,
                             'remaining_seconds': span['remaining_seconds'] if span else None,
                             'excluded': list(dict.fromkeys(excluded))})

        return {'version': '1', 'rows': rows, 'groups': cls.groups(rows, False), 'types': cls.groups(rows, True)}

    @staticmethod
    def groups(rows, by_type) -> list[dict]:
        groups = {}

        for row in rows:
            if by_type and (not row['area_id'] or row['level'] is None):
                continue

            key = (row['code'], row['area_id'], row['level']) if by_type else (row['code'],)
            groups.setdefault(key, []).append(row)

        return [{'code': key[0], 'label_key': records[0]['label_key'],
                 'area_id': records[0]['area_id'] if by_type else None, 'level': records[0]['level'] if by_type else None,
                 'name': records[0]['name'] if by_type else None, 'count': len(records),
                 'summary': MeasuredSpanIndex.statistics(records, 'offset_seconds'),
                 'without_afk': MeasuredSpanIndex.statistics(records, 'remaining_seconds')}
                for key, records in sorted(groups.items())]
