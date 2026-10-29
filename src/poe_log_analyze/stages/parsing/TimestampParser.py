from datetime import datetime
from zoneinfo import ZoneInfo

class TimestampParser:
    """Read physical lines and recognize messages conservatively."""

    @staticmethod
    def timestamp_iso(value: str, zone: ZoneInfo) -> str:
        """Validate the date and convert unambiguous local time to ISO 8601."""

        naive = datetime.strptime(value, "%Y/%m/%d %H:%M:%S")
        early = naive.replace(tzinfo = zone, fold = 0)
        late = naive.replace(tzinfo = zone, fold = 1)

        if early.utcoffset() != late.utcoffset():
            raise ValueError('Ambiguous or nonexistent local time')

        return early.isoformat()
