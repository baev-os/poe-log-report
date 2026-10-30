from pathlib import Path
from tempfile import TemporaryDirectory

from poe_log_analyze.stages.parsing.LogAnalysisService import LogAnalysisService

from poe_log_analyze.runtime.JsonFiles import JsonFiles

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext

class CollectionAnalysisService:
    """Independent analysis collection: preserve each selected file without deduplication."""

    @staticmethod
    def analyze_collection(inputs: tuple[Path, ...] | list[Path], output: Path, timezone_name: str = "Europe/London",
                           *, control: ExecutionContext | None = None,
                           require_complete: bool = False) -> Path:
        """Create the collection atomically; repeated paths and identical bytes remain separate inputs."""

        control = control or ExecutionContext()
        output = Path(output).resolve()
        paths = [Path(path).resolve(strict = True) for path in inputs]

        if not paths:
            raise ValueError('Add at least one file')

        if output.exists():
            raise FileExistsError('The collection directory already exists')

        if any(path.is_relative_to(output) for path in paths):
            raise ValueError('The collection directory cannot contain source files')

        output.parent.mkdir(parents = True, exist_ok = True)

        with TemporaryDirectory(prefix = ".collection-", dir = output.parent) as temporary:
            target = Path(temporary) / "result"
            target.mkdir()
            sources = []

            for number, path in enumerate(paths, 1):
                control.check()
                control.report(f"File {number} of {len(paths)}: {path.name}", force = True)
                relative = f"sources/{number:04d}"
                LogAnalysisService.analyze(path, target / relative, timezone_name,
                        source_label = path.stem, require_complete = require_complete, control = control)
                sources.append({"path": relative, "label": path.stem})

            JsonFiles.write_json(target / "collection.json", {"collection_version": "1", "sources": sources,
                                                    "overlap_policy": "shared_prefix_v2"})
            control.check()
            target.rename(output)

        return output
