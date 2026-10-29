"""Special areas: exact classification, durations, and a shared timeline."""

import json
import unittest

from copy import deepcopy

from pathlib import Path
from tempfile import TemporaryDirectory

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled

from poe_log_analyze.stages.composition.ActivityAreaGroups import ActivityAreaGroups
from poe_log_analyze.stages.composition.ActivityTimelineBuilder import ActivityTimelineBuilder
from poe_log_analyze.stages.parsing.CollectionAnalysisService import CollectionAnalysisService

from CollectionFixture import CollectionFixture
from ReportFixture import ReportFixture


class ActivityTimelineTests(unittest.TestCase):
    @staticmethod
    def run_record(area, start, end, seconds, line = 1):
        return {'area_id': area, 'name': 'Synthetic area', 'kind_code': 'area',
                'visits': [{'entry_line': line, 'entered_at': start, 'ended_at': end,
                            'bounded': seconds is not None, 'seconds': seconds}]}

    def test_area_ids_do_not_confuse_similar_names_and_other_mechanics(self):
        cases = {'Delve_Main': 'delve', 'Delve_Hub': 'delve', 'DelveBossLich': 'delve',
                 'SanctumLycia2': 'sanctum', 'SanctumFoyer_Start': 'sanctum',
                 'Labyrinth_Airlock': 'labyrinth', '1_Labyrinth_boss_1': 'labyrinth',
                 'EndGame_Labyrinth_boss_1': 'labyrinth',
                 'DeepwaterHub': 'deepwater', 'DeepwaterEncounterVoyage': 'deepwater',
                 '1_1_town': 'acts', '2_10_town': 'acts', '2_7_5_map': 'acts',
                 'Menagerie_Hub': 'menagerie', 'Menagerie_Mammals': 'menagerie',
                 'KalguuranSettlersLeague': 'kingsmarch', 'HeistHub': 'harbour', 'HeistHubEndless': 'harbour',
                 'HeistBunker1': 'heist', 'HeistCourts9_': 'heist', 'HeistDungeon8': 'heist',
                 'ExpeditionCemetery': 'expedition', 'ExpeditionVolcano': 'expedition',
                 'ExpeditionSubareaSpiderNest': 'expedition',
                 'BetrayalSafeHouseFortress': 'betrayal', 'BetrayalSafeHouseAssassins': 'betrayal',
                 'Incursion_Temple10': 'incursion', 'LegionLeague4': 'legion',
                 'ExpeditionArenaOlroth': 'bosses', 'HeistBoss_TheUnbreakable': 'bosses',
                 'BetrayalMastermindFight': 'bosses',
                 'ChayulaLeague': 'keepers', 'HideoutOssuary': 'hideout',
                 'MapWorldsDunes': 'maps', 'MapWorldsBoneCryptUnique': 'maps',
                 'MapWorldsElderArena': 'bosses', 'MapWorldsShapersRealm': 'bosses',
                 'MapAtlasShapersRealm': 'bosses', 'MavenBoss': 'bosses', 'MavenHub': 'bosses',
                 'AtlasExilesBoss1': 'bosses', 'BestiaryLeague_TigerBoss': 'bosses',
                 'SettlersBossPirateCove': 'bosses', 'Synthesis_MapBoss': 'bosses'}

        for area, expected in cases.items():
            with self.subTest(area = area):
                self.assertEqual(ActivityAreaGroups.classify(area), expected)

        for area in ('LakeDelve1', 'HeistCinematic', '2_11_town', 'ChayulaLeagueTower',
                     'BetrayalTest', 'BetrayalStoryVault', 'Incursion_Room1', 'HeistUnknown',
                     'ExpeditionUnknown', 'DeepwaterFilmingBecalmedWater', 'SanctumUnknown', ''):
            with self.subTest(area = area):
                self.assertIsNone(ActivityAreaGroups.classify(area))

    def test_measured_unknown_zero_and_cross_month_visits_preserve_input(self):
        runs = [self.run_record('Delve_Main', '2026-08-31T23:50:00+05:00', '2026-09-01T00:10:00+05:00', 1200),
                self.run_record('Delve_Hub', '2026-09-02T12:00:00+05:00', None, None, 2),
                self.run_record('SanctumNave', None, None, None, 3),
                self.run_record('HeistHub', '2026-09-01T12:00:00+05:00', '2026-09-01T12:00:00+05:00', 0, 4)]
        before = deepcopy(runs)

        result = ActivityTimelineBuilder.build(runs, 'Asia/Almaty', ExecutionContext())
        groups = {row['code']: row for row in result['groups']}

        self.assertEqual(len(groups), 17)
        self.assertEqual(groups['delve']['totals']['seconds'], 1200)
        self.assertEqual(groups['delve']['totals']['incomplete_visits'], 1)
        self.assertEqual(groups['delve']['children'][0]['visits'][0]['start'], groups['delve']['children'][0]['visits'][0]['end'])
        self.assertIsNone(groups['sanctum']['children'][0]['visits'][0]['start'])
        self.assertEqual(groups['harbour']['totals']['duration'], '00:00:00')
        self.assertEqual([period['id'] for period in result['periods']], ['all', '2026-08', '2026-09'])
        self.assertEqual(runs, before)

    def test_dst_offsets_and_empty_or_single_point_chart(self):
        run = self.run_record('Menagerie_Hub', '2026-10-25T02:30:00+02:00', '2026-10-25T02:30:00+01:00', 3600)

        model = ActivityTimelineBuilder.build([run], 'Europe/Berlin', ExecutionContext())
        visit = next(group for group in model['groups'] if group['code'] == 'menagerie')['children'][0]['visits'][0]

        self.assertEqual(visit['end'] - visit['start'], 3600)
        self.assertEqual(model['periods'][1]['end'] - model['periods'][1]['start'], 31 * 86400 + 3600)

        empty = ActivityTimelineBuilder.build([], 'Asia/Almaty', ExecutionContext())

        self.assertEqual(empty['periods'], [])

        point = self.run_record('HeistHub', '2026-09-01T00:00:00+05:00', None, None)

        model = ActivityTimelineBuilder.build([point], 'Asia/Almaty', ExecutionContext())

        self.assertGreater(model['periods'][0]['end'], model['periods'][0]['start'])

        with self.assertRaises(GenerationCancelled):
            ActivityTimelineBuilder.build([point], 'Asia/Almaty', ExecutionContext(cancelled = lambda: True))

    def test_export_all_lanes_languages_and_copied_history(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, copy = root / 'one.txt', root / 'copy.txt'
            ids = ('DeepwaterHub', 'DeepwaterEncounter', 'ChayulaLeague', 'HeistHub',
                   'HeistBunker1', 'ExpeditionVolcano', 'BetrayalSafeHouseFortress', 'Incursion_Temple10', 'LegionLeague4',
                   'KalguuranSettlersLeague', 'SanctumNave', 'Delve_Hub', 'Delve_Main',
                   'DelveBossLich', 'Menagerie_Hub', 'Labyrinth_Airlock', '1_Labyrinth_boss_1',
                   'HideoutOssuary', '1_1_town', 'MapWorldsDunes', 'MapWorldsElderArena')
            lines = []

            for index, area in enumerate(ids):
                lines.extend([CollectionFixture.line(index * 60, f'Generating level 60 area "{area}" with seed {index + 1}'),
                              CollectionFixture.line(index * 60 + 1, ': You have entered <script>Synthetic</script>.')])

            lines.append(CollectionFixture.line(len(ids) * 60, 'Generating level 60 area "2_11_town" with seed 99'))
            lines.append(CollectionFixture.line(len(ids) * 60 + 1, ': You have entered Karui Shores.'))
            source.write_text(''.join(lines))
            copy.write_bytes(source.read_bytes())

            CollectionAnalysisService.analyze_collection([source, copy], root / 'analysis')

            for language, title in (('ru', 'Особые области'), ('en', 'Special areas')):
                output = root / language

                entry = ReportFixture.export_report(root / 'analysis', output, report_language = language)
                model = json.loads((output / 'project/data/activities.json').read_text())
                children = [child for group in model['groups'] for child in group['children']]

                self.assertEqual([child['totals']['seconds'] for child in children], [59] * 21)
                self.assertEqual([child['totals']['visits'] for child in children], [1] * 21)
                self.assertEqual(sum(group['totals']['seconds'] for group in model['groups']), 59 * 21)
                self.assertEqual(sum(group['totals']['visits'] for group in model['groups']), 21)

                html = (entry.parent / 'activities/index.html').read_text()

                self.assertIn(title, html)
                self.assertEqual(html.count('data-activity-group='), 17)
                self.assertEqual(html.count('data-activity-lane='), 21)
                self.assertIn('id="activity-delve-azurite_mine"', html)
                self.assertIn('id="activity-labyrinth-aspirants_plaza"', html)
                self.assertEqual(html.count('<svg'), 1)
                self.assertEqual(html.count('data-activity-interval'), 21)
                self.assertIn('&lt;script&gt;Synthetic&lt;/script&gt;', html)
                self.assertNotIn('<script>Synthetic', html)
                self.assertIn('technical/timeline/2026-09-01/index.html#line-2', html)
                self.assertIn('activities/index.html', entry.read_text())

                manifest = json.loads((output / 'report-manifest.json').read_text())

                self.assertIn('activities', manifest['views_sha256'])
                self.assertIn('activities/index.html', manifest['public_sha256'])

    def test_subzones_partition_groups_without_duplicate_time(self):
        cases = {
            'DeepwaterHub': 'sovereign', 'DeepwaterEncounterVoyage': 'fathomless',
            'DeepwaterCoralForest': 'fathomless', 'Delve_Hub': 'mine_encampment',
            'Delve_Endless': 'mine_encampment', 'Delve_Main': 'azurite_mine',
            'Delve_Empty': 'azurite_mine', 'Delve_Mines8': 'azurite_mine',
            'DelveBossLich': 'delve_depths', 'Delve_SubmergedPassage': 'delve_depths',
            'Labyrinth_Airlock': 'aspirants_plaza', '1_Labyrinth_AirlockClean': 'aspirants_plaza',
            'EndGame_Labyrinth_boss_1': 'labyrinth_rooms',
        }
        runs = []

        for area, expected in cases.items():
            self.assertEqual(ActivityAreaGroups.subgroup(area), expected)

            runs.append(self.run_record(area, '2026-09-01T12:00:00+05:00', '2026-09-01T12:01:00+05:00', 60))

        model = ActivityTimelineBuilder.build(runs, 'Asia/Almaty', ExecutionContext())

        self.assertEqual(sum(group['totals']['seconds'] for group in model['groups']), len(cases) * 60)

        coordinates = []

        for group in model['groups']:
            self.assertEqual(group['totals']['seconds'], sum(child['totals']['seconds'] for child in group['children']))
            self.assertEqual(group['totals']['visits'], sum(child['totals']['visits'] for child in group['children']))

            coordinates.extend(child['y'] for child in group['children'])

        self.assertEqual(coordinates, sorted(set(coordinates)))
        self.assertGreater(model['height'], max(coordinates))
