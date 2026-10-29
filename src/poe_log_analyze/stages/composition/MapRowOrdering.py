from datetime import datetime, timezone

class MapRowOrdering:
    """Map helpers: distinguish known durations from sequence positions."""

    @staticmethod
    def moment(value):
        """Read only a known timestamp without replacing a missing value with a neighboring time."""

        return datetime.fromisoformat(value) if value else None

    @staticmethod
    def ordered_rows(rows):
        """Sort by entry or exit; use ordering hints when both are unknown."""

        groups = {}

        for index, row in enumerate(rows):
            # Actual timestamps always take precedence over generation or neighboring-record hints.
            row["_anchor"] = row["entered_at"] or row["exited_at"] or row["_anchor"]
            groups.setdefault(row.get("source", ""), []).append((index, row))

        positioned = []
        infinity = datetime.max.replace(tzinfo = timezone.utc)

        for source, values in enumerate(groups.values()):
            # Line numbers locate neighbors without timestamps and break ties.
            # Legacy models without line numbers retain known-time ordering.
            if all(row["_line"] is not None for _, row in values):
                values.sort(key = lambda item: (item[1]["_line"], item[0]))
            else:
                values.sort(key = lambda item: (MapRowOrdering.moment(item[1]["_anchor"]).astimezone(timezone.utc)
                                             if item[1]["_anchor"] else infinity, item[0]))

            following = None
            anchors = [None] * len(values)

            for i in range(len(values) - 1, -1, -1):
                following = MapRowOrdering.moment(values[i][1]["_anchor"]) or following
                anchors[i] = following

            previous = None

            for i, (_, row) in enumerate(values):
                known = MapRowOrdering.moment(row.pop("_anchor"))
                anchor = known or previous or anchors[i]
                previous = known or previous
                row.pop("_line")
                row["position_at"] = anchor.isoformat() if anchor else None
                row["position_note"] = ""

                if not row["entered_at"]:
                    row["position_note"] = ("Время входа неизвестно; положение по выходу"
                                            if row["exited_at"] else
                                            "Время входа и выхода неизвестно; положение приблизительное")

                if anchor is None:
                    row["position_note"] = "Время неизвестно; сохранён порядок записей"

                positioned.append((anchor.astimezone(timezone.utc) if anchor else infinity,
                                   source, i, row))

        positioned.sort(key = lambda item: item[:3])

        return [item[3] for item in positioned]
