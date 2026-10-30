"""Message totals, remainder expansion, and technical-map calendar."""

import json
import unittest

from copy import deepcopy

from pathlib import Path
from tempfile import TemporaryDirectory

from poe_log_analyze.stages.composition.events.LogObservationsBuilder import LogObservationsBuilder
from poe_log_analyze.stages.composition.MapCalendarBuilder import MapCalendarBuilder
from poe_log_analyze.stages.parsing.CollectionAnalysisService import CollectionAnalysisService

from CollectionFixture import CollectionFixture
from ReportFixture import ReportFixture


class LogObservationsTests(unittest.TestCase):
    def test_counts_precise_decimals_repetitions_and_continuations(self):
        builder = LogObservationsBuilder()

        self.assertEqual(builder.result()['loading_duration'], '00:00:00')

        rows = [dict(line_number = i, record_id = i, status = 'recognized', type = kind, fields = fields)
                for i, (kind, fields) in enumerate([
                    ('loading.duration', {'seconds': '0.1'}), ('loading.duration', {'seconds': '0.2'}),
                    ('loading.duration', {'seconds': '9e4'}), ('loading.duration', {'seconds': '0'}),
                    ('screen.items_identified', {'count': '3'}), ('screen.items_identified', {'count': '3'}),
                    ('screen.items_identified', {'count': '0'}),
                ], 1)]
        rows.append(dict(line_number = 8, record_id = 7, status = 'recognized', type = 'screen.items_identified', fields = {'count': '80'}))
        original = deepcopy(rows)

        for row in rows:
            builder.add(row)

        self.assertEqual(rows, original)

        result = builder.result()

        self.assertEqual(result['loading_duration'], '25:00:00.3')
        self.assertEqual(result['loading_seconds'], '90000.3')
        self.assertEqual((result['loading_count'], result['items_identified'], result['identification_count']), (4, 6, 3))

    def test_calendar_preserves_arena_only_and_undated_days(self):
        maps = {'days': [{'date': '2026-01-31', 'count': 1, 'seconds': 60},
                         {'date': '2026-03-01', 'count': 2, 'seconds': 90},
                         {'date': 'undated', 'count': 1, 'seconds': 0}]}

        calendar = MapCalendarBuilder.build_details(maps)

        self.assertEqual([month['id'] for month in calendar['months']], ['2026-01', '2026-02', '2026-03'])

        active = [day['date'] for month in calendar['months'] for week in month['weeks'] for day in week
                  if day['current'] and day['maps']]

        self.assertEqual(active, ['2026-01-31', '2026-03-01'])
        self.assertEqual(calendar['undated']['count'], 1)
        self.assertEqual(MapCalendarBuilder.build_details({'days': []})['months'], [])

    def test_export_copied_history_unknown_text_errors_charts_and_calendar(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, copy = root / 'one.txt', root / 'copy.txt'
            unknown = 'Synthetic unsupported <script>alert(1)</script> ' + 'x' * 600
            messages = [
                ': SyntheticHero (Duelist) is now level 89',
                ': SyntheticHero (Duelist) is now level 90',
                ': SyntheticHero (Duelist) is now level 91',
                '[LOADING SCREEN] (Synthetic Area) Duration = 1.125 seconds',
                '[LOADING SCREEN] (Synthetic Area) Duration = 2.5e0 seconds',
                ': 3 Items identified', ': 1 Item identified', ': 3 Items identified', unknown, unknown,
                'Generating level 80 area "MapWorldsDunes" with seed 1', ': You have entered Dunes.',
                'Generating level 1 area "Hideout" with seed 2', ': You have entered Hideout.',
            ]
            source.write_bytes(''.join(CollectionFixture.line(i, text) for i, text in enumerate(messages)).encode()
                               + b'\xff\n' + b'Synthetic unframed message\n')
            copy.write_bytes(source.read_bytes())

            CollectionAnalysisService.analyze_collection([source, copy], root / 'analysis')

            for language in ('ru', 'en'):
                output = root / language

                entry = ReportFixture.export_report(root / 'analysis', output, report_language = language)
                model = json.loads((output / 'project/data/log_observations.json').read_text())

                self.assertEqual(model['loading_duration'], '00:00:03.625')
                self.assertEqual((model['loading_count'], model['items_identified']), (2, 7))
                self.assertEqual(sum(category['count'] for category in model['diagnostics']), 4)

                messages = [message for category in model['diagnostics'] for message in category['messages']]

                self.assertEqual(next(message for message in messages if message['text'] == unknown)['count'], 2)
                self.assertEqual(sum(message['text'] is None for message in messages), 1)

                coverage = (entry.parent / 'technical/index.html').read_text()

                self.assertIn('<details class="diagnostic-category">', coverage)
                self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt; ' + 'x' * 600, coverage)
                self.assertNotIn('<script>alert', coverage)
                self.assertIn('data-items-identified>7<', coverage)
                self.assertIn('data-loading-duration>00:00:03.625<', coverage)

                statistics = (entry.parent / 'statistics/index.html').read_text()

                self.assertIn('data-items-identified>7<', statistics)

                characters = (entry.parent / 'characters/index.html').read_text()

                self.assertEqual(characters.count('data-character-chart '), 2)
                self.assertEqual(characters.count('data-chart-line '), 2)
                self.assertIn('ChartTooltip.js" defer', characters)

                for second in range(3):
                    self.assertIn(f'data-timestamp="2026-09-01T00:00:0{second}+01:00"', characters)

                maps = (entry.parent / 'technical/maps/index.html').read_text()

                self.assertIn('class="calendar"', maps)
                self.assertIn('./2026-09-01/index.html', maps)
                self.assertIn('id="day-2026-09-01"', maps)

                manifest = json.loads((output / 'report-manifest.json').read_text())

                self.assertIn('log_observations', manifest['views_sha256'])
                self.assertIn('map_details_calendar', manifest['views_sha256'])
