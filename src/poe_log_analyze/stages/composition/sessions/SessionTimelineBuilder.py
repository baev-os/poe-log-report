from datetime import datetime
from decimal import Decimal

from poe_log_analyze.runtime.AreaKind import AreaKind

from poe_log_analyze.stages.composition.ActivityAreaGroups import ActivityAreaGroups
from poe_log_analyze.stages.composition.AreaDetailsBuilder import AreaDetailsBuilder
from poe_log_analyze.stages.composition.MapPaceBuilder import MapPaceBuilder
from poe_log_analyze.stages.composition.VisitMeasurements import VisitMeasurements
from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder


class SessionTimelineBuilder:
    """Observation timeline without reconstructing unknown boundaries or summing loading times."""

    CATEGORIES = ('map', 'hideout', 'town', 'special', 'other')

    @staticmethod
    def moment(stamp: str) -> float:
        return datetime.fromisoformat(stamp).timestamp()

    @staticmethod
    def category(run: dict) -> str:
        kind = AreaKind.code(run)
        group = ActivityAreaGroups.classify(run.get('area_id', ''))

        if group and group not in ('maps', 'hideout', 'acts'):
            return 'special'

        return kind if kind in ('map', 'hideout', 'town') else 'other'

    @classmethod
    def build(cls, model: dict, runs: list[dict], intervals: list[dict], loading: dict, sessions, selection,
              *, afk: dict | None = None) -> None:

        visits, activity, loads = {}, {}, {}

        for run in runs:
            selection.control.check()

            for visit in run['visits']:
                first = sessions.session(visit['entry_line'])
                visits.setdefault(str(first), []).append((run, visit))

        for part in intervals:
            activity.setdefault(str(part['first_line']), []).append(part)

        for row in loading['rows']:
            loads.setdefault(row['session_id'], []).append(row)

        afk_rows = {}

        for row in afk['rows'] if afk else []:
            afk_rows.setdefault(row['session_id'], []).append(row)

        for session in model['rows']:
            selection.control.check()
            session['timeline'] = cls.chart(session, visits.get(session['id'], []), activity.get(session['id'], []),
                                            loads.get(session['id'], []), selection, afk_rows.get(session['id'], []))

    @classmethod
    def chart(cls, session: dict, visits: list, intervals: list[dict], loads: list[dict], selection,
              afk_rows: list[dict] | None = None) -> dict:

        start, end = cls.moment(session['started_at']), cls.moment(session['ended_at'])
        areas, loading, events, observed = [], [], {}, []
        totals = dict.fromkeys(cls.CATEGORIES, 0)
        undated = 0

        for run, visit in visits:
            selection.control.check()
            category = cls.category(run)
            totals[category] += VisitMeasurements.seconds(visit)
            href = AreaDetailsBuilder.path(AreaDetailsBuilder.key(run)) + '#visit-' + str(visit['entry_line'])

            for part in VisitMeasurements.drawable(visit):
                stamp = part.get('entered_at') or part.get('ended_at')

                if not stamp:
                    undated += 1
                    continue

                item = cls.item(start, end, cls.moment(stamp), cls.moment(part['ended_at']) if part.get('ended_at') else None,
                                selection, category = category, name = run['name'], label_key = None, href = href,
                                line = visit['entry_line'], seconds = part.get('seconds'))

                if item is not None:
                    areas.append(item)

            for field, prefix in (('mechanics', 'mechanic.'), ('discoveries', 'discovery.'), ('mercenaries', 'flow.')):
                for event in visit.get(field, []):
                    label = prefix + ('mercenaries' if field == 'mercenaries' else event['code'])
                    events.setdefault(event['line'], {'timestamp': event.get('timestamp'), 'label_key': label,
                                                     'name': event.get('speaker', '')})

        for item in session['events']:
            event = item['event']
            events[event['line_number']] = {'timestamp': event['timestamp'], 'label_key': 'event_title.' + event['type'],
                                            'name': '', 'event': event}

        for branch in session['branches']:
            # EOF and gaps mark the end of observations, not a proven player exit.
            if selection.period.contains(branch['ended_at'], selection.zone_name):
                events.setdefault(branch['last_line'], {'timestamp': branch['ended_at'],
                    'label_key': 'session_end.' + branch['reason'], 'name': ''})

        for row in loads:
            selection.control.check()

            if not row['timestamp']:
                undated += 1
                continue

            right = cls.moment(row['timestamp'])
            item = cls.item(start, end, right - float(Decimal(row['seconds'])), right, selection,
                            category = 'loading', name = row['area'], label_key = 'sessions.loading',
                            href = row['href'], line = row['line'], seconds = float(Decimal(row['seconds'])))

            if item is not None:
                loading.append(item)

        markers = []

        for line, event in events.items():
            selection.control.check()

            if not event['timestamp']:
                undated += 1
                continue

            item = cls.item(start, end, cls.moment(event['timestamp']), None, selection,
                            category = 'event', href = LogHistoryBuilder.line_href(line), line = line,
                            label_key = event['label_key'], name = event['name'], seconds = None)

            if item is not None:
                if 'event' in event:
                    item['event'] = event['event']

                markers.append(item)

        for part in intervals:
            item = cls.item(start, end, cls.moment(part['started_at']), cls.moment(part['ended_at']), selection)

            if item is not None:
                observed.append(item)

        afk = []

        for row in afk_rows or []:
            selection.control.check()
            item = cls.item(start, end, cls.moment(row['entered_at']), cls.moment(row['ended_at']), selection,
                            category = 'afk', name = row['name'], label_key = 'afk.marked', href = row['href'],
                            line = row['line'], seconds = row['seconds'])

            if item is not None:
                afk.append(item)

        tracks, y = [], 85

        for code, items in (('areas', areas), ('afk', afk), ('loading', loading), ('events', markers)):
            selection.control.check()
            lanes = cls.lanes(items)
            height = max(1, lanes) * 22 + 35
            tracks.append({'code': code, 'y': y, 'height': height, 'items': items})
            y += height

        measured = sum(totals.values())
        unallocated = session['seconds'] - measured
        breakdown = [{'code': code, 'seconds': seconds, 'duration': MapPaceBuilder.duration(seconds),
                      'share': seconds * 100 / measured if measured else 0} for code, seconds in totals.items()]
        ticks = []

        for index in range(7 if end > start else 1):
            fraction = index / 6 if end > start else .5
            ticks.append({'x': 70 + 860 * fraction, 'label': cls.label(start + (end - start) * fraction, selection)})

        return {'version': '2', 'start': start, 'end': end, 'height': y + 10, 'tracks': tracks,
                'observed': observed, 'ticks': ticks, 'breakdown': breakdown, 'undated': undated,
                'area_duration': MapPaceBuilder.duration(measured),
                'unallocated': MapPaceBuilder.duration(unallocated if unallocated >= 0 else None)}

    @staticmethod
    def label(moment: float, selection) -> str:
        return datetime.fromtimestamp(moment, selection.zone).strftime('%d.%m.%Y %H:%M:%S %z')

    @classmethod
    def item(cls, start: float, end: float, left: float, right: float | None, selection, **fields) -> dict | None:
        stop = right if right is not None else left

        if stop < start or left > end:
            return None

        begin, finish = max(start, left), min(end, stop)
        low = (begin - start) / (end - start) if end > start else .5
        high = (finish - start) / (end - start) if end > start else .5

        return {**fields, 'from': low, 'to': high, 'x': 70 + 860 * low, 'width': max(5, 860 * (high - low)),
                'start': cls.label(begin, selection), 'end': cls.label(finish, selection) if right is not None else None,
                'duration': MapPaceBuilder.duration(fields.get('seconds')), 'clipped': begin != left or finish != stop}

    @staticmethod
    def lanes(items: list[dict]) -> int:
        ends = []
        items.sort(key = lambda item: (item['from'], item['to'], item['line']))

        for item in items:
            lane = next((i for i, end in enumerate(ends) if end <= item['from']), len(ends))

            if lane == len(ends):
                ends.append(0)

            ends[lane] = max(item['to'], item['from'] + .007)
            item['lane'] = lane

        return len(ends)
