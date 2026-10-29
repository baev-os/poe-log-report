"""Application tables: time, repeated entries, midnight, and incomplete runs."""


class MapStatisticsFixture:
    """Synthetic inputs and test helpers."""

    @staticmethod
    def run(number, entered, exited, seconds, kind = "Карта", incomplete = 0):
        """Construct a minimal map-model contract record."""

        return {"id": number, "kind": kind, "name": "Test Map", "started_at": entered,
                "seconds": seconds, "unbounded_visits": incomplete,
                "visits": [{"entered_at": entered, "ended_at": exited,
                            "bounded": not incomplete, "seconds": None if incomplete else seconds}]}
