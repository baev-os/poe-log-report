from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


@dataclass(frozen = True, slots = True)
class ReportPeriod:
    """Inclusive calendar dates in the source log time zone."""

    date_from: date | None = None
    date_to: date | None = None

    def __post_init__(self) -> None:

        for value in (self.date_from, self.date_to):
            if value is not None and type(value) is not date:
                raise ValueError('Period dates must use YYYY-MM-DD format')

            if value == date.min:
                raise ValueError('Period dates must be after 0001-01-01')

        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError('The period start is later than its end')

        if self.date_to == date.max:
            raise ValueError('The end date must be before 9999-12-31')

    @property
    def active(self) -> bool:
        return self.date_from is not None or self.date_to is not None

    def bounds(self, zone_name: str) -> tuple[datetime | None, datetime | None]:
        zone = ZoneInfo(zone_name)
        start = datetime.combine(self.date_from, time(), zone).astimezone(timezone.utc) if self.date_from else None
        end = (datetime.combine(self.date_to + timedelta(days = 1), time(), zone).astimezone(timezone.utc)
               if self.date_to else None)

        return start, end

    def contains(self, stamp: str | None, zone_name: str) -> bool:
        if not self.active:
            return True

        if not stamp:
            return False

        moment = datetime.fromisoformat(stamp)

        if moment.utcoffset() is None:
            return False

        day = moment.astimezone(ZoneInfo(zone_name)).date()

        return (self.date_from is None or day >= self.date_from) and (self.date_to is None or day <= self.date_to)
