from math import ceil
from statistics import mean, median


class ObservationSamples:
    """Numeric observations: median and nearest-rank P95 without interpolating missing data."""

    @staticmethod
    def build(values) -> dict:
        ordered = sorted(value for value in values if value is not None)
        return {'count': len(ordered), 'small_sample': len(ordered) < 20,
                'median': median(ordered) if ordered else None, 'mean': mean(ordered) if ordered else None,
                'min': ordered[0] if ordered else None, 'max': ordered[-1] if ordered else None,
                'p95': ordered[ceil(.95 * len(ordered)) - 1] if ordered else None}
