"""Anonymous version-6 formats, rule boundaries, and continuation order."""


class RulesV6Fixture:
    """Synthetic inputs and test helpers."""

    @staticmethod
    def message(text):
        """Synthetic header and CRLF without user data."""

        return f"2026/09/01 10:00:00 123 abcd [INFO Client 42] {text}\r\n".encode()
