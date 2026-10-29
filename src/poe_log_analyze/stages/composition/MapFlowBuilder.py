from zoneinfo import ZoneInfo

from poe_log_analyze.runtime.AreaKind import AreaKind

from poe_log_analyze.stages.composition.MapRowOrdering import MapRowOrdering

from poe_log_analyze.runtime.DurationFormatter import DurationFormatter

from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder
from poe_log_analyze.stages.composition.VisitMeasurements import VisitMeasurements


class MapFlowBuilder:
    """Map helpers: distinguish known durations from sequence positions."""

    FLOW_VERSION = "11"

    @staticmethod
    def build_map_flow(maps: dict, source_label: str = "") -> dict:
        """Display visits by known time while retaining incomplete records."""

        rows = []
        zone = ZoneInfo(maps.get("timezone", "Asia/Almaty"))

        for day in maps["by_date"].values():
            for run in day["runs"]:
                if AreaKind.code(run) != "map":
                    continue

                for visit in run["visits"]:
                    entered, exited = MapRowOrdering.moment(visit["entered_at"]), MapRowOrdering.moment(visit["ended_at"])
                    entered = entered.astimezone(zone) if entered else None
                    exited = exited.astimezone(zone) if exited else None
                    seconds = VisitMeasurements.seconds(visit) if VisitMeasurements.parts(visit) else None
                    rows.append({"name": run["name"], "area_id": run.get("area_id", ""), "icon": run.get("icon", ""), "source": run.get("source", source_label),
                                 "entered_at": entered.isoformat() if entered else None,
                                 "entry": entered.strftime("%d.%m.%Y %H:%M:%S") if entered else "—",
                                 "exited_at": exited.isoformat() if exited else None,
                                 "exit": exited.strftime("%d.%m.%Y %H:%M:%S") if exited else "—",
                                 "seconds": seconds,
                                 'incomplete': not visit.get('bounded', seconds is not None),
                                 'branches': [MapFlowBuilder.branch(part, zone) for part in visit.get('branches', [])],
                                 'branched': bool(visit.get('branches')),
                                 "duration": DurationFormatter.duration_label(seconds) if seconds is not None else "—",
                                 "href": LogHistoryBuilder.line_href(visit['entry_line']) if visit.get('entry_line') else None,
                                 "mechanics": [MapFlowBuilder.event(item, zone) for item in
                                               sorted(visit.get('mechanics', []), key = lambda item: item['code'])],
                                 "death_messages": [MapFlowBuilder.event(item, zone)
                                                    for item in visit.get('death_messages', [])],
                                 "discoveries": [MapFlowBuilder.event(item, zone)
                                                 for item in visit.get('discoveries', [])],
                                 "mercenaries": [MapFlowBuilder.event(item, zone)
                                                 for item in visit.get('mercenaries', [])],
                                 "line": visit.get("entry_line"), "_line": visit.get("entry_line"),
                                 "_anchor": visit.get("position_at")})

        rows = MapRowOrdering.ordered_rows(rows)
        months, undated = MapFlowBuilder.group_dates(rows)

        return {"version": MapFlowBuilder.FLOW_VERSION, **MapFlowBuilder.summary(rows),
                "months": months, "undated": undated}

    @staticmethod
    def branch(visit: dict, zone: ZoneInfo) -> dict:
        result = dict(visit)

        for name, key in (('entry', 'entered_at'), ('exit', 'ended_at')):
            moment = MapRowOrdering.moment(visit[key])
            result[name] = moment.astimezone(zone).strftime('%d.%m.%Y %H:%M:%S') if moment else '—'

        result['end_href'] = LogHistoryBuilder.line_href(visit['end_line'])
        result['evidence'] = [MapFlowBuilder.event(event, zone)
                              for field in ('mechanics', 'discoveries', 'mercenaries', 'death_messages')
                              for event in visit.get(field, [])]

        return result

    @staticmethod
    def event(item: dict, zone: ZoneInfo) -> dict:
        moment = MapRowOrdering.moment(item['timestamp'])
        return {**item, 'time': moment.astimezone(zone).strftime('%d.%m.%Y %H:%M:%S') if moment else '—',
                'href': LogHistoryBuilder.line_href(item['line'])}

    @staticmethod
    def summary(rows: list[dict]) -> dict:
        seconds = sum(row["seconds"] for row in rows if row["seconds"] is not None)
        return {"rows": rows, "count": len(rows), "seconds": seconds,
                "duration": DurationFormatter.duration_label(seconds),
                "death_count": sum(len(row['death_messages']) for row in rows),
                "incomplete": sum(row.get('incomplete', row['seconds'] is None) for row in rows)}

    @staticmethod
    def group_dates(rows: list[dict]) -> tuple[list[dict], dict]:
        """Group by known entry or exit without treating an ordering hint as a date."""

        dated, undated = {}, []

        for row in rows:
            moment = MapRowOrdering.moment(row["entered_at"] or row["exited_at"])

            if moment is None:
                undated.append(row)
            else:
                dated.setdefault(moment.date().isoformat(), []).append(row)

        months = {}

        for date, visits in sorted(dated.items()):
            month_id = date[:7]
            month = months.setdefault(month_id, {"id": month_id, "label": month_id, "days": []})
            month["days"].append({"date": date, "label": ".".join(reversed(date.split("-"))),
                                  **MapFlowBuilder.summary(visits)})

        for month in months.values():
            # Rows belong to the day; the month needs counters only.
            summary = MapFlowBuilder.summary([row for day in month["days"] for row in day["rows"]])
            summary.pop("rows")
            month.update(summary)

        return list(months.values()), MapFlowBuilder.summary(undated)
