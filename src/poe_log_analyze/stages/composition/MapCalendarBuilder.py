import calendar

from typing import Any

from datetime import date

from poe_log_analyze.runtime.DurationFormatter import DurationFormatter


class MapCalendarBuilder:
    """Calendar months starting on Monday; empty days must not imply play."""

    MONTHS = ('Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
              'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь')

    @staticmethod
    def build_details(maps: dict[str, Any]) -> dict[str, Any]:
        """Technical days include arenas even when there are no regular maps that day."""

        return MapCalendarBuilder.build({'by_date': {
            day['date']: {**day, 'duration': DurationFormatter.duration_label(day['seconds'])}
            for day in maps['days']}})

    @staticmethod
    def build(statistics: dict[str, Any], playtime: dict[str, Any] | None = None,
              daily_areas: dict[str, Any] | None = None) -> dict[str, Any]:

        areas = daily_areas['by_date'] if daily_areas else {}
        dates = {key for key in statistics['by_date'] if key != 'undated'}
        dates.update(key for key in areas if key != 'undated')

        if playtime is not None:
            dates.update(day['date'] for day in playtime['days'])

        known = sorted(dates)
        months = []

        if known:
            first, last = date.fromisoformat(known[0]), date.fromisoformat(known[-1])
            cursor = first.replace(day = 1)

            while cursor <= last:
                weeks = []

                for week in calendar.Calendar().monthdatescalendar(cursor.year, cursor.month):
                    weeks.append([{'date': day.isoformat(), 'number': day.day, 'current': day.month==cursor.month,
                                   'maps': statistics['by_date'].get(day.isoformat()),
                                   'areas': areas[day.isoformat()]['zone_totals'] if day.isoformat() in areas else None}
                                  for day in week])

                months.append({'id': cursor.strftime('%Y-%m'), 'label': f'{MapCalendarBuilder.MONTHS[cursor.month-1]} {cursor.year}', 'weeks': weeks})
                cursor = date(cursor.year+cursor.month//12, cursor.month%12+1, 1)

        return {'months': months, 'undated': statistics['by_date'].get('undated'),
                'undated_areas': areas.get('undated')}
