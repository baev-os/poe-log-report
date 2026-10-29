from datetime import datetime, timedelta, timezone
from math import floor

from poe_log_analyze.runtime.AreaKind import AreaKind

from poe_log_analyze.stages.composition.MapPaceBuilder import MapPaceBuilder
from poe_log_analyze.stages.composition.VisitMeasurements import VisitMeasurements


class SessionRhythmBuilder:
    """Half-hour windows from the original session start; silence does not become AFK."""

    BIN_SECONDS = 1800
    STREAK_GAP_SECONDS = 300

    @staticmethod
    def moment(stamp: str) -> datetime:
        return datetime.fromisoformat(stamp).astimezone(timezone.utc)

    @classmethod
    def build(cls, definitions, intervals, runs, pace, sessions, selection) -> dict:
        result = {}
        anchors = {row['first_line']: min(cls.moment(branch['started_at']) for branch in row['branches'])
                   for row in definitions}

        for first, session in sessions.rows.items():
            selection.control.check()
            anchor = anchors[first]
            bins = {}

            for interval in intervals:
                selection.control.check()

                if interval['first_line'] != first:
                    continue

                cls.split(bins, anchor, interval['started_at'], interval['ended_at'], 'play_seconds', selection)

                for part in interval.get('afk_intervals', []):
                    cls.split(bins, anchor, part['entered_at'], part['ended_at'], 'afk_seconds', selection)

                if 'afk_intervals' not in interval:
                    cls.split(bins, anchor, interval['started_at'], interval['ended_at'], 'unknown_afk', selection)

            for run in runs:
                kind = AreaKind.code(run)

                if kind not in ('map', 'hideout'):
                    continue

                for visit in run['visits']:
                    if sessions.session(visit['entry_line']) != first:
                        continue

                    for part in VisitMeasurements.parts(visit):
                        cls.split(bins, anchor, part['entered_at'], part['ended_at'], kind + '_seconds', selection)

            for gap in pace['gaps']['rows']:
                if gap['session_id'] == str(first):
                    cls.split(bins, anchor, gap['started_at'], gap['ended_at'], 'gap_seconds', selection)

            maps = [row for row in pace['rows'] if row['session_id'] == str(first) and row['new'] and row['timestamp']]

            for row in maps:
                selection.control.check()
                index = floor((cls.moment(row['timestamp']) - anchor).total_seconds() / cls.BIN_SECONDS)
                cls.bin(bins, index)['new'] += 1

            rows = []

            for index, row in sorted(bins.items()):
                selection.control.check()
                start = anchor + timedelta(seconds = index * cls.BIN_SECONDS)
                row.update(index = index, elapsed = f'{index * 30}–{(index + 1) * 30}',
                           started_at = start.astimezone(selection.zone).isoformat(),
                           start = start.astimezone(selection.zone).strftime('%d.%m.%Y %H:%M:%S %z'))
                cls.metrics(row)
                rows.append(row)

            middle = (rows[0]['index'] + rows[-1]['index'] + 1) / 2 if rows else 0
            early = cls.summary([row for row in rows if row['index'] < middle])
            late = cls.summary([row for row in rows if row['index'] >= middle])
            difference = late['rate'] - early['rate'] if early['rate'] is not None and late['rate'] is not None else None
            result[str(first)] = {'id': str(first), 'href': session['path'], 'start': session['start'],
                                  'anchor': anchor.astimezone(selection.zone).isoformat(),
                                  'clipped': session['clipped'], 'branched': session['branched'], 'bins': rows,
                                  'early': early, 'late': late, 'rate_difference': difference,
                                  'streaks': cls.streaks(maps, pace['gaps']['rows'], session, selection)}

        return {'version': '1', 'bin_seconds': cls.BIN_SECONDS, 'streak_gap_seconds': cls.STREAK_GAP_SECONDS,
                'by_session': result}

    @staticmethod
    def bin(bins, index) -> dict:
        return bins.setdefault(index, {key: 0 for key in ('play_seconds', 'map_seconds', 'hideout_seconds',
                                                         'afk_seconds', 'gap_seconds', 'unknown_afk', 'new')})

    @classmethod
    def split(cls, bins, anchor, start, end, field, selection) -> None:
        left, right = cls.moment(start), cls.moment(end)

        while left < right:
            selection.control.check()
            index = floor((left - anchor).total_seconds() / cls.BIN_SECONDS)
            stop = min(right, anchor + timedelta(seconds = (index + 1) * cls.BIN_SECONDS))
            cls.bin(bins, index)[field] += (stop - left).total_seconds()
            left = stop

    @classmethod
    def metrics(cls, row) -> None:
        row['remaining_seconds'] = None if row['unknown_afk'] else max(0, row['play_seconds'] - row['afk_seconds'])
        row['rate'] = row['new'] * 3600 / row['play_seconds'] if row['play_seconds'] else None
        row['rate_without_afk'] = row['new'] * 3600 / row['remaining_seconds'] if row['remaining_seconds'] else None

        for field in ('play', 'map', 'hideout', 'gap', 'remaining', 'afk'):
            seconds = None if field == 'afk' and row['unknown_afk'] else row[field + '_seconds']
            row[field + '_duration'] = MapPaceBuilder.duration(seconds)

    @classmethod
    def summary(cls, rows) -> dict:
        result = {key: sum(row[key] for row in rows) for key in ('play_seconds', 'map_seconds', 'hideout_seconds',
                                                               'afk_seconds', 'gap_seconds', 'unknown_afk', 'new')}
        cls.metrics(result)

        return result

    @classmethod
    def streaks(cls, maps, gaps, session, selection) -> list[dict]:
        if session['branched']:
            return []

        links = {row['line']: row for row in gaps if row['session_id'] == session['id']}
        streaks, current, previous = [], [], None

        for row in sorted(maps, key = lambda item: item['line']):
            selection.control.check()
            gap = links.get(row['line'])
            linked = (previous is not None and gap is not None and gap['from_run'] == previous['line']
                      and gap['from_visit'] == previous['line']
                      and not gap['return'] and not gap['clipped'] and gap['seconds'] <= cls.STREAK_GAP_SECONDS
                      and gap['afk_seconds'] == 0)

            eligible = not row['excluded'] and row.get('afk_seconds') == 0

            if not eligible or not linked:
                if current:
                    streaks.append({'count': len(current), 'lines': list(current)})

                current = []

            if eligible:
                current.append(row['line'])

            previous = row

        if current:
            streaks.append({'count': len(current), 'lines': current})

        return sorted(streaks, key = lambda row: (-row['count'], row['lines'][0]))
