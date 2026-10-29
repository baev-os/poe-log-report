"""Progress describes actual work without changing cancellation or calculations."""

import unittest

from unittest.mock import patch

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.execution.ProgressUpdate import ProgressUpdate


class ExecutionProgressTests(unittest.TestCase):
    """Check frequency, units, activity signals, and observer errors."""

    CLOCK = 'poe_log_analyze.core.execution.ExecutionContext.monotonic'

    def test_new_operation_is_reported_even_inside_throttle_interval(self):
        updates = []
        control = ExecutionContext(progress = updates.append)

        with patch(self.CLOCK, return_value = 10):
            control.report('Чтение', 1, 10, unit = 'bytes')

            control.report('HTML', 0, unit = 'pages')

        self.assertEqual(updates, [ProgressUpdate('Чтение', 1, 10, 0, 'bytes'),
                                   ProgressUpdate('HTML', 0, 0, 0, 'pages')])

    def test_frequent_updates_are_coalesced_and_check_reports_latest_real_count(self):
        updates = []
        control = ExecutionContext(progress = updates.append)

        with patch(self.CLOCK) as clock:
            clock.return_value = 10

            control.report('Чтение', 1, 100, unit = 'bytes')
            clock.return_value = 10.01

            control.report('Чтение', 17, 100, unit = 'bytes')
            clock.return_value = 10.02

            control.report('Чтение', 28, 100, unit = 'bytes')

            self.assertEqual(len(updates), 1)

            clock.return_value = 11
            control.check()
            clock.return_value = 11.5
            control.check()

        self.assertEqual([update.processed for update in updates], [1, 28])
        self.assertEqual(updates[-1].total, 100)

    def test_heartbeat_does_not_invent_a_counter_or_start_without_an_operation(self):
        updates = []
        control = ExecutionContext(progress = updates.append)

        with patch(self.CLOCK) as clock:
            clock.return_value = 10
            control.check()

            self.assertEqual(updates, [])

            control.report('Расчёт')
            clock.return_value = 11
            control.check()
            clock.return_value = 12
            control.check()

        self.assertEqual(updates, [ProgressUpdate('Расчёт')] * 3)

    def test_forced_final_count_is_not_lost(self):
        updates = []
        control = ExecutionContext(progress = updates.append)

        with patch(self.CLOCK, return_value = 10):
            control.report('Страницы', 0, 5, unit = 'pages')

            control.report('Страницы', 5, 5, force = True, unit = 'pages')

        self.assertEqual([value.processed for value in updates], [0, 5])

    def test_cancellation_precedes_heartbeat_and_notifies_process(self):
        updates, cancelled = [], []
        control = ExecutionContext(progress = updates.append, on_cancel = lambda: cancelled.append(True))

        with patch(self.CLOCK) as clock:
            clock.return_value = 10

            control.report('PDF')
            control.cancelled = lambda: True
            clock.return_value = 11

            with self.assertRaises(GenerationCancelled):
                control.check()

        self.assertEqual(updates, [ProgressUpdate('PDF')])
        self.assertEqual(cancelled, [True])

    def test_observer_failure_does_not_break_work_or_repeat_on_every_check(self):
        control = ExecutionContext(progress = lambda _: 1 / 0)

        with patch(self.CLOCK, return_value = 10), self.assertLogs(level = 'ERROR') as log:
            control.report('HTML')
            control.check()
            control.check()

        self.assertEqual(len(log.output), 1)

    def test_observer_can_check_context_without_recursive_heartbeat(self):
        from functools import partial

        updates = []
        control = ExecutionContext()
        control.progress = partial(self.check_inside_observer, control, updates)

        with patch(self.CLOCK) as clock:
            clock.return_value = 10

            control.report('HTML')
            clock.return_value = 11
            control.check()

        self.assertEqual(updates, [ProgressUpdate('HTML')] * 2)

    @staticmethod
    def check_inside_observer(control, updates, value):
        updates.append(value)

        if len(updates) < 4:
            control.check()

    def test_old_positional_progress_contract_is_preserved(self):
        self.assertEqual(ProgressUpdate('Чтение', 10, 20, 3).unit, '')
