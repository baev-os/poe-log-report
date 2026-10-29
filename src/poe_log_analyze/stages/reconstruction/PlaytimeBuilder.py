import hashlib
import json

from pathlib import Path
from typing import Any
from datetime import datetime, timezone

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.runtime.DurationFormatter import DurationFormatter

from poe_log_analyze.stages.reconstruction.MapActivityBuilder import MapActivityBuilder

class PlaytimeBuilder:
    """Observed playtime: from area entry until disconnect or the end of observations."""

    ACTIVITY_VERSION = "2"

    @staticmethod
    def build_activity(ledger: Path, expected_sha256: str, control: ExecutionContext | None = None) -> dict[str, Any]:
        """Create independent state for an observed play session."""

        return PlaytimeBuilder(control).build(ledger, expected_sha256)

    def __init__(self, control: ExecutionContext | None = None):

        """Include towns, hideouts, loading, and AFK without filling missing time."""

        self.control = control or ExecutionContext()
        self.digest = hashlib.sha256()
        self.intervals = []
        self.start = self.previous = None
        self.first_line = self.last_line = self.total = 0
        self.afk_since = None
        self.afk_line = 0
        self.afk_intervals = []


    def build(self, ledger, expected_sha256):
        with ledger.open("rb") as stream:
            for raw in stream:
                self.control.check()
                self.digest.update(raw)
                row = json.loads(raw)
                self.total += 1

                if row["line_number"] != self.total:
                    raise ValueError('Invalid registry line sequence')

                kind = row["type"]
                own = row.get("record_id") == self.total and row["status"] == "recognized"

                if not row.get("timestamp"):
                    if own and (kind in MapActivityBuilder.BOUNDARIES or kind == "area.enter"):
                        self.close(self.previous, self.last_line, "missing_time")
                    elif own and kind in ('screen.afk_on', 'screen.afk_off'):
                        self.close_afk(self.previous, self.last_line, 'missing_time')

                    continue

                moment = datetime.fromisoformat(row["timestamp"])

                if moment.utcoffset() is None:
                    raise ValueError('Timestamps must include a UTC offset')

                moment = moment.astimezone(timezone.utc)

                if self.previous is not None:
                    if moment < self.previous:
                        self.close(self.previous, self.last_line, "clock")
                    elif (moment - self.previous).total_seconds() > MapActivityBuilder.DEFAULT_MAX_GAP_SECONDS:
                        self.close(self.previous, self.last_line, "gap")

                if own and kind in MapActivityBuilder.BOUNDARIES:
                    if kind == "log.open":
                        self.close(self.previous, self.last_line, kind)
                    else:
                        self.close(moment, self.total, kind, False)
                elif own and kind == "area.enter" and self.start is None:
                    self.start, self.first_line = moment, self.total
                elif own and kind == 'screen.afk_on' and self.afk_since is None:
                    self.afk_since, self.afk_line = moment, self.total
                elif own and kind == 'screen.afk_off':
                    self.close_afk(moment, self.total, kind)

                self.previous, self.last_line = moment, self.total

                if self.total % 1000 == 0:
                    self.control.report('Calculate playtime', lines = self.total)

        if self.digest.hexdigest() != expected_sha256:
            raise ValueError('The registry changed while calculating playtime')

        self.close(self.previous, self.last_line, "eof")
        seconds = sum(item["seconds"] for item in self.intervals)

        return {"version": PlaytimeBuilder.ACTIVITY_VERSION, "seconds": seconds, "duration": DurationFormatter.duration_label(seconds),
                "incomplete": sum(item["incomplete"] for item in self.intervals), "intervals": self.intervals,
                "max_gap_seconds": MapActivityBuilder.DEFAULT_MAX_GAP_SECONDS, "total_lines": self.total}

    def close(self, end, line, reason, incomplete = True):
        self.close_afk(end, line, reason)

        if self.start is not None:
            self.intervals.append({"started_at": self.start.isoformat(), "ended_at": end.isoformat(),
                              "first_line": self.first_line, "last_line": line, "reason": reason,
                              "incomplete": incomplete, "seconds": (end - self.start).total_seconds(),
                              'afk_intervals': self.afk_intervals})

        self.start = None
        self.afk_intervals = []

    def close_afk(self, end, line, reason):
        if self.afk_since is not None and self.start is not None and end is not None:
            start = max(self.start, self.afk_since)

            if end >= start:
                self.afk_intervals.append({'entered_at': start.isoformat(), 'ended_at': end.isoformat(),
                    'first_line': self.afk_line, 'last_line': line, 'end_reason': reason,
                    'open_at_end': reason != 'screen.afk_off'})

        self.afk_since = None
