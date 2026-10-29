"""Run the documented source checks sequentially and retain their evidence."""

import argparse
import json
import os
import subprocess
import sys

from pathlib import Path


class CheckSuite:
    """One entry point shared by local checks and CI."""

    @staticmethod
    def main() -> int:
        parser = argparse.ArgumentParser(description = "Run unit, type, and optional browser checks")
        parser.add_argument("--browser", action = "store_true")
        parser.add_argument("--output", type = Path, default = Path("build/checks"))
        args = parser.parse_args()
        root = Path(__file__).resolve().parents[3]
        output = (root / args.output).resolve()

        if not output.is_relative_to(root / "build"):
            raise ValueError("Check results must be inside build/")

        output.mkdir(parents = True, exist_ok = True)
        temporary = root / "build/tmp"
        temporary.mkdir(parents = True, exist_ok = True)
        environment = dict(os.environ, TMPDIR = str(temporary), TEMP = str(temporary), TMP = str(temporary),
                           PYTHONPATH = str(root / "src"), PYTHONDONTWRITEBYTECODE = "1", PYTHONUTF8 = "1")
        commands = [
            ("unit", [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "*Tests.py", "-v"]),
            ("mypy", [sys.executable, "-B", "-m", "mypy"]),
        ]

        if args.browser:
            if sys.platform != "linux":
                raise ValueError("The browser harness requires Linux")

            commands.extend((path.stem, [sys.executable, "-B", str(path), "--output", str(output / "browser" / path.stem)])
                            for path in sorted((root / "tests").glob("*BrowserCheck.py")))

        results = {}

        for name, command in commands:
            print("Running " + name, flush = True)

            with (output / (name + ".log")).open("w", encoding = "utf-8") as log:
                result = subprocess.run(command, cwd = root, env = environment, stdout = log, stderr = subprocess.STDOUT)

            results[name] = {"exit_code": result.returncode, "log": name + ".log"}
            (output / "results.json").write_text(json.dumps(results, indent = 2) + "\n", encoding = "utf-8")

            if result.returncode:
                print((output / (name + ".log")).read_text(encoding = "utf-8", errors = "replace")[-12000:])
                return result.returncode

        print("All source checks passed", flush = True)

        return 0
