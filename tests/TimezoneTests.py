"""IANA catalogue: GMT labels, fractional offsets, and seasonal transitions."""

import unittest

from datetime import datetime, timezone

from poe_log_analyze.desktop.TimezoneCatalogue import TimezoneCatalogue


class TimezoneTests(unittest.TestCase):
    """The displayed offset does not replace the time zone identifier."""

    def test_offsets_sorting_and_regional_identifiers(self):
        choices = TimezoneCatalogue.timezone_options(datetime(2026, 1, 15, tzinfo = timezone.utc))
        by_key = {item.key: item for item in choices}

        self.assertEqual(by_key["Asia/Almaty"].label, "GMT+05:00 — Asia/Almaty")
        self.assertEqual(by_key["Asia/Kathmandu"].offset_minutes, 345)
        self.assertEqual(by_key["America/New_York"].offset_minutes, -300)
        self.assertEqual(by_key["UTC"].label, "GMT+00:00 — UTC")
        self.assertEqual(list(choices), sorted(choices, key = lambda item: (item.offset_minutes, item.key)))
        self.assertEqual(len(by_key), len(choices))

    def test_seasonal_offset_changes_but_identifier_does_not(self):
        winter = {item.key: item for item in TimezoneCatalogue.timezone_options(datetime(2026, 1, 15, tzinfo = timezone.utc))}
        summer = {item.key: item for item in TimezoneCatalogue.timezone_options(datetime(2026, 7, 15, tzinfo = timezone.utc))}

        self.assertEqual(winter["Europe/Berlin"].offset_minutes, 60)
        self.assertEqual(summer["Europe/Berlin"].offset_minutes, 120)

        with self.assertRaises(ValueError):
            TimezoneCatalogue.timezone_options(datetime(2026, 1, 15))
