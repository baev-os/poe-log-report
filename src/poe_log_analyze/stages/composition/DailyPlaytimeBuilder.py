from typing import Any
from collections import Counter
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from poe_log_analyze.runtime.DurationFormatter import DurationFormatter


class DailyPlaytimeBuilder:
    """Split observed time at local midnight, including DST transition days."""

    @staticmethod
    def build(activity: dict[str, Any], timezone_name: str, *, reference: dict | None = None) -> dict[str, Any]:
        zone = ZoneInfo(timezone_name)
        seconds = Counter()

        for interval in activity['intervals']:
            start = datetime.fromisoformat(interval['started_at']).astimezone(timezone.utc)
            end = datetime.fromisoformat(interval['ended_at']).astimezone(timezone.utc)

            while start < end:
                day = start.astimezone(zone).date()
                midnight = datetime.combine(day+timedelta(days = 1), time(), zone).astimezone(timezone.utc)
                stop = min(end, midnight)
                seconds[day] += (stop-start).total_seconds()
                start = stop

        days = []

        if seconds or (reference and reference['days']):
            day = datetime.fromisoformat(reference['days'][0]['date']).date() if reference and reference['days'] else min(seconds)
            last = datetime.fromisoformat(reference['days'][-1]['date']).date() if reference and reference['days'] else max(seconds)

            while day <= last:
                amount = seconds[day]
                days.append({'date': day.isoformat(), 'label': day.strftime('%d.%m'), 'seconds': amount,
                             'hours': round(amount/3600, 3), 'duration': DurationFormatter.duration_label(amount)})
                day += timedelta(days = 1)

        maximum = max(1, max((day['hours'] for day in days), default = 0))
        maximum = int(maximum)+1

        if reference:
            maximum = reference['maximum']

        for i, day in enumerate(days):
            day.update(x = 70+i*900/max(1,len(days)), width = 780/max(1,len(days)),
                       y = 320-280*day['hours']/maximum, height = 280*day['hours']/maximum,
                       tick = (i % max(1, len(days)//10)==0 or i==len(days)-1))

        return {'days': days, 'seconds': sum(seconds.values()), 'maximum': maximum,
                'ticks': [{'y': 320-280*i/4, 'hours': round(maximum*i/4, 1)} for i in range(5)]}
