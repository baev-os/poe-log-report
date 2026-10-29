from pathlib import Path


class LocalResources:
    """Validated resource paths; cache exists only while checking one report."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self._paths: dict[tuple[Path, str], Path] = {}

    def file(self, directory: Path, reference: str) -> Path:
        key = (directory, reference)

        if key not in self._paths:
            path = (directory / reference).resolve()

            if not path.is_relative_to(self.root) or not path.is_file():
                raise ValueError('Report resources must exist within the local site')

            self._paths[key] = path

        return self._paths[key]
