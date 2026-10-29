from tkinter import font

from poe_log_analyze.desktop.DesktopStyle import DesktopStyle


class WindowLayout:
    """Choose the initial layout from content, font metrics, and screen dimensions."""

    def __init__(self, window, viewport, actions, progress):
        self.window = window
        self.viewport = viewport
        self.actions = actions
        self.progress = progress
        self.container = viewport.master
        self.pending = None
        self.side = None
        self.gap = 10
        self.padding = 2 * self.container.winfo_pixels(self.container.cget('padding')[0])

        viewport.request_content_size()
        window.update_idletasks()
        self.input_width = viewport.inputs.winfo_reqwidth()
        self.input_height = viewport.inputs.winfo_reqheight()
        self.journal_width = max(progress.journal_title.winfo_reqwidth() + progress.copy.winfo_reqwidth() + self.gap,
                                 font.nametofont('TkTextFont', root = window).measure('0') * 36 + 24)
        self.side_width = self.input_width + self.journal_width + self.gap + self.padding

        self.place(False)
        window.update_idletasks()
        self.menu_height = max(0, window.winfo_reqheight() - self.container.winfo_reqheight())
        vertical_height = self.content_height() + self.padding + self.menu_height
        maximum_width, maximum_height = DesktopStyle.available_size(window)
        side = vertical_height > maximum_height and self.side_width <= maximum_width

        if side and self.input_height + actions.winfo_reqheight() + self.gap + self.padding > maximum_height:
            viewport.inputs.files.list.configure(height = 2)
            viewport.request_content_size()
            window.update_idletasks()
            self.input_height = viewport.inputs.winfo_reqheight()

        self.place(side)
        progress.wrap_text(self.journal_width if side else max(1060, self.input_width + self.padding) - self.padding)
        window.update_idletasks()

        width = self.side_width if side else max(1060, self.input_width + self.padding)
        height = self.content_height() + self.padding + self.menu_height
        width, height = min(width, maximum_width), min(height, maximum_height)
        window.geometry(f'{width}x{height}')
        window.minsize(min(max(820, self.input_width + self.padding), width), min(660, height))
        window.bind('<Configure>', self.schedule_resize, add = '+')

    def content_height(self) -> int:
        left = self.input_height + self.actions.winfo_reqheight() + self.gap

        if self.side:
            return max(left, self.progress.winfo_reqheight())

        return left + self.progress.winfo_reqheight() + self.gap

    def place(self, side: bool) -> None:
        if self.side == side:
            return

        self.side = side

        for widget in (self.viewport, self.actions, self.progress):
            widget.grid_forget()

        self.container.columnconfigure(0, weight = 1)
        self.container.columnconfigure(1, weight = 1 if side else 0, minsize = self.journal_width if side else 0)
        self.container.rowconfigure(0, weight = 1)
        self.container.rowconfigure(1, weight = 0)
        self.container.rowconfigure(2, weight = 0 if side else 1)

        self.viewport.grid(row = 0, column = 0, sticky = 'nsew',
                           padx = (0, self.gap if side else 0), pady = (0, self.gap))
        self.actions.grid(row = 1, column = 0, sticky = 'ew',
                          padx = (0, self.gap if side else 0), pady = (0, 0 if side else self.gap))
        self.progress.grid(row = 0 if side else 2, column = 1 if side else 0,
                           rowspan = 2 if side else 1, sticky = 'nsew')

    def schedule_resize(self, event) -> None:
        if event.widget == self.window and self.pending is None:
            self.pending = self.window.after_idle(self.resize)

    def resize(self) -> None:
        self.pending = None
        width = self.container.winfo_width() - self.padding
        height = self.container.winfo_height() - self.padding
        vertical_height = self.input_height + self.actions.winfo_reqheight() + self.progress.winfo_reqheight() + 2 * self.gap
        side = width >= self.side_width - self.padding and height < vertical_height
        self.place(side)

        if not side:
            self.container.rowconfigure(0, weight = 0 if height >= vertical_height else 1)
            self.container.rowconfigure(2, weight = 1 if height >= vertical_height else 0)

    def close(self) -> None:
        if self.pending is not None:
            self.window.after_cancel(self.pending)
            self.pending = None
