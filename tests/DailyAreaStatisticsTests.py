"""Daily area time: midnight, DST, unknown boundaries, and export."""

import json
import unittest

from copy import deepcopy
from datetime import datetime

from pathlib import Path
from tempfile import TemporaryDirectory

from ReportFixture import ReportFixture

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled

from poe_log_analyze.stages.composition.DailyAreaStatisticsBuilder import DailyAreaStatisticsBuilder
from poe_log_analyze.stages.parsing.CollectionAnalysisService import CollectionAnalysisService


class DailyAreaStatisticsTests(unittest.TestCase):
    """Daily totals preserve measured time; never invent dates for unknown entries."""

    @staticmethod
    def run_record(area, kind, start, end):
        bounded = start is not None and end is not None
        return {'area_id': area, 'name': area, 'kind_code': kind, 'icon': '',
                'visits': [{'entered_at': start, 'ended_at': end, 'bounded': bounded,
                            'seconds': (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
                            if bounded else None}]}

    def test_midnight_splits_time_but_keeps_each_visit_once_per_day(self):
        runs = [self.run_record('Dunes', 'map', '2026-09-01T23:59:50+05:00', '2026-09-02T00:00:10+05:00'),
                self.run_record('Hideout', 'hideout', '2026-09-02T00:00:12+05:00', '2026-09-02T00:00:42+05:00')]
        before = deepcopy(runs)
        days = DailyAreaStatisticsBuilder.build(runs, 'Asia/Almaty', {'2026-09-03'}, ExecutionContext())['by_date']

        self.assertEqual({date: day['zone_totals']['seconds'] for date, day in days.items()},
                         {'2026-09-01': 10, '2026-09-02': 40, '2026-09-03': 0})
        self.assertEqual(days['2026-09-01']['zone_totals']['visits'], 1)
        self.assertEqual(days['2026-09-02']['zone_totals']['visits'], 2)
        self.assertEqual(days['2026-09-03']['zones'], [])
        self.assertEqual(runs, before)

    def test_dst_uses_elapsed_utc_time_and_exact_midnight_has_no_extra_visit(self):
        for start, end, hours in (('2026-03-29T00:00:00+01:00', '2026-03-30T00:00:00+02:00', 23),
                                  ('2026-10-25T00:00:00+02:00', '2026-10-26T00:00:00+01:00', 25)):
            with self.subTest(start = start):
                runs = [self.run_record('Hideout', 'hideout', start, end)]
                days = DailyAreaStatisticsBuilder.build(runs, 'Europe/Berlin', set(), ExecutionContext())['by_date']

                self.assertEqual(list(days), [start[:10]])
                self.assertEqual(days[start[:10]]['zone_totals']['seconds'], hours * 3600)
                self.assertEqual(days[start[:10]]['zone_totals']['visits'], 1)

    def test_unknown_boundaries_zero_duration_and_local_date(self):
        runs = [self.run_record('Town', 'town', '2026-09-01T22:00:00+00:00', None),
                self.run_record('Unknown', 'area', None, '2026-09-03T10:00:00+05:00'),
                self.run_record('Zero', 'arena', '2026-09-02T00:00:00+05:00', '2026-09-02T00:00:00+05:00')]
        days = DailyAreaStatisticsBuilder.build(runs, 'Asia/Almaty', set(), ExecutionContext())['by_date']

        self.assertEqual(set(days), {'2026-09-02', 'undated'})
        self.assertEqual(days['undated']['zone_totals']['incomplete_visits'], 1)
        self.assertEqual(days['undated']['zone_totals']['duration'], '—')

        rows = {row['name']: row for row in days['2026-09-02']['zones']}

        self.assertEqual(rows['Town']['duration'], '—')
        self.assertEqual(rows['Zero']['duration'], '00:00:00')
        self.assertEqual(days['2026-09-02']['zone_totals']['visits'], 2)

        with self.assertRaises(GenerationCancelled):
            DailyAreaStatisticsBuilder.build(runs, 'Asia/Almaty', set(), ExecutionContext(cancelled = lambda: True))

    def test_grouping_retains_repeated_visits_and_separates_zone_ids(self):
        first = self.run_record('Dunes', 'map', '2026-09-01T10:00:00+05:00', '2026-09-01T10:00:10+05:00')
        second = self.run_record('Dunes', 'map', '2026-09-01T11:00:00+05:00', '2026-09-01T11:00:20+05:00')
        third = self.run_record('Other', 'map', '2026-09-01T12:00:00+05:00', '2026-09-01T12:00:30+05:00')
        third['name'] = 'Dunes'
        first['visits'] += second['visits']
        days = DailyAreaStatisticsBuilder.build([first, third], 'Asia/Almaty', set(), ExecutionContext())['by_date']
        rows = {row['area_id']: row for row in days['2026-09-01']['zones']}

        self.assertEqual(rows['Dunes']['visits'], 2)
        self.assertEqual(rows['Dunes']['seconds'], 30)
        self.assertEqual(rows['Other']['visits'], 1)

    def test_export_midnight_hideout_only_day_and_deduplicated_sources_in_both_languages(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'synthetic.txt'
            messages = [('2026/09/01 23:59:49', 'Generating level 83 area "MapWorldsDunes" with seed 1'),
                        ('2026/09/01 23:59:50', ': You have entered Dunes.'),
                        ('2026/09/02 00:00:10', 'Generating level 60 area "HideoutOssuary" with seed 2'),
                        ('2026/09/02 00:00:12', ': You have entered <Hideout>.'),
                        ('2026/09/02 00:00:42', 'Generating level 1 area "1_1_town" with seed 3'),
                        ('2026/09/02 00:00:43', ': You have entered Town.'),
                        ('2026/09/02 00:00:44', ': Trade accepted.')]
            source.write_text(''.join(f'{stamp} 1 abcd [INFO Client 1] {text}\n' for stamp, text in messages))
            copy = root / 'copy.txt'
            copy.write_bytes(source.read_bytes())

            CollectionAnalysisService.analyze_collection([source, copy], root / 'analysis')

            for language in ('ru', 'en'):
                report = root / language

                ReportFixture.export_report(root / 'analysis', report, report_language = language)
                data = report / 'project/data'
                days = json.loads((data / 'daily_areas.json').read_text())['by_date']
                all_time = json.loads((data / 'statistics_summary.json').read_text())

                self.assertEqual(sum(day['zone_totals']['seconds'] for day in days.values()), all_time['zone_totals']['seconds'])
                self.assertEqual(days['2026-09-01']['zone_totals']['seconds'], 10)
                self.assertEqual(days['2026-09-02']['zone_totals']['seconds'], 40)
                self.assertEqual(days['2026-09-02']['zone_totals']['visits'], 3)

                public = report / 'public'
                html = (public / 'maps/2026-09-02/index.html').read_text()

                self.assertIn('Dunes', html)
                self.assertIn('&lt;Hideout&gt;', html)
                self.assertIn('data-kind="town"', html)
                self.assertIn('00:00:40', html)
                self.assertNotIn('<table class="map-statistics">', html)
                self.assertIn('class="day-overview"', html)
                self.assertIn('maps/2026-09-02/index.html', (public / 'maps/index.html').read_text())
                self.assertIn('../2026-09-01/index.html', html)

                manifest = json.loads((report / 'report-manifest.json').read_text())

                self.assertIn('daily_areas', manifest['views_sha256'])
