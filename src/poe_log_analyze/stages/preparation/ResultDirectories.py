import json

from pathlib import Path

class ResultDirectories:
    """Read a portable result collection and validate its paths."""

    @staticmethod
    def result_directories(directory: Path) -> list[Path]:
        """Open a single analysis or portable collection with relative paths."""

        directory = Path(directory).resolve(strict = True)
        path = directory / "collection.json"

        if not path.is_file():
            return [directory]

        value = json.loads(path.read_text(encoding = "utf-8"))

        if value["collection_version"] != "1" or value["overlap_policy"] not in ("keep_all", "shared_prefix_v1", "shared_prefix_v2"):
            raise ValueError('Unsupported collection version or policy')

        results = []

        for source in value["sources"]:
            child = (directory / source["path"]).resolve(strict = True)

            if not child.is_relative_to(directory) or child == directory:
                raise ValueError('Source results must remain inside the collection')

            results.append(child)

        if not results:
            raise ValueError('The collection contains no sources')

        return results
