"""Child-tool environment inside the workspace."""

import os

from pathlib import Path

from poe_log_analyze.runtime.NativePlatform import NativePlatform


class ProcessEnvironment:
    """Pass temporary paths explicitly without changing the environment of running threads."""

    @staticmethod
    def within(directory: Path) -> dict[str, str]:
        env = dict(os.environ)

        temporary = directory / "tmp"
        temporary.mkdir(parents = True, exist_ok = True)

        for key in ("TMPDIR", "TEMP", "TMP"):
            env[key] = str(temporary)

        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        return env

    @staticmethod
    def options() -> dict:
        # CREATE_NO_WINDOW: hide child-process consoles in the Windows GUI.
        return {"creationflags": 0x08000000} if NativePlatform.current().windows else {}
