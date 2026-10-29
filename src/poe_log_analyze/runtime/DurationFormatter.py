class DurationFormatter:
    """Map helpers: distinguish known durations from sequence positions."""

    @staticmethod
    def duration_label(seconds: float) -> str:
        """Format durations without a 24-hour limit."""

        hours, remainder = divmod(int(seconds), 3600)
        minutes, seconds = divmod(remainder, 60)

        return f"{hours:02}:{minutes:02}:{seconds:02}"
