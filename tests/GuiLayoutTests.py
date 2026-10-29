"""Initial layout checks for real Tk windows at different DPI settings."""

import importlib.util
import ctypes
import os
import unittest

from ctypes.util import find_library

from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import patch

from poe_log_analyze.Bootstrap import Bootstrap

AVAILABLE = bool(importlib.util.find_spec('_tkinter'))

if AVAILABLE:
    import tkinter as tk

    from tkinter import filedialog, font

    from poe_log_analyze.desktop.DesktopStyle import DesktopStyle
    from poe_log_analyze.desktop.MainWindow import MainWindow


@unittest.skipUnless(AVAILABLE, "Tkinter is required")

class GuiLayoutTests(unittest.TestCase):
    """Parameters and journal fit before the first manual resize."""

    @classmethod
    def setUpClass(cls):
        try:
            probe = tk.Tk()
            probe.destroy()
        except tk.TclError as error:
            raise unittest.SkipTest("A separate graphical display is required: " + str(error)) from error

    def setUp(self):
        self.temp = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build')
        self.root = Path(self.temp.name)
        self.window = None
        self.style = DesktopStyle.apply
        self.scale = 4 / 3
        self.system_font_size = None
        self.dialog_errors = []
        self.selected_files = ()
        self.dialog_attempts = 0

    def tearDown(self):
        if self.window is not None:
            self.window.close()

        self.temp.cleanup()

    def apply_style(self, window):
        window.tk.call('tk', 'scaling', self.scale)

        if self.system_font_size is not None:
            for name in ('TkDefaultFont', 'TkTextFont'):
                font.nametofont(name, root = window).configure(size = self.system_font_size)

        self.style(window)

    def open_window(self, scale = 4 / 3):
        if self.window is not None:
            self.window.close()

        self.scale = scale

        with patch.object(DesktopStyle, 'apply', self.apply_style):
            self.window = MainWindow(Bootstrap.report_generator(), self.root / 'report')

        self.window.update()
        return self.window

    def assert_inside(self, widget, parent):
        self.assertTrue(widget.winfo_ismapped(), str(widget))
        self.assertGreaterEqual(widget.winfo_rootx(), parent.winfo_rootx(), str(widget))
        self.assertGreaterEqual(widget.winfo_rooty(), parent.winfo_rooty(), str(widget))
        self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                             parent.winfo_rootx() + parent.winfo_width(), str(widget))
        self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                             parent.winfo_rooty() + parent.winfo_height(), str(widget))

    def assert_initial_controls_visible(self):
        window = self.window
        viewport = window.viewport
        self.assertGreaterEqual(viewport.canvas.winfo_height(), window.inputs.winfo_reqheight())
        self.assertEqual(viewport.canvas.yview(), (0., 1.))
        self.assertFalse(viewport.scrollbar.winfo_ismapped())

        for path in window.file_dialog_layout.descendants(str(window.inputs)):
            widget = window.nametowidget(path)

            if widget.winfo_ismapped():
                self.assert_inside(widget, viewport.canvas)

        for widget in (window.actions, window.progress, window.progress.copy, window.progress.log):
            self.assert_inside(widget, window)

        line = font.nametofont('TkTextFont', root = window).metrics('linespace')
        self.assertGreaterEqual(window.progress.log.winfo_height(), line * 5)
        self.assertLessEqual(window.winfo_width(), window.winfo_screenwidth() - 48)
        self.assertLessEqual(window.winfo_height(), window.winfo_screenheight() - 64)

    def test_initial_size_shows_every_control(self):
        self.open_window()

        self.assert_initial_controls_visible()

    def test_small_system_fonts_have_readable_minimum(self):
        self.system_font_size = 9
        window = self.open_window()

        for name in ('TkDefaultFont', 'TkTextFont'):
            self.assertGreaterEqual(font.nametofont(name, root = window).actual('size'), 12)

        self.assert_initial_controls_visible()

    def test_short_screen_places_journal_beside_parameters(self):
        with patch.object(DesktopStyle, 'available_size', return_value = (1318, 688)):
            window = self.open_window()

        self.assertLessEqual(window.winfo_height(), 688)
        self.assertGreater(window.progress.winfo_rootx(), window.viewport.winfo_rootx() + window.viewport.winfo_width())
        self.assert_initial_controls_visible()

        window.progress.start()
        window.progress.notice('Создание PDF: синтетический пример, страница 12 из 30')
        window.update()

        self.assert_inside(window.progress.log, window)
        self.assertGreaterEqual(window.progress.log.winfo_height(), 5 * font.nametofont('TkTextFont', root = window).metrics('linespace'))

        window.progress.finish('Проверка завершена', True)

    def test_large_fonts_fit_before_manual_resize(self):
        window = self.open_window()

        if window.winfo_screenwidth() < 1800 or window.winfo_screenheight() < 1080:
            self.skipTest("High-DPI checks require a screen of at least 1800×1080")

        for scale in (2., 8 / 3):
            with self.subTest(scale = scale):
                self.open_window(scale)

                self.assert_initial_controls_visible()

    def test_narrow_resize_keeps_actions_and_scrolling_available(self):
        window = self.open_window()
        window.geometry('850x680')
        window.update()

        self.assert_inside(window.actions, window)
        self.assert_inside(window.progress.log, window)
        self.assertTrue(window.viewport.scrollbar.winfo_ismapped())

        window.viewport.canvas.yview_moveto(1)
        window.update()

        self.assertGreater(window.viewport.canvas.yview()[0], 0)
        self.assert_inside(window.inputs.workspace_entry, window.viewport.canvas)

    def test_file_dialog_fits_fonts_and_selects_multiple_files(self):
        window = self.open_window()

        if window.tk.call('tk', 'windowingsystem') != 'x11':
            self.skipTest("This check targets the standard Tk dialog on X11")

        for name in ('Synthetic One.log', 'Synthetic Two.txt'):
            path = self.root / name
            path.write_text('', encoding = 'utf-8')

        self.selected_files = tuple(str(self.root / name) for name in ('Synthetic One.log', 'Synthetic Two.txt'))

        scales = (4 / 3, 8 / 3) if window.winfo_screenwidth() >= 1800 else (4 / 3,)

        for scale in scales:
            window = self.open_window(scale)

            for _ in range(2):
                self.dialog_attempts = 0
                window.after(100, self.inspect_dialog)
                deadline = window.after(5000, self.cancel_dialog)

                try:
                    paths = filedialog.askopenfilenames(parent = window, title = 'Add logs', initialdir = self.root,
                                                        filetypes = (('Log files', '*.txt *.log'), ('All files', '*')))
                finally:
                    window.after_cancel(deadline)

                self.assertFalse(self.dialog_errors, self.dialog_errors)
                self.assertEqual(set(paths), set(self.selected_files))

    def cancel_dialog(self):
        self.dialog_errors.append('Истекло время ожидания диалога')

        for path in self.window.file_dialog_layout.descendants(str(self.window)):
            if self.window.tk.call('winfo', 'class', path) == 'TkFDialog':
                self.window.tk.eval(self.window.tk.call('wm', 'protocol', path, 'WM_DELETE_WINDOW'))

    def test_file_dialog_menus_stay_open_after_click_and_allow_selection(self):
        if os.environ.get('POE_TEST_NATIVE_INPUT') != '1':
            self.skipTest("Real mouse checks require POE_TEST_NATIVE_INPUT=1 on a separate Xvfb display")

        window = self.open_window()

        if window.tk.call('tk', 'windowingsystem') != 'x11':
            self.skipTest("This mouse check targets the standard Tk dialog on X11")

        if not find_library('Xtst'):
            self.skipTest("Real mouse events require libXtst")

        self.x11 = ctypes.CDLL(find_library('X11'))
        self.xtst = ctypes.CDLL(find_library('Xtst'))
        self.x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.x11.XOpenDisplay.restype = ctypes.c_void_p
        self.x11.XFlush.argtypes = [ctypes.c_void_p]
        self.x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        self.xtst.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
        self.xtst.XTestFakeButtonEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        self.display = self.x11.XOpenDisplay(window.winfo_screen().encode())

        self.assertTrue(self.display)

        self.addCleanup(self.x11.XCloseDisplay, self.display)
        child = self.root / 'child'
        child.mkdir()
        source = self.root / 'Synthetic.log'
        source.touch()
        scales = (4 / 3, 8 / 3) if window.winfo_screenwidth() >= 1800 else (4 / 3,)

        for scale in scales:
            window = self.open_window(scale)

            for click_arrow in (False, True):
                self.click_arrow = click_arrow
                self.menu_stage = 'directory'
                self.dialog_path = None
                window.after(150, self.open_dialog_menu)
                deadline = window.after(5000, self.cancel_dialog)

                try:
                    paths = filedialog.askopenfilenames(parent = window, initialdir = child,
                        filetypes = (('Log files', '*.txt *.log'), ('All files', '*')))
                finally:
                    window.after_cancel(deadline)

                self.assertFalse(self.dialog_errors, self.dialog_errors)
                self.assertEqual(paths, (str(source),))

    def mouse_click(self, x, y):
        self.xtst.XTestFakeMotionEvent(self.display, -1, int(x), int(y), 0)
        self.xtst.XTestFakeButtonEvent(self.display, 1, 1, 0)
        self.x11.XFlush(self.display)
        self.window.after(50, self.release_mouse)

    def release_mouse(self):
        self.xtst.XTestFakeButtonEvent(self.display, 1, 0, 0)
        self.x11.XFlush(self.display)

    def open_dialog_menu(self):
        tk = self.window.tk

        try:
            if self.dialog_path is None:
                self.dialog_path = next(path for path in self.window.file_dialog_layout.descendants('.')
                                        if tk.call('winfo', 'class', path) == 'TkFDialog')
                self.dialog_geometry = tk.call('wm', 'geometry', self.dialog_path)

            buttons = [path for path in self.window.file_dialog_layout.descendants(self.dialog_path)
                       if tk.call('winfo', 'class', path) == 'TMenubutton']
            self.directory_button = buttons[0]
            self.type_button = buttons[1]
            button = buttons[0 if self.menu_stage == 'directory' else 1]
            self.active_menu = str(tk.call(button, 'cget', '-menu'))
            width = int(tk.call('winfo', 'width', button))
            x = int(tk.call('winfo', 'rootx', button)) + (width - 10 if self.click_arrow else width // 2)
            y = int(tk.call('winfo', 'rooty', button)) + int(tk.call('winfo', 'height', button)) // 2
            self.mouse_click(x, y)
            self.window.after(250, self.inspect_dialog_menu)
        except Exception as error:
            self.menu_failure(error)

    def inspect_dialog_menu(self):
        tk = self.window.tk

        try:
            self.assertEqual(int(tk.call('winfo', 'ismapped', self.active_menu)), 1,
                             "The dropdown closed immediately after mouse release: " + self.menu_stage)
            self.assertEqual(tk.call('wm', 'geometry', self.dialog_path), self.dialog_geometry)
            last = int(tk.call(self.active_menu, 'index', 'last'))
            index = last - 1 if self.menu_stage == 'directory' else last
            top = int(tk.call(self.active_menu, 'yposition', index))
            bottom = (int(tk.call(self.active_menu, 'yposition', index + 1)) if index < last
                      else int(tk.call('winfo', 'height', self.active_menu)) - 2)
            x = int(tk.call('winfo', 'rootx', self.active_menu)) + 30
            y = int(tk.call('winfo', 'rooty', self.active_menu)) + (top + bottom) // 2
            self.mouse_click(x, y)
            self.window.after(200, self.inspect_menu_selection)
        except Exception as error:
            self.menu_failure(error)

    def inspect_menu_selection(self):
        tk = self.window.tk

        try:
            self.assertEqual(int(tk.call('winfo', 'ismapped', self.active_menu)), 0)

            if self.menu_stage == 'directory':
                directory = tk.getvar(tk.call(self.directory_button, 'cget', '-textvariable'))
                self.assertEqual(Path(str(directory)), self.root)
                self.menu_stage = 'types'
                self.open_dialog_menu()
            else:
                self.assertIn('All files', str(tk.call(self.type_button, 'cget', '-text')))
                entries = [path for path in self.window.file_dialog_layout.descendants(self.dialog_path)
                           if tk.call('winfo', 'class', path) == 'TEntry']
                entry = entries[-1]
                tk.call(entry, 'delete', 0, 'end')
                tk.call(entry, 'insert', 0, 'Synthetic.log')
                buttons = [path for path in self.window.file_dialog_layout.descendants(self.dialog_path)
                           if tk.call('winfo', 'class', path) == 'TButton']
                accept = next(path for path in buttons if str(tk.call(path, 'cget', '-text')) == 'Open')
                tk.call(accept, 'invoke')
        except Exception as error:
            self.menu_failure(error)

    def menu_failure(self, error):
        self.dialog_errors.append(str(error))

        if self.dialog_path:
            self.window.tk.eval(str(self.window.tk.call('wm', 'protocol', self.dialog_path, 'WM_DELETE_WINDOW')))

    def inspect_dialog(self):
        window = self.window
        tk = window.tk
        self.dialog_attempts += 1
        dialogs = [path for path in window.file_dialog_layout.descendants(str(window))
                   if tk.call('winfo', 'class', path) == 'TkFDialog']
        dialog = next((path for path in dialogs if int(tk.call('winfo', 'ismapped', path))), None)

        if dialog is None:
            if self.dialog_attempts > 40:
                self.cancel_dialog()
                return

            window.after(50, self.inspect_dialog)
            return

        widgets = window.file_dialog_layout.descendants(dialog)
        entries = [path for path in widgets if tk.call('winfo', 'class', path) in ('Entry', 'TEntry')]
        buttons = [path for path in widgets if tk.call('winfo', 'class', path) in ('Button', 'TButton')]
        cancel = next(path for path in buttons if str(tk.call(path, 'cget', '-text')) == 'Cancel')

        try:
            width, height = int(tk.call('winfo', 'width', dialog)), int(tk.call('winfo', 'height', dialog))
            maximum_width, maximum_height = DesktopStyle.available_size(window)
            self.assertLessEqual(width, maximum_width)
            self.assertLessEqual(height, maximum_height)
            canvases = [path for path in widgets if tk.call('winfo', 'class', path) == 'Canvas']
            self.assertTrue(canvases)
            line = font.nametofont('TkTextFont', root = window).metrics('linespace')
            self.assertGreaterEqual(int(tk.call('winfo', 'height', canvases[0])), line * 8)
            right = int(tk.call('winfo', 'rootx', dialog)) + width
            bottom = int(tk.call('winfo', 'rooty', dialog)) + height

            for path in (*entries, *buttons):
                if int(tk.call('winfo', 'ismapped', path)):
                    self.assertLessEqual(int(tk.call('winfo', 'rootx', path)) + int(tk.call('winfo', 'width', path)), right)
                    self.assertLessEqual(int(tk.call('winfo', 'rooty', path)) + int(tk.call('winfo', 'height', path)), bottom)

            entry = entries[-1]
            tk.call(entry, 'delete', 0, 'end')
            tk.call(entry, 'insert', 0, tk.call('list', *self.selected_files))
            accept = next(path for path in buttons if str(tk.call(path, 'cget', '-text')) == 'Open')
            tk.call(accept, 'invoke')
        except Exception as error:
            self.dialog_errors.append(str(error))
            tk.call(cancel, 'invoke')
