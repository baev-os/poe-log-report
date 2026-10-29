from zoneinfo import ZoneInfo

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.runtime.AreaKind import AreaKind

from poe_log_analyze.stages.composition.MapFlowBuilder import MapFlowBuilder
from poe_log_analyze.stages.composition.MapRowOrdering import MapRowOrdering
from poe_log_analyze.stages.reconstruction.MapEncounterTracker import MapEncounterTracker


class MapObservationStatisticsBuilder:
    """Maps with observations: count confirmed returns and shared lines once."""

    LABELS = {**{code: 'mechanic.' + code for code in MapEncounterTracker.SPEAKERS},
              **{code: 'discovery.' + code for code in MapEncounterTracker.DISCOVERIES.values()},
              'mercenaries': 'flow.mercenaries'}

    @classmethod
    def build(cls, maps: dict, control: ExecutionContext) -> dict:
        zone = ZoneInfo(maps['timezone'])
        records = {}

        for day in maps['by_date'].values():
            for run in day['runs']:
                control.check()

                if AreaKind.code(run) != 'map':
                    continue

                # A shared renumbered entry line proves the same starting point
                # even for partially overlapping runs from divergent files.
                key = (run['area_id'], run['first_line'])
                record = records.setdefault(key, cls.record(run, zone))

                for visit in run['visits']:
                    control.check()

                    for field in ('mechanics', 'discoveries', 'mercenaries'):
                        for event in visit.get(field, []):
                            code = 'mercenaries' if field == 'mercenaries' else event['code']
                            evidence = record['observations'].setdefault(code, {})
                            evidence.setdefault(event['line'], MapFlowBuilder.event(event, zone))

        rows = list(records.values())
        rows.sort(key = lambda row: (row['entered_at'] is None,
                                  MapRowOrdering.moment(row['entered_at']).timestamp() if row['entered_at'] else 0,
                                  row['line']))

        for row in rows:
            row['observations'] = {code: [events[line] for line in sorted(events)]
                                   for code, events in row['observations'].items()}

        months, undated = cls.periods(rows)
        groups = []

        for code, label in sorted(cls.LABELS.items()):
            control.check()
            selected = [dict(row, evidence = row['observations'][code]) for row in rows if code in row['observations']]

            for row in selected:
                row.pop('observations')

            details, unknown = cls.detail_periods(selected)
            groups.append({'code': code, 'label_key': label, 'count': len(selected),
                           'months': details, 'undated': unknown})

        return {'version': '1', **cls.summary(rows), 'months': months, 'undated': undated, 'groups': groups}

    @staticmethod
    def record(run: dict, zone: ZoneInfo) -> dict:
        entered = MapRowOrdering.moment(run['started_at'])
        entered = entered.astimezone(zone) if entered else None

        return {'name': run['name'], 'area_id': run['area_id'], 'icon': run.get('icon', ''),
                'line': run['first_line'], 'entered_at': entered.isoformat() if entered else None,
                'entry': entered.strftime('%d.%m.%Y %H:%M:%S') if entered else '—',
                'date': entered.date().isoformat() if entered else 'undated',
                'identity_complete': run['identity_complete'],
                'map_href': f"technical/maps/{run['date']}/index.html#run-{run['id']}",
                'observations': {}}

    @classmethod
    def summary(cls, rows: list[dict]) -> dict:
        return {'map_count': len(rows), 'observed_maps': sum(bool(row['observations']) for row in rows),
                'unconfirmed_maps': sum(not row['identity_complete'] for row in rows),
                'rows': [{'code': code, 'label_key': label,
                          'count': sum(code in row['observations'] for row in rows),
                          'href': f'statistics/observations/{code}/index.html'}
                         for code, label in sorted(cls.LABELS.items())]}

    @classmethod
    def periods(cls, rows: list[dict]) -> tuple[list[dict], dict]:
        months, undated = cls.detail_periods(rows)

        for month in months:
            month.update(cls.summary([row for day in month['days'] for row in day['rows']]))

            for day in month['days']:
                day.update(cls.summary(day.pop('rows')))

        return months, cls.summary(undated)

    @staticmethod
    def detail_periods(rows: list[dict]) -> tuple[list[dict], list[dict]]:
        days, undated = {}, []

        for row in rows:
            if row['date'] == 'undated':
                undated.append(row)
            else:
                days.setdefault(row['date'], []).append(row)

        months = {}

        for date, records in sorted(days.items()):
            month = months.setdefault(date[:7], {'id': date[:7], 'label': date[:7], 'days': [], 'count': 0})
            month['days'].append({'date': date, 'label': '.'.join(reversed(date.split('-'))), 'rows': records})
            month['count'] += len(records)

        return list(months.values()), undated
