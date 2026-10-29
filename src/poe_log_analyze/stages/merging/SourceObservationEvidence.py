import json

from datetime import datetime, timezone

from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue
from poe_log_analyze.stages.parsing.TechnicalIssueClassifier import TechnicalIssueClassifier
from poe_log_analyze.stages.reconstruction.MapActivityBuilder import MapActivityBuilder
from poe_log_analyze.stages.merging.SourceFaultIntervals import SourceFaultIntervals
from poe_log_analyze.stages.reconstruction.MapEncounterTracker import MapEncounterTracker
from poe_log_analyze.stages.reconstruction.MercenaryGreetings import MercenaryGreetings


class SourceObservationEvidence:
    """Establish observation links in original source order before merging."""

    NETWORK = {'network.instance_latency', 'network.connected', 'network.resync',
               'network.abnormal_disconnect', 'network.maintenance_disconnect', 'network.instance_disconnect'}
    TREE = {'passive.allocation', 'mastery.allocated', 'settlers.gold_respec'}
    PROGRESS = {'screen.level_up', 'screen.slain', 'screen.suicide'}
    ENVIRONMENT = {'engine.version': 'engine', 'engine.build_revision': 'revision',
                   'render.start_device': 'backend', 'render.driver_version': 'driver', 'render.fallback_d3d11': 'backend'}
    STARTUP = {'startup.stage_start', 'startup.stage_duration', 'engine.lifecycle'}
    ACQUISITIONS = {'screen.items_identified', 'screen.expedition_added', 'screen.bestiary_added', 'screen.card_drawn'}
    FILTERS = {'filter.download', 'filter.status', 'filter.hash', 'filter.saved', 'filter.reloaded',
               'filter.empty_hash', 'filter.list_download', 'filter.list_status', 'filter.list_entry'}
    MILESTONES = {'screen.quest_points', 'screen.quest_contribution', 'screen.ascendancy_points',
                  'screen.resistance_reward', 'screen.kitava_affliction', 'screen.movement_reward',
                  'screen.passive_points', 'screen.level_points', 'screen.point_received',
                  'screen.points_received', 'steam.achievement'}
    CLOCKS = {'screen.played_time', 'screen.played_time_days', 'screen.played_time_minutes',
              'screen.character_age', 'screen.character_age_hours'}
    TYPES = (NETWORK | TREE | PROGRESS | STARTUP | ACQUISITIONS | MILESTONES | CLOCKS | FILTERS | set(ENVIRONMENT)
             | {'etrade.request', 'etrade.response', 'screen.area_presence', 'area.enter', 'memory.usage', 'loading.duration'})

    def __init__(self, mapping, source_id, control):
        control.check()
        self.mapping, self.source_id, self.control = mapping, source_id, control
        self.events, self.links, self.paths = [], [], []
        self.requests, self.presence, self.levels, self.deaths = {}, {}, {}, {}
        self.entries = []
        self.previous = self.pid = self.tick = self.area = None
        self.environment = {}
        self.environment_intervals = []
        self.environment_open = self.previous_line = None
        self.memory = self.milestone = self.startup = None
        self.last = 0
        self.filters = {}
        self.marker_epoch = None
        self.faults = SourceFaultIntervals(mapping, source_id, control)

    @classmethod
    def read(cls, source, mapping, source_id, control) -> dict:
        reader = cls(mapping, source_id, control)

        with (source.directory / 'lines.jsonl').open('rb') as stream:
            for raw in stream:
                control.check()
                reader.add(json.loads(raw))

        reader.reset('eof', reader.last)
        reader.faults.finish('eof')

        return {'events': reader.events, 'links': reader.links, 'paths': reader.paths,
                'environment_intervals': reader.environment_intervals, 'fault_intervals': reader.faults.rows}

    def add(self, row):
        self.faults.add(row)
        self.last = row['line_number']
        stamp, code = row.get('timestamp'), row['type']
        moment = datetime.fromisoformat(stamp).astimezone(timezone.utc) if stamp else None
        header = row.get('header') or {}
        pid, tick = header.get('pid'), int(header['tick']) if 'tick' in header else None
        own = row.get('record_id') == self.last and (row['status'] == 'recognized' or
                                                    TechnicalIssueClassifier.category(row) is not None)
        reason = None

        if pid is not None and self.pid is not None and pid != self.pid:
            reason = 'process'
        elif tick is not None and self.tick is not None and tick < self.tick:
            reason = 'clock'

        if moment is not None and self.previous is not None:
            if moment < self.previous:
                reason = 'clock'
            elif (moment - self.previous).total_seconds() > MapActivityBuilder.DEFAULT_MAX_GAP_SECONDS:
                reason = 'gap'

        if own and code in MapActivityBuilder.BOUNDARIES:
            reason = 'boundary'
        elif own and code == 'area.enter' and not stamp:
            reason = 'missing_time'

        old_area = self.area
        old_environment = dict(self.environment)

        if reason:
            if reason == 'boundary' and moment is not None and self.previous is not None:
                if 0 <= (moment - self.previous).total_seconds() <= MapActivityBuilder.DEFAULT_MAX_GAP_SECONDS:
                    self.close_environment(moment, self.last)

            self.reset(reason, self.last)

        if moment is not None:
            self.previous = moment
            self.previous_line = self.last

        if pid is not None:
            self.pid = pid

        if tick is not None:
            self.tick = tick

        if not own:
            return

        if code == 'engine.lifecycle' and row['fields'].get('stage') == 'Init':
            self.reset('boundary', self.last)

        if code in self.ENVIRONMENT:
            self.close_environment()
            key = self.ENVIRONMENT[code]
            value = ('DirectX11' if code == 'render.fallback_d3d11' else
                     row['fields'].get('backend' if key == 'backend' else 'revision' if key == 'revision' else 'version'))
            self.environment[key] = {'value': value, 'line': self.mapping[self.last]}

            if stamp:
                self.environment_open = {'started_at': stamp, 'line': self.last,
                                         'environment': {key: dict(value) for key, value in self.environment.items()}}

        issue = TechnicalIssueClassifier.category(row)
        marker = (MapEncounterTracker.BY_SPEAKER.get(row['fields'].get('speaker')) if code == 'dialogue.named'
                  else MapEncounterTracker.DISCOVERIES.get(code))

        if code == 'dialogue.named' and MercenaryGreetings.matches(row['fields'].get('speaker', ''), row['fields'].get('utterance', '')):
            marker = 'mercenaries'

        if code in ('area.generate', 'network.instance_connect', 'area.enter'):
            self.close_presence('transition', self.last)
            self.area = self.last if code == 'area.enter' and stamp else None

        if code not in self.TYPES and issue is None and marker is None:
            return

        text = row.get('text') or ''
        match = RuleCatalogue.HEADER.fullmatch(text)
        event = {'line': self.mapping[self.last], 'timestamp': stamp, 'code': code,
                 'entry_line': self.mapping[self.area] if self.area is not None else
                 self.mapping[old_area] if code in self.NETWORK and reason == 'boundary' and old_area is not None else None,
                 'text': match['message'] if match else text, 'fields': dict(row['fields']),
                 'environment': {key: dict(value) for key, value in
                                 (old_environment if reason == 'boundary' else self.environment).items()}, 'issue': issue}

        if marker is not None:
            if self.marker_epoch is None:
                self.marker_epoch = event['line']

            event.update(marker_code = marker, marker_epoch = self.marker_epoch)

        if code == 'memory.usage':
            event['previous_memory_line'] = self.mapping[self.memory] if self.memory is not None else None
            self.memory = self.last
        elif code in self.MILESTONES:
            event['previous_milestone_line'] = self.mapping[self.milestone] if self.milestone is not None else None
            self.milestone = self.last

        if code in ('filter.saved', 'filter.reloaded'):
            key = code, event['fields']['filter_id']
            event['previous_filter_line'] = self.filters.get(key)

            if code == 'filter.saved' or event['fields']['result'] == 'true':
                self.filters[key] = event['line']

        if code == 'screen.level_up':
            name = event['fields']['character']
            previous = self.levels.get(name)
            event['previous_level_line'] = self.mapping[previous['line']] if previous else None
            event['death_lines'] = [self.mapping[line] for line in self.deaths.get(name, [])]
            self.levels[name] = {'line': self.last, 'timestamp': stamp}
            self.deaths[name] = []
        elif code in ('screen.slain', 'screen.suicide'):
            self.deaths.setdefault(event['fields']['character'], []).append(self.last)

        self.events.append(event)
        item = {'line': self.last, 'timestamp': stamp, 'entry_line': event['entry_line']}

        if code.startswith('startup.') or code == 'engine.lifecycle' and event['fields'].get('stage') == 'Init':
            if self.startup is None:
                self.startup = item

        if code == 'area.enter' and self.startup is not None:
            self.close('startup', self.startup, self.last,
                       'matched' if self.startup['timestamp'] and stamp else 'missing_time', stamp)
            self.startup = None

        if code == 'etrade.request':
            self.requests.setdefault(event['fields']['request_id'], []).append(item)
        elif code == 'etrade.response':
            pending = self.requests.pop(event['fields']['request_id'], [])

            for request in pending:
                state = 'ambiguous' if len(pending) > 1 else 'matched' if request['timestamp'] and stamp else 'missing_time'
                self.close('api', request, self.last, state, stamp)

            if not pending:
                self.close('api', item, self.last, 'orphan')
        elif code == 'screen.area_presence':
            name = event['fields']['character']

            if event['fields']['action'] == 'joined':
                self.presence.setdefault(name, item)
            else:
                pending = self.presence.pop(name, None)

                if pending is None:
                    self.close('presence', item, self.last, 'orphan')
                else:
                    state = 'matched' if pending['timestamp'] and stamp and self.area is not None else 'missing_time'
                    self.close('presence', pending, self.last, state, stamp)
        elif code == 'area.enter' and stamp:
            self.entries.append(event['line'])
            self.entries = self.entries[-3:]

            for length in (2, 3):
                if len(self.entries) >= length:
                    self.paths.append(self.entries[-length:])

    def close(self, kind, item, last, state, ended_at = None):
        self.links.append({'kind': kind, 'line': self.mapping[item['line']], 'timestamp': item['timestamp'],
                           'entry_line': item['entry_line'], 'end_line': self.mapping[last], 'ended_at': ended_at,
                           'state': state, 'origin': {'source': self.source_id, 'first_line': item['line'], 'last_line': last}})

    def close_presence(self, reason, last):
        for item in self.presence.values():
            self.control.check()
            self.close('presence', item, last, reason)

        self.presence.clear()

    def reset(self, reason, last):
        self.close_presence(reason, last)
        self.close_environment()

        if self.startup is not None:
            self.close('startup', self.startup, last, reason)
            self.startup = None

        for pending in self.requests.values():
            for item in pending:
                self.control.check()
                self.close('api', item, last, reason)

        self.requests.clear()
        self.levels.clear()
        self.deaths.clear()
        self.entries.clear()
        self.environment.clear()
        self.filters.clear()
        self.marker_epoch = None
        self.memory = self.milestone = None
        self.area = None

    def close_environment(self, end = None, last = None):
        item = self.environment_open
        end = end if end is not None else self.previous
        last = last if last is not None else self.previous_line

        if item is not None and end is not None and last is not None:
            self.environment_intervals.append({
                'line': self.mapping[item['line']], 'environment': item['environment'],
                'started_at': item['started_at'], 'ended_at': end.isoformat(),
                'origin': {'source': self.source_id, 'first_line': item['line'], 'last_line': last}})

        self.environment_open = None

    @staticmethod
    def merge(records, measurements) -> dict:
        events, links, paths, environments, faults = {}, {}, set(), {}, {}

        for record in records:
            for row in record['events']:
                measurements.control.check()
                events[row['line']] = row

            for row in record['links']:
                measurements.control.check()
                links.setdefault((row['kind'], row['line']), []).append(row)

            for path in record['paths']:
                measurements.control.check()
                paths.add(tuple(path))

            for item in record.get('environment_intervals', []):
                measurements.control.check()
                environments.setdefault(item['line'], []).append(item)

            for item in record.get('fault_intervals', []):
                measurements.control.check()
                faults.setdefault((item['category'], item['line']), []).append(item)

        return {'events': [events[line] for line in sorted(events)],
                'links': [row for copies in links.values() for row in measurements.maximal(copies)],
                'paths': [list(path) for path in sorted(paths)],
                'environment_intervals': [part for copies in environments.values()
                                          for part in measurements.segments(copies, 'started_at', 'ended_at')],
                'fault_intervals': [item for copies in faults.values() for item in measurements.maximal(copies)]}
