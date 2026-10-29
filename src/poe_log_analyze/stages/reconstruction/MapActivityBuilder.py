import hashlib
import json

from collections import Counter
from datetime import datetime, timezone

from pathlib import Path
from zoneinfo import ZoneInfo

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod

from poe_log_analyze.runtime.GameAreaCatalogue import GameAreaCatalogue
from poe_log_analyze.runtime.AreaKind import AreaKind

from poe_log_analyze.stages.reconstruction.MapEncounterTracker import MapEncounterTracker
from poe_log_analyze.stages.reconstruction.LoadingRouteTracker import LoadingRouteTracker
from poe_log_analyze.stages.reconstruction.TechnicalContextTracker import TechnicalContextTracker

class MapActivityBuilder:
    """Reconstruct map runs from observed client transitions."""

    MAPS_VERSION = "12"

    DEFAULT_MAX_GAP_SECONDS = 1800

    BOUNDARIES = {
        "log.open": "Открытие лога",
        "game.closing": "Выход из игры",
        "network.abnormal_disconnect": "Неожиданное отключение",
        "network.maintenance_disconnect": "Отключение на обслуживание",
        "network.instance_disconnect": "Отключение от экземпляра",
    }

    REASONS = {
        "transition": "Переход в другую область",
        "next_map": "Началась другая карта",
        "eof": "Конец файла",
        "gap": "Разрыв наблюдений более порога",
        "clock": "Время вернулось назад",
        "missing_time": "У перехода нет корректного времени",
        **BOUNDARIES,
    }

    @staticmethod
    def build_map_activity(ledger: Path, timezone_name: str, expected_sha256: str,
                           control: ExecutionContext | None = None,
                           max_gap_seconds: int = DEFAULT_MAX_GAP_SECONDS, *, include_areas: bool = False,
                           period: ReportPeriod = ReportPeriod(), comparison_period: ReportPeriod | None = None) -> dict:
        """Create independent processing state for one registry."""

        return MapActivityBuilder(timezone_name, control, max_gap_seconds, include_areas = include_areas,
                                  period = period, comparison_period = comparison_period).build(ledger, expected_sha256)

    def __init__(self, timezone_name: str, control: ExecutionContext | None = None,
                 max_gap_seconds: int = DEFAULT_MAX_GAP_SECONDS, *, include_areas: bool = False,
                 period: ReportPeriod = ReportPeriod(), comparison_period: ReportPeriod | None = None):

        """Read validated JSONL in line order without guessing missing entries."""

        if type(max_gap_seconds) is not int or max_gap_seconds <= 0:
            raise ValueError('The observation-gap threshold must be a positive integer')

        self.include_areas = include_areas
        self.periods = {key: value for key, value in (('period_observations', period),
                        ('comparison_observations', comparison_period)) if value is not None and value.active}
        self.zone = ZoneInfo(timezone_name)
        self.control = control or ExecutionContext()
        self.digest, self.statuses, self.diagnostics, self.outside = hashlib.sha256(), Counter(), Counter(), Counter()
        self.runs = []
        self.diagnostic_events, self.outside_entries = [], []
        self.current = self.visit = self.pending = self.instance = self.previous = None
        self.afk = False
        self.total = 0


        self.timezone_name = timezone_name
        self.max_gap_seconds = max_gap_seconds
        self.loading_routes = LoadingRouteTracker(set(self.BOUNDARIES), max_gap_seconds, self.control)
        self.technical_context = TechnicalContextTracker(set(self.BOUNDARIES), max_gap_seconds, self.control)

    def build(self, ledger, expected_sha256):
        self.control.report('Analyze map runs', force = True)

        with ledger.open("rb") as source:
            for raw in source:
                self.control.check()
                self.digest.update(raw)
                row = json.loads(raw)
                self.loading_routes.add(row)
                self.technical_context.add(row)
                self.total += 1
                status, kind = row["status"], row["type"]

                if row["line_number"] != self.total or status not in ("recognized", "unknown", "error"):
                    raise ValueError('Invalid registry line sequence or statuses')

                self.statuses[status] += 1
                moment = datetime.fromisoformat(row["timestamp"]) if row.get("timestamp") else None

                if moment is not None:
                    if moment.utcoffset() is None:
                        raise ValueError('Registry timestamps must include a UTC offset')

                    moment = moment.astimezone(timezone.utc)

                    if self.previous is not None:
                        if moment < self.previous:
                            self.reset("clock", self.previous, self.total)
                        elif (moment - self.previous).total_seconds() > self.max_gap_seconds:
                            self.reset("gap", self.previous, self.total)

                    self.previous = moment

                if self.visit is not None and status != "recognized":
                    self.current["uncertain_lines"] += 1
                    self.current['uncertain_line_numbers'].append(self.total)

                own = row.get("record_id") == self.total

                if not own:
                    continue

                critical = kind in MapActivityBuilder.BOUNDARIES or kind in ("area.generate", "area.enter", "network.instance_connect")

                # A recognized transition without a timestamp retains its sequence position.
                # Its timestamp and duration remain unknown.
                if critical and moment is None and (status != "recognized" or kind in MapActivityBuilder.BOUNDARIES):
                    self.reset("missing_time", self.previous, self.total)
                    continue

                if critical and moment is None:
                    self.close_visit(None, self.total, "missing_time", False)
                    self.finish("missing_time", self.total)
                    self.diagnose("missing_time")
                    self.afk = False

                if status != "recognized":
                    continue

                fields = row["fields"]

                if kind in MapActivityBuilder.BOUNDARIES:
                    # Opening a log does not establish the end of a previous stay.
                    # A disconnect also does not prove when the client left a map.
                    self.reset(kind, moment, self.total)
                elif kind == "network.instance_connect":
                    self.close_visit(moment, self.total, "transition", True)

                    if self.pending is not None:
                        self.diagnose("generation_without_entry")

                    self.pending = self.instance = None
                elif kind == "instance.id":
                    self.instance = fields["instance_id"]
                elif kind == "area.generate":
                    self.close_visit(moment, self.total, "transition", True)

                    if self.pending is not None:
                        self.diagnose("generation_without_entry")

                    self.pending = {"area_id": fields["area"], "level": fields["level"],
                               "seed": fields["seed"], "instance_id": self.instance,
                               "discoveries": [],
                               "generation_line": self.total, "generated_at": self.stamp(moment)}
                    self.instance = None
                elif kind == "area.enter":
                    self.close_visit(moment, self.total, "transition", True)

                    if self.pending is None:
                        self.diagnose("entry_without_generation")
                        continue

                    target, self.pending = self.pending, None
                    discoveries = target.pop('discoveries')
                    period_discoveries = {key: target.pop(key, []) for key in self.periods}
                    area_id = target["area_id"]
                    area = GameAreaCatalogue.lookup(area_id)

                    if not self.include_areas and AreaKind.code(area) not in ("map", "arena"):
                        self.outside[area_id] += 1
                        self.outside_entries.append({"line": self.total, "area_id": area_id})
                        continue

                    key = (area_id, target["seed"], target["instance_id"])
                    position = self.stamp(moment) or target["generated_at"] or self.stamp(self.previous)
                    basis = "entry" if moment else ("generation" if target["generated_at"] else "previous_record")
                    joinable = target["seed"] not in ("", "0") and bool(target["instance_id"])
                    same = self.current is not None and joinable and key == (
                        self.current["area_id"], self.current["seed"], self.current["instance_id"])

                    if not same:
                        self.finish("next_map", self.total)
                        self.current = {**target, "id": len(self.runs) + 1, "name": fields["area"],
                                   "kind": area["kind"], "kind_code": AreaKind.code(area), "icon": area["icon"],
                                   "started_at": self.stamp(moment), "date": moment.astimezone(self.zone).date().isoformat() if moment else "undated",
                                   "position_at": position, "position_basis": basis if position else None,
                                   "first_line": self.total, "identity_complete": joinable,
                                   "visits": [], "seconds": 0, "afk_seconds": 0,
                                   "unbounded_visits": 0, "uncertain_lines": 0, "uncertain_line_numbers": [], "death_messages": []}
                        self.runs.append(self.current)

                    self.visit = {"entry_line": self.total, "generation_line": target["generation_line"],
                             "entered_at": self.stamp(moment), "level": target["level"],
                             "position_at": position, "position_basis": basis if position else None,
                             "mechanics": [], "death_messages": [], "discoveries": discoveries, "mercenaries": [],
                             "afk_seconds": 0, 'afk_intervals': [], "_afk_since": moment if self.afk else None}
                    self.current["visits"].append(self.visit)

                    for key in self.periods:
                        self.visit[key] = {'mechanics': [], 'discoveries': period_discoveries[key],
                                           'death_messages': [], 'mercenaries': []}
                elif kind in ("screen.afk_on", "screen.afk_off") and moment is not None:
                    new_afk = kind == "screen.afk_on"

                    if self.visit is not None and new_afk != self.afk:
                        if new_afk:
                            self.visit["_afk_since"] = moment
                        elif self.visit["_afk_since"] is not None:
                            self.visit["afk_seconds"] += (moment - self.visit["_afk_since"]).total_seconds()
                            self.visit['afk_intervals'].append({'entered_at': self.stamp(self.visit['_afk_since']),
                                                               'ended_at': self.stamp(moment)})
                            self.visit["_afk_since"] = None

                    self.afk = new_afk
                elif kind in ("screen.slain", "screen.suicide") and self.visit is not None and moment is not None:
                    self.current["death_messages"].append({"line": self.total, "timestamp": self.stamp(moment)})

                if self.visit is not None and AreaKind.code(self.current) == 'map':
                    MapEncounterTracker.add(self.visit, self.current['area_id'], row)

                    for key, period in self.periods.items():
                        if period.contains(row.get('timestamp'), self.timezone_name):
                            MapEncounterTracker.add(self.visit[key], self.current['area_id'], row)
                elif (self.pending is not None and kind == 'hideout.discoverable'
                      and AreaKind.code(GameAreaCatalogue.lookup(self.pending['area_id'])) == 'map'):
                    MapEncounterTracker.discover(self.pending, self.pending['area_id'], row)

                    for key, period in self.periods.items():
                        if period.contains(row.get('timestamp'), self.timezone_name):
                            context = {'discoveries': self.pending.setdefault(key, [])}
                            MapEncounterTracker.discover(context, self.pending['area_id'], row)

                if self.total % 1000 == 0:
                    self.control.report('Analyze map runs', lines = self.total)

        if self.digest.hexdigest() != expected_sha256:
            raise ValueError('The registry changed during map analysis')

        self.close_visit(self.previous, self.total, "eof", False)
        self.finish("eof", self.total)

        if self.pending is not None:
            self.diagnose("generation_without_entry")

        days = {}

        for run in self.runs:
            run["entrances"] = len(run["visits"])
            run["returns"] = run["entrances"] - 1
            run["between_visits_seconds"] = sum(
                (datetime.fromisoformat(right["entered_at"]).astimezone(timezone.utc)
                 - datetime.fromisoformat(left["ended_at"]).astimezone(timezone.utc)).total_seconds()
                for left, right in zip(run["visits"], run["visits"][1:])
                if left["ended_at"] and right["entered_at"])

            if any(not left["ended_at"] or not right["entered_at"]
                   for left, right in zip(run["visits"], run["visits"][1:])):
                run["between_visits_seconds"] = None

            day = days.setdefault(run["date"], {"date": run["date"], "runs": [], "seconds": 0})
            day["runs"].append(run)
            day["seconds"] += run["seconds"]

        summaries = [{"date": day["date"], "count": len(day["runs"]), "seconds": day["seconds"]}
                     for _, day in sorted(days.items())]

        return {"version": MapActivityBuilder.MAPS_VERSION, "loading_routes": self.loading_routes.rows,
                "technical_context": self.technical_context.rows,
                "timezone": self.timezone_name, "ledger_sha256": expected_sha256,
                "max_gap_seconds": self.max_gap_seconds, "total_lines": self.total, "statuses": dict(self.statuses),
                "run_count": len(self.runs), "map_count": sum(AreaKind.code(r) == "map" for r in self.runs),
                "arena_count": sum(AreaKind.code(r) == "arena" for r in self.runs),
                "entrances": sum(r["entrances"] for r in self.runs),
                "seconds": sum(r["seconds"] for r in self.runs),
                "afk_seconds": sum(r["afk_seconds"] for r in self.runs),
                "unbounded_visits": sum(r["unbounded_visits"] for r in self.runs),
                "diagnostics": dict(sorted(self.diagnostics.items())),
                "diagnostic_events": self.diagnostic_events, "outside_entries": self.outside_entries,
                "outside_areas": dict(sorted(self.outside.items())), "days": summaries, "by_date": days}

    def stamp(self, moment):
        return moment.astimezone(self.zone).isoformat() if moment is not None else None

    def close_visit(self, moment, line, reason, bounded):
        if self.visit is None:
            return

        start = datetime.fromisoformat(self.visit["entered_at"]).astimezone(timezone.utc) if self.visit["entered_at"] else None
        ended = moment if bounded else None
        bounded = start is not None and ended is not None
        self.visit.update(end_line = line, ended_at = self.stamp(ended),
                     end_reason = MapActivityBuilder.REASONS[reason], end_reason_code = reason, bounded = bounded,
                     seconds = (ended - start).total_seconds() if bounded else None)

        if self.current["position_at"] is None and ended is not None:
            self.current["position_at"] = self.visit["position_at"] = self.stamp(ended)
            self.current["position_basis"] = self.visit["position_basis"] = "exit"

        if bounded:
            if self.visit["_afk_since"] is not None:
                self.visit["afk_seconds"] += (moment - self.visit["_afk_since"]).total_seconds()
                self.visit['afk_intervals'].append({'entered_at': self.stamp(self.visit['_afk_since']),
                                                   'ended_at': self.stamp(moment)})

            self.current["seconds"] += self.visit["seconds"]
            self.current["afk_seconds"] += self.visit["afk_seconds"]
        else:
            # An unfinished interval is excluded from bounded-interval totals.
            self.visit["afk_seconds"] = None
            self.current["unbounded_visits"] += 1

        del self.visit["_afk_since"]
        self.visit = None

    def finish(self, reason, line):
        if self.current is not None:
            self.current.update(end_reason = MapActivityBuilder.REASONS[reason], end_reason_code = reason, boundary_line = line)
            self.current = None

    def reset(self, reason, moment, line):
        self.close_visit(moment, line, reason, False)
        self.finish(reason, line)

        if self.pending is not None:
            self.diagnose("generation_without_entry")

        self.pending = self.instance = None
        self.afk = False
        self.diagnose(reason)

    def diagnose(self, kind):
        self.diagnostics[kind] += 1
        self.diagnostic_events.append({"kind": kind, "line": self.total})
