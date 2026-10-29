"""Optional calendar boundaries in ISO format."""

import tkinter as tk

from datetime import date

from tkinter import ttk

from poe_log_analyze.core.request.ReportPeriod import ReportPeriod


class PeriodInput(ttk.Frame):
    """Use the entire history by default; validate input before starting."""

    def __init__(self, parent):
        super().__init__(parent)

        self.enabled = True
        self.use_start = tk.BooleanVar(self, False)
        self.use_end = tk.BooleanVar(self, False)
        self.start = tk.StringVar(self, date.today().isoformat())
        self.end = tk.StringVar(self, date.today().isoformat())
        self.start_check = ttk.Checkbutton(self, text = 'From', variable = self.use_start)
        self.start_entry = ttk.Entry(self, textvariable = self.start, width = 12)
        self.end_check = ttk.Checkbutton(self, text = 'to', variable = self.use_end)
        self.end_entry = ttk.Entry(self, textvariable = self.end, width = 12)

        for column, widget in enumerate((self.start_check, self.start_entry, self.end_check, self.end_entry)):
            widget.grid(row = 0, column = column, padx = (0, 6), sticky = "w")

        ttk.Label(self, text = 'YYYY-MM-DD, inclusive').grid(row = 0, column = 4, sticky = "w")

        self.use_start.trace_add("write", self.update_enabled)
        self.use_end.trace_add("write", self.update_enabled)
        self.update_enabled()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.update_enabled()

    def update_enabled(self, *_args) -> None:
        for checkbox, entry, selected in ((self.start_check, self.start_entry, self.use_start),
                                          (self.end_check, self.end_entry, self.use_end)):
            checkbox.state(["!disabled" if self.enabled else "disabled"])
            entry.state(["!disabled" if self.enabled and selected.get() else "disabled"])

    def value(self) -> ReportPeriod:
        try:
            start = date.fromisoformat(self.start.get().strip()) if self.use_start.get() else None
            end = date.fromisoformat(self.end.get().strip()) if self.use_end.get() else None
        except ValueError as error:
            raise ValueError('Enter a date in YYYY-MM-DD format, for example 2026-09-01') from error

        return ReportPeriod(start, end)
