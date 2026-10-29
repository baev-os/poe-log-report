from bisect import bisect_right
from collections import defaultdict
from colorsys import hsv_to_rgb
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.runtime.DurationFormatter import DurationFormatter

from poe_log_analyze.stages.composition.PlaytimeHeatmapBuilder import PlaytimeHeatmapBuilder


class WeeklyIntensityBuilder:
    """Continuous weekly profile from exact intervals without hourly buckets."""

    DAY = 86400
    WEEK = 7 * DAY
    STEP = 300
    RADIUS = 1800

    @classmethod
    def build(cls, intervals: list[dict], timezone_name: str, control: ExecutionContext) -> dict:
        zone = ZoneInfo(timezone_name)
        events = defaultdict(float, {0: 0., cls.WEEK: 0.})
        totals = [0.] * 7

        for interval in intervals:
            control.check()

            if not interval.get('started_at') or not interval.get('ended_at'):
                continue

            start = datetime.fromisoformat(interval['started_at']).astimezone(timezone.utc)
            end = datetime.fromisoformat(interval['ended_at']).astimezone(timezone.utc)

            while start < end:
                control.check()
                local = start.astimezone(zone)
                midnight = datetime.combine(local.date() + timedelta(days = 1), datetime.min.time(), zone)
                # The step bounds offset-transition searches; time is not rounded to hours.
                stop = min(end, start + timedelta(hours = 1), midnight.astimezone(timezone.utc))

                if stop.astimezone(zone).utcoffset() != local.utcoffset():
                    stop = PlaytimeHeatmapBuilder.transition(start, stop, zone)

                seconds = (stop - start).total_seconds()
                wall = local.weekday() * cls.DAY + local.hour * 3600 + local.minute * 60 + local.second + local.microsecond / 1e6
                events[wall] += 1
                events[wall + seconds] -= 1
                totals[local.weekday()] += seconds
                start = stop

        coordinates = sorted(events)
        areas, heights = [], []
        height = area = previous = 0.

        for stamp in coordinates:
            area += height * (stamp - previous)
            height += events[stamp]
            areas.append(area)
            heights.append(height)
            previous = stamp

        rows = []

        for weekday in range(7):
            points = []

            for second in range(0, cls.DAY + 1, cls.STEP):
                control.check()
                center = weekday * cls.DAY + second
                value = max(0., cls.integral(center + cls.RADIUS, coordinates, areas, heights)
                            - cls.integral(center - cls.RADIUS, coordinates, areas, heights))
                points.append({'second': second, 'time': f'{second // 3600:02}:{second % 3600 // 60:02}',
                               'seconds': value, 'duration': DurationFormatter.duration_label(value)})

            rows.append({'weekday': weekday, 'seconds': totals[weekday],
                         'duration': DurationFormatter.duration_label(totals[weekday]), 'points': points})

        maximum = max((point['seconds'] for row in rows for point in row['points']), default = 0.)

        for row in rows:
            for point in row['points']:
                level = point['seconds'] / maximum if maximum else 0.
                rgb = hsv_to_rgb((180 - 155 * level) / 360, .72, .88)
                point.update(level = level, opacity = round(level ** .45, 6),
                             color = '#' + ''.join(f'{round(channel * 255):02x}' for channel in rgb))

        return {'version': '1', 'timezone': timezone_name, 'step_seconds': cls.STEP,
                'smoothing_radius_seconds': cls.RADIUS, 'rows': rows, 'seconds': sum(totals),
                'maximum_seconds': maximum, 'maximum_duration': DurationFormatter.duration_label(maximum)}

    @classmethod
    def integral(cls, stamp, coordinates, areas, heights):
        """Density antiderivative extended across the cyclic week."""

        cycles, remainder = divmod(stamp, cls.WEEK)
        index = bisect_right(coordinates, remainder) - 1
        return cycles * areas[-1] + areas[index] + heights[index] * (remainder - coordinates[index])
