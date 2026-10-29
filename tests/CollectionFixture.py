"""Collections preserve duplicates, provenance, complete duration, and atomicity."""


class CollectionFixture:
    """Synthetic inputs and test helpers."""

    @staticmethod
    def line(seconds, message):
        """Write a second-resolution timestamp in a synthetic log."""

        hours, rest = divmod(seconds, 3600)
        minutes, seconds = divmod(rest, 60)

        return f"2026/09/01 {hours:02}:{minutes:02}:{seconds:02} 1 abcd [INFO Client 1] {message}\n"
