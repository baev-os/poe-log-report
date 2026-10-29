"""Status, live elapsed time, and full operation journal on the Tk main thread."""

import tkinter as tk

from time import monotonic

from tkinter import ttk

from poe_log_analyze.core.execution.ProgressUpdate import ProgressUpdate


class ProgressPanel(ttk.Frame):
    """Observe execution without substituting timer ticks for real progress."""

    def __init__(self, parent):
        super().__init__(parent)

        self.started_at = monotonic()
        self.stage_started = self.started_at
        self.last_signal = self.started_at
        self.running = False
        self.clock_id = None
        self.follow_id = None
        self.current_stage = None
        self.completed = ()
        self.activity = ''
        self.last_entry = ''

        self.stage = tk.StringVar(self, 'Ready')
        self.message = tk.StringVar(self, 'Add logs and click Analyze.')
        self.timing = tk.StringVar(self, '')

        self.bar = ttk.Progressbar(self, maximum = 100)
        self.bar.grid(row = 0, column = 0, columnspan = 2, sticky = 'ew', pady = (0, 7))

        self.heading = ttk.Label(self, textvariable = self.stage, style = 'ProgressHeading.TLabel')
        self.heading.grid(row = 1, column = 0, columnspan = 2, sticky = 'ew')
        self.detail = ttk.Label(self, textvariable = self.message, wraplength = 900)
        self.detail.grid(row = 2, column = 0, columnspan = 2, sticky = 'ew', pady = (4, 0))
        self.elapsed = ttk.Label(self, textvariable = self.timing, wraplength = 900)
        self.elapsed.grid(row = 3, column = 0, columnspan = 2, sticky = 'ew', pady = (4, 8))

        self.journal_title = ttk.Label(self, text = 'Execution journal')
        self.journal_title.grid(row = 4, column = 0, sticky = 'w')
        self.copy = ttk.Button(self, text = 'Copy journal', command = self.copy_journal)
        self.copy.grid(row = 4, column = 1, sticky = 'e', pady = (0, 5))

        journal = ttk.Frame(self)
        journal.grid(row = 5, column = 0, columnspan = 2, sticky = 'nsew')
        self.log = tk.Text(journal, width = 36, height = 7, wrap = 'word', font = 'TkTextFont', state = 'disabled')
        scrollbar = ttk.Scrollbar(journal, orient = tk.VERTICAL, command = self.log.yview)
        self.log.configure(yscrollcommand = scrollbar.set)
        self.log.grid(row = 0, column = 0, sticky = 'nsew')
        scrollbar.grid(row = 0, column = 1, sticky = 'ns')
        journal.columnconfigure(0, weight = 1)
        journal.rowconfigure(0, weight = 1)

        self.columnconfigure(0, weight = 1)
        self.rowconfigure(5, weight = 1)
        self.bind('<Configure>', self.resize)

    def resize(self, event) -> None:
        self.wrap_text(event.width)

    def wrap_text(self, width: int) -> None:
        for label in (self.detail, self.heading, self.elapsed):
            label.configure(wraplength = max(1, width - 10))

    @staticmethod
    def duration(seconds: float) -> str:
        value = int(max(0, seconds))
        return f'{value // 3600:02}:{value % 3600 // 60:02}:{value % 60:02}'

    def start(self) -> None:
        self.stop_clock()
        self.started_at = self.stage_started = self.last_signal = monotonic()
        self.running = True
        self.current_stage = None
        self.completed = ()
        self.activity = self.last_entry = ''
        self.log.configure(state = 'normal')
        self.log.delete('1.0', tk.END)
        self.log.configure(state = 'disabled')
        self.stage.set('Starting analysis')
        self.notice('New analysis started.')
        self.bar.configure(mode = 'indeterminate')
        self.bar.start(50)
        self.tick()

    def tick(self) -> None:
        now = monotonic()
        silence = int(max(0, now - self.last_signal))
        self.timing.set('Elapsed: ' + self.duration(now - self.started_at)
                        + ' · Current stage: ' + self.duration(now - self.stage_started)
                        + f' · Worker signal: {silence} s ago')

        if self.running:
            self.clock_id = self.after(250, self.tick)

    def append(self, text: str, *, replace: bool = False) -> None:
        follow = not self.log.winfo_ismapped() or self.log.yview()[1] >= .99
        self.log.configure(state = 'normal')

        if replace and self.last_entry:
            self.log.delete('end-2l linestart', 'end-1l linestart')

        self.log.insert(tk.END, '[' + self.duration(monotonic() - self.started_at) + '] ' + text + '\n')
        self.log.configure(state = 'disabled')
        self.last_entry = text

        if follow and self.follow_id is None:
            self.follow_id = self.after_idle(self.follow_end)

    def follow_end(self) -> None:
        self.follow_id = None
        self.log.see(tk.END)

    def notice(self, text: str) -> None:
        self.message.set(text)
        self.activity = ''

        if text != self.last_entry:
            self.append(text)

    def update_state(self, snapshot) -> None:
        self.last_signal = monotonic()

        for completed in snapshot.completed[len(self.completed):]:
            self.activity = ''
            self.append('Stage completed: ' + completed.value)

        self.completed = snapshot.completed

        if snapshot.stage is not None and snapshot.stage != self.current_stage:
            self.current_stage = snapshot.stage
            self.stage_started = monotonic()
            self.activity = ''
            label = f'Stage {len(snapshot.completed) + 1} of {snapshot.total}: {snapshot.stage.value}'
            self.stage.set(label)
            self.append(label)

        if snapshot.status.value == 'publishing':
            self.stage.set('Saving results')
            self.stage_started = monotonic()
            self.notice('Saving the completed report and removing temporary results…')
        elif snapshot.status.value == 'cancelling':
            self.stage.set('Cancelling operation')
            self.notice('Cancelling… waiting for work to stop and temporary results to be removed.')

    def update_progress(self, value: ProgressUpdate) -> None:
        self.last_signal = monotonic()
        counters = []

        if value.unit == 'bytes' and value.total:
            counters.append(f'{value.processed / 1024 ** 2:.1f} of {value.total / 1024 ** 2:.1f} MiB')
        elif value.unit in ('pages', 'files', 'resources'):
            label = {'pages': 'Pages', 'files': 'Files', 'resources': 'Resources'}[value.unit]
            counters.append(label + f': {value.processed:,}' + (f' of {value.total:,}' if value.total else ''))
        elif value.total:
            counters.append(f'{value.processed:,} of {value.total:,} {value.unit}'.strip())
        elif value.unit:
            counters.append(f'{value.processed:,} {value.unit}')

        if value.lines:
            counters.append(f'Lines: {value.lines:,}')

        text = value.stage + (' · ' + ' · '.join(counters) if counters else '')
        self.message.set(text)

        if value.stage != (self.current_stage.value if self.current_stage is not None else '') or counters:
            self.append(text, replace = self.activity == value.stage)

        self.activity = value.stage

        if value.total:
            self.bar.stop()
            self.bar.configure(mode = 'determinate', value = min(100, max(0, 100 * value.processed / value.total)))
        elif str(self.bar['mode']) != 'indeterminate':
            self.bar.configure(mode = 'indeterminate')
            self.bar.start(50)

    def stop_clock(self) -> None:
        if self.follow_id is not None:
            self.after_cancel(self.follow_id)
            self.follow_id = None

        if self.clock_id is not None:
            self.after_cancel(self.clock_id)
            self.clock_id = None

    def finish(self, message: str, success: bool) -> None:
        self.running = False
        self.stop_clock()
        self.bar.stop()
        self.bar.configure(mode = 'determinate', value = 100 if success else 0)
        self.stage.set('Done' if success else 'Operation complete')
        self.notice(message)
        self.timing.set('Total time: ' + self.duration(monotonic() - self.started_at))

    def copy_journal(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.log.get('1.0', 'end-1c'))
