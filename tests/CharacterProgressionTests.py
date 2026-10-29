"""Level history without guessing missing levels, ownership, or repeated names."""

import json
import unittest

from copy import deepcopy

from pathlib import Path
from tempfile import TemporaryDirectory

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled

from poe_log_analyze.stages.composition.CharacterProgressionBuilder import CharacterProgressionBuilder
from poe_log_analyze.stages.parsing.CollectionAnalysisService import CollectionAnalysisService

from CollectionFixture import CollectionFixture
from ReportFixture import ReportFixture


class CharacterProgressionTests(unittest.TestCase):
    @staticmethod
    def event(line, stamp, name, level, character_class = 'Duelist', kind = 'screen.level_up'):
        return {'line_number': line, 'timestamp': stamp, 'type': kind,
                'message': {'fields': {'character': name, 'class': character_class, 'level': str(level)}}}

    @staticmethod
    def timeline(events):
        return {'timezone': 'Asia/Almaty', 'days': [{'date': '2026-09-01'}],
                'by_date': {'2026-09-01': {'events': events}}}

    def test_chronology_uses_instants_preserves_ties_gaps_and_class_changes(self):
        model = self.timeline([
            self.event(3, '2026-09-01T12:00:00+05:00', 'Hero', 13),
            self.event(2, '2026-09-01T12:00:00+05:00', 'Hero', 13),
            self.event(1, '2026-09-01T12:30:00+06:00', 'Hero', 10),
            self.event(4, '2026-09-02T12:00:00+05:00', 'Hero', 20, 'Slayer'),
            self.event(5, '2026-09-03T12:00:00+05:00', 'Hero', 2),
            self.event(6, '2026-09-01T12:00:00+05:00', 'Other', 8),
            self.event(7, '2026-09-01T12:00:00+05:00', 'Ignored', 8, kind = 'screen.character_info'),
        ])
        original = deepcopy(model)

        result = CharacterProgressionBuilder.build(model, ExecutionContext())

        self.assertEqual(model, original)
        self.assertEqual((result['count'], result['event_count']), (2, 6))

        hero = result['characters'][0]

        self.assertEqual([event['line'] for event in hero['events']], [1, 2, 3, 4, 5])
        self.assertEqual([event['level'] for event in hero['events']], [10, 13, 13, 20, 2])
        self.assertEqual(hero['classes'], ['Duelist', 'Slayer'])
        self.assertEqual([e['delta_seconds'] for e in hero['events']], [None, 1800, None, 86400, None])
        self.assertEqual([e['delta_from_level'] for e in hero['events']], [None, 10, None, 13, None])
        self.assertEqual(hero['events'][3]['delta_duration'], '24:00:00')
        self.assertEqual((hero['first']['level'], hero['last']['level']), (10, 2))
        self.assertEqual(hero['charts'][0]['events'][0]['x'], 60)
        self.assertEqual(hero['charts'][0]['events'][-1]['x'], 940)
        self.assertEqual(hero['charts'][0]['events'][1]['x'], hero['charts'][0]['events'][2]['x'])

    def test_empty_single_point_same_time_and_cancellation(self):
        empty = CharacterProgressionBuilder.build(self.timeline([]), ExecutionContext())

        self.assertEqual(empty['characters'], [])

        single = self.timeline([self.event(1, '2026-09-01T12:00:00+05:00', 'Solo', 7)])
        point = CharacterProgressionBuilder.build(single, ExecutionContext())['characters'][0]

        self.assertEqual((point['charts'][0]['events'][0]['x'], point['charts'][0]['events'][0]['y']), (500, 120))

        single['by_date']['2026-09-01']['events'].append(self.event(2, '2026-09-01T12:00:00+05:00', 'Solo', 8))
        points = CharacterProgressionBuilder.build(single, ExecutionContext())['characters'][0]['charts'][0]['events']

        self.assertEqual([point['x'] for point in points], [500, 500])

        with self.assertRaises(GenerationCancelled):
            CharacterProgressionBuilder.build(single, ExecutionContext(cancelled = lambda: True))

    def test_export_languages_escaping_links_and_copied_history(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, copy = root / 'one.txt', root / 'copy.txt'
            source.write_text(''.join(CollectionFixture.line(second, message) for second, message in [
                (0, ': SyntheticHero (Duelist) is now level 13'),
                (15, ': <script> (Witch) is now level 5'),
                (30, ': SyntheticHero (Slayer) is now level 15'),
                (30, ': SyntheticHero (Slayer) is now level 15'),
            ]))
            copy.write_bytes(source.read_bytes())

            CollectionAnalysisService.analyze_collection([source, copy], root / 'analysis')

            for language, title in (('ru', 'Персонажи'), ('en', 'Characters')):
                output = root / language

                entry = ReportFixture.export_report(root / 'analysis', output, report_language = language)
                model = json.loads((output / 'project/data/characters.json').read_text())

                self.assertEqual((model['count'], model['event_count']), (2, 4))

                hero = next(item for item in model['characters'] if item['name'] == 'SyntheticHero')

                self.assertEqual([event['level'] for event in hero['events']], [13, 15, 15])

                html = (entry.parent / 'characters/index.html').read_text()

                self.assertIn(title, html)
                self.assertIn('&lt;script&gt;', html)
                self.assertNotIn('<script>', html)
                self.assertIn('technical/timeline/2026-09-01/index.html#line-1', html)
                self.assertIn('id="character-1"', html)
                self.assertIn('characters/index.html', entry.read_text())

                manifest = json.loads((output / 'report-manifest.json').read_text())

                self.assertIn('characters', manifest['views_sha256'])
                self.assertIn('characters/index.html', manifest['public_sha256'])

    def test_split_above_90_keeps_boundary_without_inventing_levels(self):
        for levels in ([89, 90], [89, 90, 91, 100], [89, 91], [95], [91, 2]):
            timeline = self.timeline([self.event(index, f'2026-09-{index:02}T12:00:00+05:00', 'Hero', level)
                                      for index, level in enumerate(levels, 1)])
            result = CharacterProgressionBuilder.build(timeline, ExecutionContext())['characters'][0]

            self.assertEqual([event['level'] for event in result['events']], levels)

            charts = result['charts']

            self.assertEqual(len(charts), 2 if max(levels) > 90 else 1)

            if len(charts) == 2:
                self.assertEqual([e['level'] for e in charts[0]['events']], [level for level in levels if level <= 90])
                self.assertEqual([e['level'] for e in charts[1]['events']], [level for level in levels if level >= 90])
                self.assertEqual([tick['level'] for tick in charts[1]['ticks']], [90, 92, 94, 96, 98, 100])

                for chart in charts:
                    if chart['events']:
                        self.assertEqual(len(chart['segments']), len(chart['events']) - 1)

    def test_level_delta_repeats_reset_and_dst(self):
        events = [self.event(1, '2026-10-25T02:30:00+02:00', 'Hero', 89),
                  self.event(2, '2026-10-25T02:30:00+01:00', 'Hero', 90),
                  self.event(3, '2026-10-25T03:00:00+01:00', 'Hero', 90),
                  self.event(4, '2026-10-25T03:30:00+01:00', 'Hero', 92),
                  self.event(5, '2026-10-25T04:00:00+01:00', 'Hero', 1),
                  self.event(6, '2026-10-25T04:10:00+01:00', 'Hero', 2)]
        timeline = self.timeline(events)
        timeline['timezone'] = 'Europe/Berlin'
        hero = CharacterProgressionBuilder.build(timeline, ExecutionContext())['characters'][0]

        self.assertEqual([e['delta_seconds'] for e in hero['events']], [None, 3600, None, 3600, None, 600])

        chart = hero['charts'][1]

        self.assertEqual(chart['time_ticks'][0]['time'], '02:30:00')
        self.assertEqual(chart['time_ticks'][-1]['time'], '03:30:00')
        self.assertEqual(len(chart['time_ticks']), 6)
        self.assertEqual(chart['events'][-1]['delta_from_level'], 90)
