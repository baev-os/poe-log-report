"""Checks use synthetic data without the user's original log."""


class AnalysisFixture:
    """Synthetic inputs and test helpers."""

    @staticmethod
    def message(text: str, stamp: str = "2026/09/01 10:00:00") -> bytes:
        """Create a synthetic line with a client header."""

        return f"{stamp} 123 abcd [INFO Client 42] {text}\n".encode()
