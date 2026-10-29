"""Launch the compact desktop interface."""

import sys

from poe_log_analyze.Bootstrap import Bootstrap


class DesktopApplication:
    """Create the Tk window and start its single event loop."""

    @staticmethod
    def main() -> int:
        try:
            import tkinter as tk
        except ModuleNotFoundError:
            print('Tkinter is missing from this Python installation. Install Tcl/Tk as described in README.md.', file = sys.stderr)
            return 1

        from poe_log_analyze.desktop.MainWindow import MainWindow

        try:
            window = MainWindow(Bootstrap.report_generator())
        except tk.TclError as error:
            print('Could not open the Tkinter window: ' + str(error), file = sys.stderr)
            return 1

        window.mainloop()

        return 0
