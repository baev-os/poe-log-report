from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.runtime.AreaKind import AreaKind
from poe_log_analyze.runtime.DurationFormatter import DurationFormatter

from poe_log_analyze.stages.composition.VisitMeasurements import VisitMeasurements


class AllTimeStatisticsBuilder:
    """Totals by map type and all areas in the already merged history."""

    @classmethod
    def build(cls, runs: list[dict], control: ExecutionContext) -> dict:
        zones = {}

        for run in runs:
            control.check()
            kind = AreaKind.code(run)
            # An ID combines instances of one area, but not different areas with the same name.
            key = (kind, run.get("area_id") or run["name"])
            row = zones.setdefault(key, {
                "area_id": run.get("area_id", ""), "kind_code": kind,
                "name": run["name"], "names": [], "icon": run.get("icon", ""),
                **cls.empty_totals(),
            })

            if run["name"] not in row["names"]:
                row["names"].append(run["name"])

            row["count"] += 1

            for visit in run["visits"]:
                control.check()
                row["visits"] += 1
                row['seconds'] += VisitMeasurements.seconds(visit)

                if visit["bounded"] and visit["seconds"] is not None:
                    row["measured_visits"] += 1
                else:
                    row["incomplete_visits"] += 1

        rows = sorted(zones.values(), key = lambda row: (-row["seconds"], -row["count"], row["name"], row["area_id"]))

        for row in rows:
            row["name"] = " / ".join(sorted(row["names"]))
            cls.format_duration(row)

        maps = [row for row in rows if row["kind_code"] == "map"]

        return {"version": "1", "maps": cls.total(maps), "map_types": maps,
                "zones": rows, "zone_totals": cls.total(rows),
                "kinds": sorted({row["kind_code"] for row in rows})}

    @staticmethod
    def empty_totals() -> dict:
        return {"count": 0, "visits": 0, "measured_visits": 0, "incomplete_visits": 0, "seconds": 0}

    @classmethod
    def total(cls, rows: list[dict]) -> dict:
        result = {key: sum(row[key] for row in rows) for key in cls.empty_totals()}
        cls.format_duration(result)

        return result

    @staticmethod
    def format_duration(row: dict) -> None:
        row["duration"] = DurationFormatter.duration_label(row["seconds"]) if row["measured_visits"] or row['seconds'] else "—"
