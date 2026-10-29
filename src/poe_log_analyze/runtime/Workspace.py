import json

from pathlib import Path

class Workspace:
    """Local result workspace independent of cwd and the home directory."""

    @staticmethod
    def project_root() -> Path:
        """Find the project above the module; use the distribution directory after relocation."""

        module = Path(__file__).resolve()
        package = module.parents[1]
        metadata = package / "resources/build-info.json"

        if metadata.is_file():
            build = json.loads(metadata.read_text(encoding = "utf-8"))

            if build.get("distribution_layout") == "app":
                return package.parent.parent

            return package.parent

        for parent in module.parents:
            if (parent / "pyproject.toml").is_file() and (parent / "src/poe_log_analyze").is_dir():
                return parent

        raise RuntimeError('Project or standalone distribution directory not found')

    @staticmethod
    def local_output(path: Path) -> Path:
        """Allow writes only within project build/, including after symlink resolution."""

        root = Workspace.project_root()
        base = root / "build"
        target = Path(path)

        if not target.is_absolute():
            target = root / target

        target = target.resolve()

        if not base.resolve().is_relative_to(root) or not target.is_relative_to(base.resolve()):
            raise ValueError(f"Results must be inside {base}")

        return target

    @staticmethod
    def default_workspace() -> Path:
        """Single current report beside the external launcher."""

        return Workspace.project_root() / "report"

    @staticmethod
    def current_report_output(path: Path) -> Path:
        """Allow report/ at the application root or under build/ for checks."""

        root = Workspace.project_root().resolve()
        target = Path(path)

        if not target.is_absolute():
            target = root / target

        if target.is_symlink() or target.name != "report":
            raise ValueError('The current report must be a regular report directory')

        target = target.resolve()

        if target.parent != root:
            Workspace.local_output(target)

        if (target.parent / "index.html").is_symlink():
            raise ValueError('index.html must not be a symbolic link')

        return target
