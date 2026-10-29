"""Unified history: calendar boundaries, classification, conversations, and safe local HTML."""
import json
import unittest

from pathlib import Path
from tempfile import TemporaryDirectory

from poe_log_analyze.stages.composition.MapCalendarBuilder import MapCalendarBuilder
from poe_log_analyze.stages.composition.DailyPlaytimeBuilder import DailyPlaytimeBuilder

from poe_log_analyze.runtime.GameAreaCatalogue import GameAreaCatalogue

from ReportFixture import ReportFixture

from poe_log_analyze.stages.verification.LocalHTML import LocalHTML
from poe_log_analyze.stages.composition.specification.SpecificationBuilder import SpecificationBuilder
from poe_log_analyze.stages.parsing.CollectionAnalysisService import CollectionAnalysisService

from CollectionFixture import CollectionFixture


class HistoryViewsTests(unittest.TestCase):
    """Requirement checks using synthetic data without user conversations."""

    def test_midnight_dst_and_empty_days_preserve_total(self):
        model = DailyPlaytimeBuilder.build({'intervals': [
            {'started_at': '2026-03-28T23:30:00+01:00', 'ended_at': '2026-03-30T00:30:00+02:00'},
            {'started_at': '2026-04-01T10:00:00+02:00', 'ended_at': '2026-04-01T11:00:00+02:00'}]}, 'Europe/Berlin')
        days = {d['date']: d['seconds'] for d in model['days']}

        self.assertEqual(days, {'2026-03-28': 1800, '2026-03-29': 23*3600, '2026-03-30': 1800,
                               '2026-03-31': 0, '2026-04-01': 3600})
        self.assertEqual(model['seconds'], 25*3600)
        self.assertEqual(DailyPlaytimeBuilder.build({'intervals': []}, 'Asia/Almaty')['days'], [])

    def test_calendar_has_blank_days_and_leap_day(self):
        model = MapCalendarBuilder.build({'by_date': {'2024-02-29': {'count': 2}, '2024-04-01': {'count': 1}}})

        self.assertEqual([m['id'] for m in model['months']], ['2024-02','2024-03','2024-04'])

        feb = model['months'][0]

        self.assertEqual(feb['weeks'][0][0]['date'], '2024-01-29')
        self.assertFalse(feb['weeks'][0][0]['current'])
        self.assertEqual(next(d for w in feb['weeks'] for d in w if d['date']=='2024-02-29')['maps']['count'], 2)
        self.assertTrue(all(d['maps'] is None for w in model['months'][1]['weeks'] for d in w if d['current']))

    def test_game_catalogue_distinguishes_map_from_memory_area(self):
        self.assertEqual(GameAreaCatalogue.lookup('MapWorldsDunes')['kind'], 'Карта')
        self.assertEqual(GameAreaCatalogue.lookup('MapWorldsMemoryVault1')['kind'], 'Область')
        self.assertEqual(GameAreaCatalogue.lookup('MapAtlasEncounter_Perandus')['kind'], 'Область')
        self.assertEqual(GameAreaCatalogue.lookup('HarvestLeagueBoss')['kind'], 'Область')
        self.assertEqual(GameAreaCatalogue.lookup('Synthesis_MapBoss')['kind'], 'Карта')
        self.assertEqual(GameAreaCatalogue.lookup('Synthesis_MapGuardian1')['kind'], 'Карта')
        self.assertNotEqual(GameAreaCatalogue.lookup('MapWorldsUnknownFuture')['kind'], 'Карта')

        for key in ('MapWorldsDunes','Synthesis_MapGuardian1'):
            self.assertTrue(GameAreaCatalogue.lookup(key)['icon'])

    def test_calendar_includes_playtime_months_without_maps(self):
        statistics = {'by_date': {'2026-09-02': {'count': 1}}}
        playtime = {'days': [{'date': '2026-08-31'}, {'date': '2026-10-01'}]}

        for maps in (statistics, {'by_date': {}}):
            model = MapCalendarBuilder.build(maps, playtime)

            self.assertEqual([month['id'] for month in model['months']], ['2026-08', '2026-09', '2026-10'])

            days = {day['date']: day for month in model['months'] for week in month['weeks']
                    for day in week if day['current']}

            self.assertIsNone(days['2026-08-31']['maps'])
            self.assertIsNone(days['2026-10-01']['maps'])

        self.assertEqual(MapCalendarBuilder.build({'by_date': {}}, {'days': []})['months'], [])

    def test_playtime_links_to_unique_calendar_days_in_both_languages(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = root / 'synthetic.txt'
            lines = []

            for date, area, name in (('2026-08-31', 'HideoutOssuary', 'Hideout'),
                                     ('2026-09-02', 'MapWorldsDunes', 'Dunes'),
                                     ('2026-10-01', 'HideoutOssuary', 'Hideout')):
                for second, message in ((0, f'Generating level 83 area "{area}" with seed 1'),
                                        (1, f': You have entered {name}.'), (11, ': Trade accepted.')):
                    lines.append(CollectionFixture.line(second, message).replace('2026/09/01', date.replace('-', '/')))

            log.write_text(''.join(lines))

            CollectionAnalysisService.analyze_collection([log], root / 'analysis')

            for language in ('ru', 'en'):
                report = root / language

                ReportFixture.export_report(root / 'analysis', report, report_language = language)
                public = report / 'public'
                playtime = (public / 'playtime/index.html').read_text()
                calendar = (public / 'maps/index.html').read_text()
                model = json.loads((report / 'project/data/daily_playtime.json').read_text())

                self.assertEqual(model['seconds'], 30)
                self.assertIn('role="group"', playtime)

                for day in model['days']:
                    link = f'../maps/index.html#day-{day["date"]}'

                    # Two chart modes and one daily-table row.
                    self.assertEqual(playtime.count(f'href="{link}"'), 3)
                    self.assertEqual(calendar.count(f'id="day-{day["date"]}"'), 1)

                self.assertTrue((public / 'maps/2026-08-31/index.html').exists())
                self.assertTrue((public / 'maps/2026-09-02/index.html').exists())

    def test_compact_descriptions_cover_every_code(self):
        document = (Path(__file__).parents[1]/'docs/rules.md').read_text()

        spec = SpecificationBuilder.build_specification(document)
        codes = [*spec.framing, *spec.continuations, *(r for f in spec.families for r in f.rules)]

        self.assertTrue(all(r.description for r in codes))

        with self.assertRaisesRegex(ValueError, 'brief description'):
            SpecificationBuilder.build_specification(document.replace('| Area tile checksum |', '| |'))

    def test_one_history_chat_issues_calendar_icons_and_chart(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = root/'one.txt'
            messages = [(0, 'Generating level 83 area "MapWorldsDunes" with seed 123'),
                        (1, ': You have entered Dunes.'),
                        (2, '@From TestPlayer: <img src=x onerror=alert(1)>'),
                        (3, '@To TestPlayer: reply'),
                        (4, '[JOB] Irrecoverable Exception Callback: SET'),
                        (5, 'Generating level 83 area "MapWorldsMemoryVault1" with seed 124'),
                        (6, ": You have entered Machinist's Vault."),
                        (7, 'Unhandled exception: synthetic fault')]
            log.write_text(''.join(CollectionFixture.line(t,text) for t,text in messages))
            result, report = root/'analysis', root/'report'

            CollectionAnalysisService.analyze_collection([log,log], result)

            ReportFixture.export_report(result, report)
            data = report/'project/data'
            coverage = json.loads((data/'analysis.json').read_text())

            self.assertEqual(coverage['total_lines'], 8)
            self.assertEqual(coverage['unknown_lines'], 1)

            chats = json.loads((data/'conversations.json').read_text())

            self.assertEqual(chats['count'], 2)
            self.assertEqual(len(chats['groups']), 1)
            self.assertEqual([m['direction'] for m in chats['groups'][0]['messages']], ['←', 'Вы →'])

            faults = json.loads((data/'issues.json').read_text())

            self.assertEqual(faults['count'], 1)
            self.assertEqual(faults['groups'][0]['category'], 'Признаки аварийного завершения')
            self.assertEqual(json.loads((data/'map_statistics.json').read_text())['count'], 1)

            areas = json.loads((data/'areas.json').read_text())

            self.assertEqual(areas['run_count'], 1)
            self.assertEqual(areas['by_date']['2026-09-01']['runs'][0]['name'], "Machinist's Vault")
            self.assertEqual(json.loads((data/'daily_playtime.json').read_text())['seconds'], 6)

            public = report/'public'
            chat_html = (public/'conversations/index.html').read_text()

            self.assertIn('&lt;img src=x onerror=alert(1)&gt;', chat_html)
            self.assertNotIn('<img src=x', chat_html)
            self.assertNotIn('sources/', chat_html)
            self.assertFalse((public/'sources').exists())

            day = (public/'maps/2026-09-01/index.html').read_text()

            self.assertIn('images/maps/', day)
            self.assertIn("Machinist", day)
            self.assertNotIn('<th scope="col">Источник</th>', day)
            self.assertIn('calendar-active', (public/'maps/index.html').read_text())

            home = (public/'index.html').read_text()

            self.assertIn('class="playtime-chart"', home)

            routes = ['playtime', 'maps', 'characters', 'activities', 'statistics', 'areas', 'flow', 'events', 'conversations']
            positions = [home.index(f'href="./{route}/index.html"') for route in routes]

            self.assertEqual(positions, sorted(positions))
            self.assertIn('>Календарь</a>', home)
            self.assertIn('history-rows', (public/'events/index.html').read_text())
            self.assertTrue((public/'vendor/bootstrap.min.css').is_file())

            spec = (public/'technical/specification/index.html').read_text()

            self.assertLess(spec.index('id="compact"'), spec.index('id="format"'))
            self.assertNotIn('&lt;img src=x', spec)

    def test_only_bundled_scripts_are_permitted(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'index.html').touch()
            (root/'ReportInteractions.js').touch()
            LocalHTML(root).feed('<script src="ReportInteractions.js" defer></script>')

            for html in ('<script>alert(1)</script>', '<script src="https://example.org/x.js"></script>',
                         '<script src="ReportInteractions.js">alert(1)</script>', '<img src="x" onerror="alert(1)">'):
                with self.subTest(html = html), self.assertRaises(ValueError):
                    LocalHTML(root).feed(html)
