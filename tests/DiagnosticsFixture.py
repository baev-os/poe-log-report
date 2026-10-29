"""Complete review queue, stable groups, and preservation of unknown lines."""


class DiagnosticsFixture:
    """Synthetic inputs and test helpers."""

    @staticmethod
    def message(text, tick = 1, stamp = '2026/09/01 10:00:00'):
        """Create an unknown message with a synthetic header."""

        return f'{stamp} {tick} abcd [INFO Client 42] {text}\n'.encode()
