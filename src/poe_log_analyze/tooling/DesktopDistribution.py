"""Standalone application packaging with one visible launcher."""

from pathlib import Path

from poe_log_analyze.runtime.NativePlatform import NativePlatform


class DesktopDistribution:
    """Preserve the relative layout of the Nuitka binary, libraries, and resources."""

    @staticmethod
    def runtime_directory(distribution: Path) -> Path:
        """Read the new distribution or a legacy flat directory."""

        nested = distribution / "app"
        return nested if (nested / "poe_log_analyze/resources/build-info.json").is_file() else distribution

    @staticmethod
    def arrange(distribution: Path, native: NativePlatform) -> None:
        """Move compiled files together and add a launcher independent of cwd."""

        entries = list(distribution.iterdir())
        runtime = distribution / "app"
        runtime.mkdir(exist_ok = False)

        for entry in entries:
            entry.rename(runtime / entry.name)

        if native.windows:
            launcher = "poe-log-analyze.cmd"
            content = '@echo off\r\nsetlocal\r\n"%~dp0app\\poe-log-analyze.exe" %*\r\nexit /b %errorlevel%\r\n'
        else:
            launcher = native.application_name
            content = ('#!/bin/sh\nset -eu\n'
                       'app_root="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"\n'
                       'exec "$app_root/app/poe-log-analyze" "$@"\n')

        path = distribution / launcher
        path.write_text(content, encoding = "utf-8", newline = "")
        path.chmod(0o755)
        terminal_command = r".\poe-log-analyze.cmd" if native.windows else "./poe-log-analyze"
        (distribution / "README.md").write_text(
            "# PoE Log Analyze\n\n"
            f"To start, open `{launcher}` in this folder.\n"
            f"From a terminal: `{terminal_command}`.\n\n"
            "Add logs, select the time zone and report language, and click Analyze.\n"
            "English is the default; Russian reports are also available.\n"
            "Each selected report includes its PDF automatically.\n"
            "Open the result with Open report or the `index.html` file.\n"
            "The current report is stored in `report/` beside the launcher.\n"
            "A successful analysis replaces the previous report.\n"
            "Errors and cancellation preserve the previous report.\n"
            "Intermediate analyses and temporary files are removed automatically.\n"
            "The application needs write access to this folder.\n\n"
            "The `app/` directory contains the program, libraries, and resources.\n"
            "Copy the entire distribution folder, including `app/`, when moving it.\n\n"
            "Library licenses and source instructions are available from Help > Licenses\n"
            "and in `app/poe_log_analyze/resources/licenses/`.\n"
            "Project license: [LICENSE](app/LICENSE).\n"
            "Third-party resources: [THIRD_PARTY_NOTICES.md](app/THIRD_PARTY_NOTICES.md).\n",
            encoding = "utf-8", newline = "\n")
