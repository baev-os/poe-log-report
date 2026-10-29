class ArchitecturePolicy:
    """Stages do not control each other; GUI and CLI call only the shared core."""

    ENTRIES = {"PrepareInputs", "ParseLogs", "ReconstructHistory", "MergeHistory",
               "ComposeReport", "RenderReport", "VerifyReport"}
    OWNERS = {
        "runtime": {"runtime"},
        "core": {"core", "runtime"},
        "stages": {"stages", "core", "runtime"},
        "desktop": {"desktop", "core", "runtime"},
        "cli": {"cli", "core", "desktop"},
        "gui": {"desktop"},
        "tooling": {"tooling", "stages", "core", "runtime"},
    }
    CORE_ZONES = {
        "request": {"request"},
        "result": {"result"},
        "plan": {"plan", "request"},
        "process": {"process", "plan"},
        "execution": {"execution", "process"},
    }

    @staticmethod
    def violation(source: str, target: str) -> str | None:
        owner = source.split(".")[1]

        if target.split(".")[0] in {"PySide6", "shiboken6", "PyQt6", "PyQt5"}:
            return "Qt is excluded from the application"

        if target.split(".")[0] in {"tkinter", "_tkinter"} and owner != "desktop":
            return "Tkinter is allowed only in the desktop interface"

        if not target.startswith("poe_log_analyze."):
            return None

        dependency = target.split(".")[1]
        name = target.rsplit(".", 1)[-1]

        if source == "poe_log_analyze.core.ReportGenerator" and dependency == "stages":
            return None

        if dependency == "Bootstrap":
            if source in {"poe_log_analyze.cli.AnalysisCli", "poe_log_analyze.cli.ReportCli",
                          "poe_log_analyze.desktop.DesktopApplication", "poe_log_analyze.desktop.DesktopSmokeTest"}:
                return None

            return "Dependency composition is allowed only at entry points"

        if dependency not in ArchitecturePolicy.OWNERS.get(owner, set()):
            return "Forbidden dependency direction between packages"

        if owner == "core" and dependency == "core":
            zone = source.split(".")[2]
            target_zone = target.split(".")[2]

            if zone in ArchitecturePolicy.CORE_ZONES and target_zone not in ArchitecturePolicy.CORE_ZONES[zone]:
                return "Core zones must not depend on the coordinator or reverse dependency direction"

        if owner == "stages":
            if dependency == "core" and name in {"ReportGenerator", "GenerationProcess", "ReportWorkspace", "CurrentReport"}:
                return "Stages must not control the process or publication"

            if dependency == "stages" and name in ArchitecturePolicy.ENTRIES:
                if source.split(".")[2] != target.split(".")[2]:
                    return "Stages must not invoke other stages"

        return None
