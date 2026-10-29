from poe_log_analyze.runtime.AreaKind import AreaKind

from poe_log_analyze.stages.composition.MapRowOrdering import MapRowOrdering
from poe_log_analyze.stages.composition.VisitMeasurements import VisitMeasurements

from poe_log_analyze.runtime.DurationFormatter import DurationFormatter

from datetime import datetime

class MapStatisticsBuilder:
    """Map helpers: distinguish known durations from sequence positions."""

    STATISTICS_VERSION = "7"

    @staticmethod
    def calendar_counts(runs: list[dict], control) -> dict:
        """The calendar needs only instance counts by date of selected visits."""

        days = {}

        for run in runs:
            control.check()

            if AreaKind.code(run) == 'map':
                day = days.setdefault(run.get('period_date', run['date']), {'count': 0})
                day['count'] += 1

        return {'by_date': days}

    @staticmethod
    def build_map_statistics(maps: dict) -> dict:
        """Display all maps, including records missing one or both timestamps."""

        days = {}
        keys = sorted(maps["by_date"], key = lambda key: (key != "undated", key), reverse = True)

        for key in keys:
            rows = []

            for run in maps["by_date"][key]["runs"]:
                if AreaKind.code(run) != "map":
                    continue

                entered = MapRowOrdering.moment(run["started_at"])
                exited = MapRowOrdering.moment(run["visits"][-1]["ended_at"])
                parts = [part for visit in run['visits'] for part in VisitMeasurements.parts(visit)]
                seconds = sum(part['seconds'] for part in parts) if parts else None
                rows.append({
                    "name": run["name"], "area_id": run.get("area_id", ""), "icon": run.get("icon", ""), "seconds": seconds,
                    "duration": DurationFormatter.duration_label(seconds) if seconds is not None else "—",
                    "entered_at": entered.isoformat() if entered else None,
                    "entry": entered.strftime("%H:%M:%S") if entered else "—",
                    "exited_at": exited.isoformat() if exited else None,
                    "exit": (exited.strftime("%H:%M:%S") if entered and exited.date() == entered.date()
                             else exited.strftime("%d.%m.%Y %H:%M:%S")) if exited else "—",
                    "line": run.get("first_line"), "_line": run.get("first_line"),
                    "_anchor": run.get("position_at"),
                    'branched': run.get('branched', False),
                    'incomplete': bool(run['unbounded_visits']) or seconds is None,
                })

                if "source" in run:
                    rows[-1]["source"] = run["source"]

            if rows:
                rows = MapRowOrdering.ordered_rows(rows)
                measured = [row["seconds"] for row in rows if row["seconds"] is not None]
                days[key] = {"date": key, "label": "Дата входа неизвестна" if key == "undated" else datetime.fromisoformat(key).strftime("%d.%m.%Y"),
                             "count": len(rows), "duration": DurationFormatter.duration_label(sum(measured)),
                             "incomplete": sum(row['incomplete'] for row in rows), "rows": rows}

        keys = list(days)

        for i, key in enumerate(keys):
            days[key]["newer"] = keys[i - 1] if i else None
            days[key]["older"] = keys[i + 1] if i + 1 < len(keys) else None

        return {"version": MapStatisticsBuilder.STATISTICS_VERSION, "timezone": maps["timezone"],
                "count": sum(day["count"] for day in days.values()),
                "days": [{k: v for k, v in day.items() if k != "rows"} for day in days.values()],
                "by_date": days}
