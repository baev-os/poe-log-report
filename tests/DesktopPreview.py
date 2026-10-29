"""Capture the real desktop window using reproducible synthetic inputs."""

import argparse
import os
import shutil
import subprocess
import sys

from pathlib import Path
from time import monotonic

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from poe_log_analyze.Bootstrap import Bootstrap

from poe_log_analyze.desktop.MainWindow import MainWindow

from poe_log_analyze.runtime.ProcessEnvironment import ProcessEnvironment
from poe_log_analyze.runtime.Workspace import Workspace


class DesktopPreview:
    """Create a documentation screenshot without reading personal logs or settings."""

    @staticmethod
    def main() -> int:
        parser = argparse.ArgumentParser(description = "Capture the Tk desktop with synthetic example logs")
        parser.add_argument("--output", type = Path, default = Path("build/desktop-preview.png"))
        parser.add_argument("--ready", action = "store_true", help = "Capture the configured window before generating reports")
        args = parser.parse_args()
        temporary = Workspace.project_root() / "build/tmp"
        temporary.mkdir(parents = True, exist_ok = True)

        for name in ("TMPDIR", "TEMP", "TMP"):
            os.environ[name] = str(temporary)

        return DesktopPreview().run(args.output, ready = args.ready)

    def run(self, output: Path, *, ready: bool = False) -> int:
        self.output = Workspace.local_output(output)

        if self.output.suffix.lower() != ".png":
            raise ValueError("The preview output must be a PNG inside build/")

        self.scrot = shutil.which("scrot")

        if self.scrot is None:
            raise RuntimeError("Desktop preview requires scrot and a graphical display")

        self.root = Workspace.local_output(Path("build/desktop-preview"))
        self.root.mkdir(parents = True, exist_ok = True)
        self.output.parent.mkdir(parents = True, exist_ok = True)
        sources = []

        for day, name in (("2026/09/01", "Synthetic-Desktop-Client.txt"),
                          ("2026/09/02", "Synthetic-Laptop-Client.txt")):
            source = self.root / name
            source.write_text(self.source_text(day), encoding = "utf-8", newline = "\n")
            sources.append(source)

        self.window = MainWindow(Bootstrap.report_generator(), self.root / "report")
        self.window.inputs.add_files(sources)
        self.window.inputs.set_report_language("en")
        self.window.inputs.set_timezone("UTC")
        self.window.inputs.extended_report.set(True)
        self.window.inputs.period.use_start.set(True)
        self.window.inputs.period.use_end.set(True)
        self.window.inputs.period.start.set("2026-09-01")
        self.window.inputs.period.end.set("2026-09-02")
        self.window.inputs.comparison_period.start.set("2026-08-30")
        self.window.inputs.comparison_period.end.set("2026-08-31")
        self.window.geometry("1060x940+32+32")
        self.started = monotonic()
        self.error = None
        self.captured = False

        if ready:
            self.window.after(500, self.capture)
        else:
            self.window.start_analysis()
            self.window.after(100, self.poll)

        self.window.mainloop()

        if self.error is not None:
            print("Desktop preview failed: " + self.error, file = sys.stderr)
            return 1

        if not self.captured:
            print("Desktop preview closed before a screenshot was captured", file = sys.stderr)
            return 1

        print(self.output)

        return 0

    @staticmethod
    def source_text(day: str) -> str:
        return "".join(f"{day} {stamp} 123 abcd [INFO Client 42] {message}\n" for stamp, message in (
            ("21:00:00", "Client-Safe Instance ID = 123"),
            ("21:00:00", 'Generating level 83 area "MapWorldsBeach" with seed 456'),
            ("21:00:03", ": You have entered Synthetic Beach."),
            ("21:02:10", "Sister Cassia: Synthetic example dialogue."),
            ("21:05:00", ": 12 monsters remain."),
            ("21:08:00", 'Generating level 60 area "HideoutOssuary" with seed 789'),
            ("21:08:03", ": You have entered Synthetic Hideout."),
            ("21:08:12", "@From SyntheticTrader: Synthetic example trade message."),
            ("21:08:20", ": Trade accepted."),
            ("21:08:25", ": 7 Items identified"),
            ("21:10:00", "Abnormal disconnect: Synthetic end of session"),
        ))

    def poll(self) -> None:
        if self.window.closed:
            return

        if monotonic() - self.started > 120:
            self.error = "Synthetic report generation exceeded 120 seconds"
            self.window.close()
            return

        if self.window.task is not None:
            self.window.after(100, self.poll)
            return

        if self.window.session.report_path is None:
            self.error = self.window.progress.message.get()
            self.window.close()
            return

        self.window.after(500, self.capture)

    def capture(self) -> None:
        try:
            self.window.update_idletasks()
            self.window.lift()
            x, y = self.window.winfo_rootx(), self.window.winfo_rooty()
            width, height = self.window.winfo_width(), self.window.winfo_height()
            rectangle = f"{x},{y},{width},{height}"
            self.output.unlink(missing_ok = True)
            subprocess.run([self.scrot, "-a", rectangle, str(self.output)], check = True,
                           env = ProcessEnvironment.within(self.root), timeout = 20)

            with self.output.open("rb") as stream:
                if stream.read(8) != b"\x89PNG\r\n\x1a\n":
                    raise ValueError("The screenshot tool did not produce a PNG")

            self.captured = True
        except Exception as error:
            self.error = str(error)
        finally:
            self.window.close()


if __name__ == "__main__":
    raise SystemExit(DesktopPreview.main())
