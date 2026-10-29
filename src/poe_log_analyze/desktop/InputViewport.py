import tkinter as tk

from tkinter import ttk

from poe_log_analyze.desktop.InputPanel import InputPanel


class InputViewport(ttk.Frame):
    """Scroll parameters while keeping actions and the journal visible."""

    def __init__(self, parent):
        super().__init__(parent)

        self.canvas = tk.Canvas(self, highlightthickness = 0)
        self.scrollbar = ttk.Scrollbar(self, orient = tk.VERTICAL, command = self.canvas.yview)
        self.canvas.configure(yscrollcommand = self.update_scrollbar, background = ttk.Style(self).lookup('TFrame', 'background'))
        self.canvas.grid(row = 0, column = 0, sticky = 'nsew')
        self.scrollbar.grid(row = 0, column = 1, sticky = 'ns')
        self.columnconfigure(0, weight = 1)
        self.rowconfigure(0, weight = 1)

        self.inputs = InputPanel(self.canvas)
        self.item = self.canvas.create_window((0, 0), window = self.inputs, anchor = 'nw')

        self.inputs.bind('<Configure>', self.update_region)
        self.canvas.bind('<Configure>', self.update_width)
        self.wheel_tag = 'InputScroll' + str(id(self))
        self.bind_class(self.wheel_tag, '<MouseWheel>', self.scroll)
        self.bind_class(self.wheel_tag, '<Button-4>', self.scroll)
        self.bind_class(self.wheel_tag, '<Button-5>', self.scroll)
        self.bind_wheel(self.inputs)

    def bind_wheel(self, widget) -> None:
        if not isinstance(widget, (tk.Listbox, ttk.Combobox)):
            widget.bindtags((*widget.bindtags(), self.wheel_tag))

        for child in widget.winfo_children():
            self.bind_wheel(child)

    def update_width(self, event) -> None:
        self.canvas.itemconfigure(self.item, width = event.width)

    def request_content_size(self) -> None:
        self.inputs.update_idletasks()
        self.canvas.configure(width = self.inputs.winfo_reqwidth(), height = self.inputs.winfo_reqheight())

    def update_scrollbar(self, first, last) -> None:
        self.scrollbar.set(first, last)

        if float(first) <= 0 and float(last) >= 1:
            self.scrollbar.grid_remove()
        else:
            self.scrollbar.grid()

    def update_region(self, _event) -> None:
        self.canvas.configure(scrollregion = self.canvas.bbox('all'))

    def scroll(self, event) -> str:
        if self.inputs.winfo_height() > self.canvas.winfo_height():
            direction = -1 if getattr(event, 'num', None) == 4 or getattr(event, 'delta', 0) > 0 else 1
            self.canvas.yview_scroll(direction * 3, 'units')

        return 'break'
