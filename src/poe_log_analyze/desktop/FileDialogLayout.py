from tkinter import font

from poe_log_analyze.desktop.DesktopStyle import DesktopStyle


class FileDialogLayout:
    """Scale the standard Tk dialog without replacing native system dialogs."""

    def __init__(self, window):
        self.window = window

        if window.tk.call('tk', 'windowingsystem') == 'x11':
            window.bind_class('TkFDialog', '<Map>', self.fit, add = '+')

    def fit(self, event) -> None:
        dialog = str(event.widget)
        tk = self.window.tk
        maximum_width, maximum_height = DesktopStyle.available_size(self.window)
        text = font.nametofont('TkTextFont', root = self.window)
        width = min(text.measure('0') * 84, max(1, maximum_width - 40))
        height = min(text.metrics('linespace') * 12, maximum_height // 2)

        for widget in self.descendants(dialog):
            kind = tk.call('winfo', 'class', widget)

            if kind == 'Canvas':
                tk.call(widget, 'configure', '-width', width, '-height', height)
            elif kind == 'TMenubutton':
                # Flush places the current folder under the pointer: releasing
                #  the mouse selects it immediately and closes the newly opened list.
                tk.call(widget, 'configure', '-direction', 'below')

        self.window.update_idletasks()
        width = min(int(tk.call('winfo', 'reqwidth', dialog)), maximum_width)
        height = min(int(tk.call('winfo', 'reqheight', dialog)), maximum_height)
        x = self.window.winfo_rootx() + (self.window.winfo_width() - width) // 2
        y = self.window.winfo_rooty() + (self.window.winfo_height() - height) // 2
        x = max(0, min(x, self.window.winfo_screenwidth() - width - 24))
        y = max(0, min(y, self.window.winfo_screenheight() - height - 64))
        tk.call('wm', 'geometry', dialog, f'{width}x{height}+{x}+{y}')

    def descendants(self, parent) -> list[str]:
        children = self.window.tk.call('winfo', 'children', parent)
        result = []

        for child in children:
            result.append(str(child))
            result.extend(self.descendants(child))

        return result
