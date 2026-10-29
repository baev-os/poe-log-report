import json

from datetime import datetime, timezone

from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue
from poe_log_analyze.stages.reconstruction.MapActivityBuilder import MapActivityBuilder


class SourceActivityEvidence:
    """Establish event context and focus pairs before merging sources."""

    OBSTACLES = {'screen.stash_full': 'stash', 'screen.item_no_room': 'inventory',
                 'screen.apply_failed': 'application', 'screen.use_failed': 'application',
                 'screen.portals_disabled': 'portal', 'screen.area_unreachable': 'portal',
                 'screen.passage_item_required': 'access', 'screen.locked': 'access',
                 'screen.door_locked': 'access'}
    TYPES = {'window.focus', 'screen.monsters_remaining'} | OBSTACLES.keys()

    @classmethod
    def read(cls, source, mapping, source_id, control) -> dict:
        events, focus = [], []
        pending, previous, area = None, None, None
        last_obstacle = None
        last = 0

        with (source.directory / 'lines.jsonl').open('rb') as stream:
            for raw in stream:
                control.check()
                row = json.loads(raw)
                last = row['line_number']
                stamp, kind = row.get('timestamp'), row['type']
                moment = datetime.fromisoformat(stamp).astimezone(timezone.utc) if stamp else None
                own = row['status'] == 'recognized' and row.get('record_id') == last
                reason = None

                if moment is not None and previous is not None:
                    if moment < previous:
                        reason = 'clock'
                    elif (moment - previous).total_seconds() > MapActivityBuilder.DEFAULT_MAX_GAP_SECONDS:
                        reason = 'gap'

                if own and kind in MapActivityBuilder.BOUNDARIES:
                    reason = 'boundary'
                elif own and kind == 'area.enter' and not stamp:
                    reason = 'missing_time'

                if reason is not None:
                    if pending is not None:
                        focus.append(cls.close(pending, last, mapping, source_id, reason))
                        pending = None

                    area = None
                    last_obstacle = None

                if moment is not None:
                    previous = moment

                if not own:
                    continue

                if kind in ('area.generate', 'network.instance_connect'):
                    area = None
                    last_obstacle = None
                elif kind == 'area.enter':
                    area = last if stamp else None
                    last_obstacle = None

                if kind in cls.TYPES:
                    text = row.get('text') or ''
                    header = RuleCatalogue.HEADER.fullmatch(text)
                    message = header['message'] if header else text
                    predecessor = None

                    if kind in cls.OBSTACLES:
                        if (last_obstacle is not None and last_obstacle['code'] == kind and last_obstacle['text'] == message and area is not None
                                and moment is not None and last_obstacle['moment'] is not None
                                and 0 <= (moment - last_obstacle['moment']).total_seconds() <= 60):
                            predecessor = mapping[last_obstacle['line']]

                        last_obstacle = {'line': last, 'code': kind, 'moment': moment, 'text': message}

                    events.append({'line': mapping[last], 'timestamp': stamp, 'code': kind,
                                   'previous_line': predecessor,
                                   'entry_line': mapping[area] if area is not None else None,
                                   'fields': dict(row['fields']), 'text': message})

                if kind != 'window.focus':
                    continue

                if row['fields']['state'] == 'Lost':
                    if pending is None:
                        pending = {'line': last, 'timestamp': stamp}
                elif pending is not None:
                    focus.append(cls.close(pending, last, mapping, source_id,
                                           'matched' if pending['timestamp'] and stamp else 'missing_time', stamp))
                    pending = None
                else:
                    focus.append(cls.close({'line': last, 'timestamp': stamp}, last, mapping, source_id, 'unmatched_gain'))

        if pending is not None:
            focus.append(cls.close(pending, last, mapping, source_id, 'eof'))

        return {'events': events, 'focus': focus}

    @staticmethod
    def close(item, last, mapping, source_id, state, end = None) -> dict:
        return {**item, 'line': mapping[item['line']], 'end_line': mapping[last], 'ended_at': end, 'state': state,
                'origin': {'source': source_id, 'first_line': item['line'], 'last_line': last}}

    @staticmethod
    def merge(records, measurements) -> dict:
        events, groups = {}, {}

        for record in records:
            for row in record['events']:
                measurements.control.check()
                events[row['line']] = row

            for row in record['focus']:
                measurements.control.check()
                groups.setdefault(row['line'], []).append(row)

        return {'events': [events[line] for line in sorted(events)],
                'focus': [row for copies in groups.values() for row in measurements.maximal(copies)]}
