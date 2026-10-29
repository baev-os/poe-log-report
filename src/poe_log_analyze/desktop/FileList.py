"""Small scrollable list of selected files."""

import tkinter as tk

from pathlib import Path

from tkinter import ttk


class FileList(ttk.Frame):
    """Preserve ordering and repeated inputs until application-level source validation."""

    def __init__(self, parent):
        super().__init__(parent)

        self.list = tk.Listbox(self, height = 3, width = 58, selectmode = tk.EXTENDED, exportselection = False)
        scrollbar = ttk.Scrollbar(self, orient = tk.VERTICAL, command = self.list.yview)
        self.list.configure(yscrollcommand = scrollbar.set)
        self.list.grid(row = 0, column = 0, sticky = "nsew")
        scrollbar.grid(row = 0, column = 1, sticky = "ns")
        self.columnconfigure(0, weight = 1)

    def add_files(self, paths) -> None:
        for path in paths:
            self.list.insert(tk.END, str(Path(path).resolve()))

    def paths(self) -> tuple[Path, ...]:
        return tuple(Path(value) for value in self.list.get(0, tk.END))

    def remove_selected(self) -> None:
        for index in reversed(self.list.curselection()):
            self.list.delete(index)

    def set_enabled(self, enabled: bool) -> None:
        self.list.configure(state = tk.NORMAL if enabled else tk.DISABLED)
