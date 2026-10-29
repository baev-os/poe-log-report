from tkinter import font, ttk


class DesktopStyle:
    """Increase system fonts while respecting scaling and screen size."""

    @staticmethod
    def apply(window) -> None:
        style = ttk.Style(window)

        if window.tk.call('tk', 'windowingsystem') == 'x11':
            style.theme_use('clam')

        for name in ('TkDefaultFont', 'TkTextFont', 'TkFixedFont', 'TkMenuFont',
                     'TkHeadingFont', 'TkCaptionFont', 'TkSmallCaptionFont', 'TkTooltipFont'):
            named = font.nametofont(name, root = window)
            size = named.actual('size')
            named.configure(size = max(size, min(16, max(12, size + 2))) if size > 0 else size - 3)

        default = font.nametofont('TkDefaultFont', root = window)
        style.configure('TButton', padding = (12, 6))
        style.configure('TEntry', padding = (6, 4))
        style.configure('TCombobox', padding = (6, 4), arrowsize = max(16, default.metrics('linespace')))
        style.configure('TCheckbutton', padding = (0, 3), indicatorsize = max(18, default.metrics('linespace')))
        style.configure('TProgressbar', thickness = 18)
        style.configure('ProgressHeading.TLabel', font = (default.actual('family'), default.actual('size'), 'bold'))

        window.resizable(True, True)

    @staticmethod
    def available_size(window) -> tuple[int, int]:
        line = font.nametofont('TkDefaultFont', root = window).metrics('linespace')
        maximum_width, maximum_height = window.maxsize()
        width = min(maximum_width, window.winfo_screenwidth() - 48)
        height = min(maximum_height, window.winfo_screenheight() - max(96, 3 * line + 32))
        return max(1, width), max(1, height)
