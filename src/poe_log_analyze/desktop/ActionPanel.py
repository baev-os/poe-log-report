"""Current-session actions."""

from tkinter import ttk


class ActionPanel(ttk.Frame):
    """Button availability follows operation state and the available report."""

    def __init__(self, parent, start, view_report, cancel):
        super().__init__(parent)

        self.start = ttk.Button(self, text = 'Analyze', command = start)
        self.view_report = ttk.Button(self, text = 'Open report', command = view_report)
        self.cancel = ttk.Button(self, text = 'Cancel', command = cancel)

        for column, button in enumerate((self.start, self.view_report, self.cancel)):
            button.grid(row = 0, column = column, padx = (0, 6), sticky = "ew")
            self.columnconfigure(column, weight = 1)

    def update_available(self, busy: bool, has_report: bool) -> None:
        for button, enabled in ((self.start, not busy), (self.view_report, not busy and has_report), (self.cancel, busy)):
            button.state(["!disabled" if enabled else "disabled"])
