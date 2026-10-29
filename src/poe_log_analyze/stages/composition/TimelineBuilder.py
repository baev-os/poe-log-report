import hashlib
import json

from collections import Counter
from datetime import datetime, timezone

from pathlib import Path
from zoneinfo import ZoneInfo

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

from poe_log_analyze.stages.composition.events.RecordedMessage import RecordedMessage

class TimelineBuilder:
    """Chronology of selected confirmed messages and line accounting by date."""

    TIMELINE_VERSION = "3"

    EVENT_TYPES = {
        "log.open": "Открытие лога",
        "area.enter": "Вход в область",
        "screen.level_up": "Повышение уровня",
        "screen.slain": "Сообщение о гибели",
        "screen.suicide": "Гибель от собственного урона",
        "screen.nameless_seer": "Появление Nameless Seer",
        "screen.reflecting_mist": "Появление Reflecting Mist",
        "hideout.discoverable": "Доступное для обнаружения убежище",
        "screen.death_count": "Счётчик смертей",
        "network.abnormal_disconnect": "Неожиданное отключение",
        "reliquary.message": "Сообщение Reliquary",
    }

    @staticmethod
    def describe_event(kind: str, fields: dict) -> str:
        """Select only allowed fields; omit chat text and raw lines."""

        if kind == "area.enter":
            return f"Вход в область: {fields['area']}"

        if kind == "screen.level_up":
            return f"{fields['character']} ({fields['class']}): уровень {fields['level']}"

        if kind in ("screen.slain", "screen.suicide"):
            return f"Сообщение о гибели персонажа: {fields['character']}"

        if kind == "screen.death_count":
            return f"Показан счётчик смертей: {fields['count']}"

        if kind == 'reliquary.message':
            return fields['message']

        return TimelineBuilder.EVENT_TYPES[kind]

    @staticmethod
    def event(row: dict, zone: ZoneInfo) -> dict:
        """Shared event view for the complete timeline and level chart."""

        local = datetime.fromisoformat(row['timestamp']).astimezone(zone)

        return {'line_number': row['line_number'], 'type': row['type'], 'kind': TimelineBuilder.EVENT_TYPES[row['type']],
                'description': TimelineBuilder.describe_event(row['type'], row['fields']),
                'timestamp': local.isoformat(), 'utc': local.astimezone(timezone.utc).isoformat(),
                'timestamp_raw': row.get('timestamp_raw', ''), 'time': local.strftime('%H:%M:%S'),
                'message': RecordedMessage.from_record(row)}

    @staticmethod
    def build_timeline(ledger: Path, timezone_name: str, expected_sha256: str,
                       control: ExecutionContext | None = None) -> dict:
        """Stream the registry; order messages by UTC and line number."""

        control = control or ExecutionContext()
        zone = ZoneInfo(timezone_name)
        days = {}
        statuses, undated_statuses, event_counts = Counter(), Counter(), Counter()
        total = dated = regressions = selected_without_time = 0
        previous = first = last = None
        reliquary_event = None
        digest = hashlib.sha256()
        size, processed = ledger.stat().st_size, 0
        control.report('Prepare timeline', total = size, force = True, unit = 'bytes')

        with ledger.open("rb") as source:
            for raw in source:
                control.check()
                digest.update(raw)
                processed += len(raw)
                row = json.loads(raw)

                if row['type'] == 'reliquary.message.field' and reliquary_event and row.get('record_id') == reliquary_event['line_number']:
                    reliquary_event['message']['original'] += '\n' + row['text']
                    reliquary_event['message']['fields']['message'] += '\n' + row['text']
                    reliquary_event['description'] += '\n' + row['text']
                else:
                    reliquary_event = None

                total += 1

                if row["line_number"] != total or row["status"] not in ("recognized", "unknown", "error"):
                    raise ValueError('Invalid registry line sequence or statuses')

                statuses[row["status"]] += 1
                selected = row["status"] == "recognized" and row["type"] in TimelineBuilder.EVENT_TYPES and row.get("record_id") == total

                # Joining independent observations is not evidence of a client clock rollback.
                if row.get("history_boundary"):
                    previous = None

                stamp = row.get("timestamp")

                if not stamp:
                    undated_statuses[row["status"]] += 1
                    selected_without_time += int(selected)
                else:
                    instant = datetime.fromisoformat(stamp)

                    if instant.utcoffset() is None:
                        raise ValueError('Registry timestamps must include a UTC offset')

                    utc = instant.astimezone(timezone.utc)
                    local = instant.astimezone(zone)
                    regressions += int(previous is not None and utc < previous)
                    previous = utc
                    first = utc if first is None else min(first, utc)
                    last = utc if last is None else max(last, utc)
                    dated += 1
                    day_key = local.date().isoformat()

                    if day_key not in days:
                        days[day_key] = {"date": day_key, "label": local.strftime("%d.%m.%Y"),
                                         "lines": 0, "recognized": 0, "unknown": 0, "error": 0, "events": []}

                    day = days[day_key]
                    day["lines"] += 1
                    day[row["status"]] += 1

                    if selected:
                        event_counts[row["type"]] += 1
                        day["events"].append(TimelineBuilder.event(row, zone))

                        if row['type'] == 'reliquary.message':
                            reliquary_event = day['events'][-1]

                control.report('Prepare timeline', processed, size, total, unit = 'bytes')

        if digest.hexdigest() != expected_sha256:
            raise ValueError('The registry changed while building the timeline')

        summaries = []
        ordered = sorted(days)
        maximum = max((len(day["events"]) for day in days.values()), default = 0)

        for index, day_key in enumerate(ordered):
            day = days[day_key]
            day["events"].sort(key = lambda event: (event["utc"], event["line_number"]))
            day["event_count"] = len(day["events"])
            day["previous"] = ordered[index - 1] if index else None
            day["next"] = ordered[index + 1] if index + 1 < len(ordered) else None
            day["bar_percent"] = round(100 * day["event_count"] / maximum, 2) if maximum else 0
            summaries.append({key: value for key, value in day.items() if key != "events"})

        control.check()

        return {
            "version": TimelineBuilder.TIMELINE_VERSION, "timezone": timezone_name, "total_lines": total,
            "statuses": dict(statuses), "dated_lines": dated, "undated_lines": total - dated,
            "undated_statuses": {key: undated_statuses[key] for key in ("recognized", "unknown", "error")},
            "selected_without_time": selected_without_time, "clock_regressions": regressions,
            "event_count": sum(event_counts.values()), "other_dated_lines": dated - sum(event_counts.values()),
            "first": first.astimezone(zone).isoformat() if first else None,
            "last": last.astimezone(zone).isoformat() if last else None,
            "kinds": [{"type": key, "label": label, "count": event_counts[key]} for key, label in TimelineBuilder.EVENT_TYPES.items()],
            "days": summaries, "by_date": days,
        }
