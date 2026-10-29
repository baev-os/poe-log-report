from datetime import datetime, timezone
from zoneinfo import ZoneInfo, available_timezones

from poe_log_analyze.runtime.RuntimeResources import RuntimeResources

from poe_log_analyze.desktop.TimezoneOption import TimezoneOption

class TimezoneCatalogue:
    """Regional time zone catalogue with readable GMT offsets."""

    @staticmethod
    def timezone_options(at: datetime | None = None) -> tuple[TimezoneOption, ...]:
        """Display today's offset; analysis uses the selected zone's historical rules."""

        RuntimeResources.configure_timezone()
        at = at or datetime.now(timezone.utc)

        if at.tzinfo is None:
            raise ValueError('The time-zone catalogue date must include a time zone')

        names = {name for name in available_timezones()
                 if "/" in name and not name.startswith(("Etc/", "posix/", "right/"))}
        names.add("UTC")
        options = []

        for name in names:
            offset = int(at.astimezone(ZoneInfo(name)).utcoffset().total_seconds() // 60)
            hours, minutes = divmod(abs(offset), 60)
            label = f"GMT{'+' if offset >= 0 else '-'}{hours:02d}:{minutes:02d} — {name}"
            options.append(TimezoneOption(name, label, offset))

        return tuple(sorted(options, key = lambda item: (item.offset_minutes, item.key)))
