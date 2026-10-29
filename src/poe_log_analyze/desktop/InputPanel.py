"""Run parameters in a compact ttk interface."""

import tkinter as tk

from tkinter import filedialog, ttk

from poe_log_analyze.core.request.ReportLanguage import ReportLanguage
from poe_log_analyze.core.request.ReportOutputs import ReportOutputs

from poe_log_analyze.desktop.FileList import FileList
from poe_log_analyze.desktop.PeriodInput import PeriodInput
from poe_log_analyze.desktop.TimezoneCatalogue import TimezoneCatalogue

from poe_log_analyze.runtime.Workspace import Workspace


class InputPanel(ttk.Frame):
    """Read parameters on the main thread before creating the request."""

    def __init__(self, parent):
        super().__init__(parent)

        self.enabled = True
        self.columnconfigure(1, weight = 1)
        self.files = FileList(self)
        self.files.grid(row = 0, column = 0, columnspan = 2, sticky = "ew")

        buttons = ttk.Frame(self)
        buttons.grid(row = 1, column = 0, columnspan = 2, sticky = "ew", pady = (5, 10))

        self.select_file = ttk.Button(buttons, text = 'Add logs…', command = self.choose_files)
        self.remove_file = ttk.Button(buttons, text = 'Remove selected', command = self.files.remove_selected)
        self.select_file.pack(side = tk.LEFT)
        self.remove_file.pack(side = tk.LEFT, padx = 6)
        self.timezones = TimezoneCatalogue.timezone_options()
        self.timezone = ttk.Combobox(self, values = [option.label for option in self.timezones],
                                     state = "readonly", height = 16, width = 40)
        self.set_timezone("Asia/Almaty")

        ttk.Label(self, text = 'Log time zone:').grid(row = 2, column = 0, sticky = "w", padx = (0, 10))

        self.timezone.grid(row = 2, column = 1, sticky = "ew", pady = 3)
        self.languages = tuple(ReportLanguage.LABELS)
        self.report_language = ttk.Combobox(self, values = list(ReportLanguage.LABELS.values()), state = "readonly")
        self.set_report_language("en")

        ttk.Label(self, text = 'Report language:').grid(row = 3, column = 0, sticky = "w")

        self.report_language.grid(row = 3, column = 1, sticky = "ew", pady = 3)
        reports = ttk.Frame(self)
        reports.grid(row = 4, column = 0, columnspan = 2, sticky = "ew", pady = (6, 3))
        self.basic_report = tk.BooleanVar(self, True)
        self.extended_report = tk.BooleanVar(self, False)
        self.report_checks = []

        for row, (label, variable) in enumerate((
                ('Basic report', self.basic_report),
                ('Extended report', self.extended_report))):
            check = ttk.Checkbutton(reports, text = label, variable = variable)
            check.grid(row = row, column = 0, sticky = "w", padx = (0, 20), pady = 3)
            self.report_checks.append(check)

        self.pdf_dark = tk.BooleanVar(self, False)
        self.pdf_dark_check = ttk.Checkbutton(reports, text = 'Dark theme for PDFs and area image',
                                              variable = self.pdf_dark)
        self.pdf_dark_check.grid(row = 2, column = 0, columnspan = 2, sticky = "w", pady = (4, 0))
        self.report_checks.append(self.pdf_dark_check)

        self.period_panel = ttk.Frame(self)
        self.period_panel.grid(row = 5, column = 0, columnspan = 2, sticky = "ew", pady = 5)

        ttk.Label(self.period_panel, text = 'Report period:').grid(row = 0, column = 0, sticky = "w", pady = 3)

        self.period = PeriodInput(self.period_panel)
        self.period.grid(row = 1, column = 0, sticky = "w")
        self.compare = tk.BooleanVar(self, False)
        self.compare_check = ttk.Checkbutton(self.period_panel, text = 'Compare with period A (extended report)', variable = self.compare)
        self.compare_check.grid(row = 2, column = 0, sticky = "w", pady = (8, 3))
        self.comparison_period = PeriodInput(self.period_panel)
        self.comparison_period.grid(row = 3, column = 0, sticky = "w")
        self.compare.trace_add("write", self.update_comparison)
        self.update_comparison()
        self.workspace = tk.StringVar(self, str(Workspace.default_workspace()))

        ttk.Label(self, text = 'Output:').grid(row = 6, column = 0, sticky = "w", pady = (5, 0))

        self.workspace_entry = ttk.Entry(self, textvariable = self.workspace, state = "readonly")
        self.workspace_entry.grid(row = 6, column = 1, sticky = "ew", pady = (5, 0))

    def paths(self):
        return self.files.paths()

    def add_files(self, paths) -> None:
        self.files.add_files(paths)

    def choose_files(self) -> None:
        paths = filedialog.askopenfilenames(parent = self.winfo_toplevel(), title = 'Add logs',
                                            filetypes = (('Log files', "*.txt *.log"), ('All files', "*")))
        self.add_files(paths)

    def set_timezone(self, key: str) -> None:
        self.timezone.current(next(index for index, option in enumerate(self.timezones) if option.key == key))

    def timezone_key(self) -> str:
        return self.timezones[self.timezone.current()].key

    def set_report_language(self, code: str) -> None:
        self.report_language.current(self.languages.index(code))

    def language_code(self) -> str:
        return self.languages[self.report_language.current()]

    def update_comparison(self, *_args) -> None:
        self.comparison_period.set_enabled(self.enabled and self.compare.get())

    def outputs(self) -> ReportOutputs:
        basic = self.basic_report.get()
        extended = self.extended_report.get()
        return ReportOutputs(basic = basic, basic_pdf = basic, extended = extended, extended_pdf = extended)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.files.set_enabled(enabled)

        for widget in (self.select_file, self.remove_file, self.compare_check, *self.report_checks):
            widget.state(["!disabled" if enabled else "disabled"])

        for combo in (self.timezone, self.report_language):
            combo.configure(state = "readonly" if enabled else "disabled")

        self.period.set_enabled(enabled)
        self.update_comparison()
