class VisitMeasurements:
    """Measured spans of one entry; branch spans are not new visits."""

    @staticmethod
    def parts(visit: dict) -> list[dict]:
        if 'segments' in visit:
            return visit['segments']

        bounded = visit.get('bounded', bool(visit.get('entered_at') and visit.get('ended_at')))

        return [visit] if bounded and visit['seconds'] is not None else []

    @staticmethod
    def seconds(visit: dict) -> float:
        return sum(part['seconds'] for part in VisitMeasurements.parts(visit))

    @staticmethod
    def drawable(visit: dict) -> list[dict]:
        parts = VisitMeasurements.parts(visit)

        if not visit['bounded']:
            return [*parts, {**visit, 'ended_at': None, 'seconds': None}]

        return parts
