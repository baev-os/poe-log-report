"""Independent examples of time boundaries, line links, and selected events."""


class TimelineFixture:
    """Synthetic inputs and test helpers."""

    @staticmethod
    def message(stamp, text):
        """Construct a synthetic client header."""

        return f"{stamp} 123 abcd [INFO Client 42] {text}\n"
