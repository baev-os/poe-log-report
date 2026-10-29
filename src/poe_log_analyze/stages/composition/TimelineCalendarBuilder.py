import calendar

from datetime import date

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext


class TimelineCalendarBuilder:
    """Monthly line accounting; dates without selected events remain available."""

    @staticmethod
    def build(timeline: dict, control: ExecutionContext) -> dict:
        days = {day['date']: day for day in timeline['days']}
        months = []

        if days:
            cursor = date.fromisoformat(min(days)).replace(day = 1)
            last = date.fromisoformat(max(days))

            while cursor <= last:
                control.check()
                weeks = []

                for week in calendar.Calendar().monthdatescalendar(cursor.year, cursor.month):
                    weeks.append([{'date': day.isoformat(), 'number': day.day,
                                   'current': day.month == cursor.month,
                                   'summary': days.get(day.isoformat())}
                                  for day in week])

                months.append({'id': cursor.strftime('%Y-%m'), 'weeks': weeks})
                cursor = date(cursor.year + cursor.month // 12, cursor.month % 12 + 1, 1)

        return {'version': '1', 'months': months}
