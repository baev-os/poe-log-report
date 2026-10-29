import json

from pathlib import Path

class JsonFiles:
    """Deterministic JSON artifact writing."""

    @staticmethod
    def write_json(path: Path, value: dict) -> None:
        """Stream JSON fragments without keeping a complete serialized model in memory."""

        with path.open("w", encoding = "utf-8", newline = "\n") as stream:
            json.dump(value, stream, ensure_ascii = False, sort_keys = True, indent = 2)
            stream.write("\n")
