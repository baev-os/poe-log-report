"""Observation summaries count map instances while preserving evidence and unknown dates."""

import json
import unittest

from copy import deepcopy

from pathlib import Path
from tempfile import TemporaryDirectory

from CollectionFixture import CollectionFixture

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.stages.composition.MapObservationStatisticsBuilder import MapObservationStatisticsBuilder


class MapObservationTests(unittest.TestCase):
    @staticmethod
    def map_run(number, entered, mechanics = (), discoveries = (), mercenaries = (), complete = True):
        return {'id': number, 'first_line': number * 100, 'area_id': 'MapWorldsDunes',
                'kind_code': 'map', 'name': 'Synthetic Dunes', 'started_at': entered,
                'date': entered[:10] if entered else 'undated', 'identity_complete': complete,
                'seed': '1', 'instance_id': '1' if complete else None,
                'visits': [{'mechanics': list(mechanics), 'discoveries': list(discoveries),
                            'mercenaries': list(mercenaries)}]}

    @staticmethod
    def event(code, line, timestamp = '2026-09-01T00:00:00+05:00'):
        return {'code': code, 'line': line, 'timestamp': timestamp}

    @staticmethod
    def build(runs):
        return MapObservationStatisticsBuilder.build({'timezone': 'Asia/Almaty',
                    'by_date': {'synthetic': {'runs': runs}}}, ExecutionContext())

    @staticmethod
    def counts(summary):
        return {row['code']: row['count'] for row in summary['rows']}

    def test_returns_first_entry_timezone_period_totals_and_unknown_identity(self):
        first = self.map_run(1, '2026-12-31T18:59:00+00:00', [self.event('blight', 101)])
        first['visits'].append({'mechanics': [self.event('blight', 110), self.event('maven', 111)]})
        second = self.map_run(2, '2027-01-01T01:00:00+05:00', mercenaries = [
            {**self.event('unused', 201), 'speaker': 'Synthetic A'},
            {**self.event('unused', 202), 'speaker': 'Synthetic B'}])
        unknown = self.map_run(3, None, discoveries = [self.event('reflecting_mist', 301, None)], complete = False)
        empty = self.map_run(4, '2027-01-01T02:00:00+05:00')
        arena = dict(self.map_run(5, '2027-01-02T00:00:00+05:00', [self.event('blight', 501)]), kind_code = 'arena')
        runs = [unknown, second, first, empty, arena]
        original = deepcopy(runs)

        result = self.build(runs)

        self.assertEqual(runs, original)
        self.assertEqual((result['map_count'], result['observed_maps'], result['unconfirmed_maps']), (4, 3, 1))
        self.assertEqual({key: value for key, value in self.counts(result).items() if value},
                         {'blight': 1, 'maven': 1, 'mercenaries': 1, 'reflecting_mist': 1})
        self.assertEqual([month['id'] for month in result['months']], ['2026-12', '2027-01'])
        self.assertEqual([month['map_count'] for month in result['months']], [1, 2])
        self.assertEqual(self.counts(result['months'][0])['maven'], 1)
        self.assertEqual(self.counts(result['months'][1])['maven'], 0)

        for code, total in self.counts(result).items():
            self.assertEqual(total, sum(self.counts(month)[code] for month in result['months'])
                             + self.counts(result['undated'])[code])

            for month in result['months']:
                self.assertEqual(self.counts(month)[code], sum(self.counts(day)[code] for day in month['days']))

        blight = next(group for group in result['groups'] if group['code'] == 'blight')
        row = blight['months'][0]['days'][0]['rows'][0]

        self.assertEqual(row['entry'], '31.12.2026 23:59:00')
        self.assertEqual([event['line'] for event in row['evidence']], [101, 110])

        mist = next(group for group in result['groups'] if group['code'] == 'reflecting_mist')

        self.assertEqual(mist['months'], [])
        self.assertEqual(mist['undated'][0]['entry'], '—')
        self.assertEqual(mist['undated'][0]['evidence'][0]['time'], '—')

    def test_partial_shared_start_unifies_maps_and_evidence_but_equal_seed_does_not(self):
        first = self.map_run(1, '2026-09-01T00:00:00+05:00', [self.event('blight', 101)])
        branch = deepcopy(first)
        branch['id'] = 2
        branch['visits'].append({'mechanics': [self.event('maven', 120)]})
        independent = self.map_run(3, first['started_at'], [self.event('blight', 301)])

        result = self.build([first, branch, independent])

        self.assertEqual(result['map_count'], 2)
        self.assertEqual(self.counts(result)['blight'], 2)
        self.assertEqual(self.counts(result)['maven'], 1)

        group = next(group for group in result['groups'] if group['code'] == 'blight')

        self.assertEqual(len(group['months'][0]['days'][0]['rows'][0]['evidence']), 1)

    def test_empty_and_cancellation(self):
        result = self.build([])

        self.assertEqual(result['map_count'], 0)
        self.assertEqual(result['months'], [])
        self.assertTrue(all(row['count'] == 0 for row in result['rows']))

        with self.assertRaises(GenerationCancelled):
            MapObservationStatisticsBuilder.build({'timezone': 'Asia/Almaty', 'by_date': {}},
                                                   ExecutionContext(cancelled = lambda: True))

    def test_report_links_languages_returns_copies_and_escaping(self):
        with TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp') as directory:
            root = Path(directory)
            source = root / 'synthetic.txt'
            line = CollectionFixture.line
            source.write_text('\n' * 500 + ''.join([
                line(0, 'Client-Safe Instance ID = 1'),
                line(1, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
                line(2, ': You have entered Synthetic <script>map</script>.'),
                line(3, 'Sister Cassia: Synthetic dialogue.'),
                line(4, 'Sister Cassia: Synthetic repeat.'),
                line(5, ': The Nameless Seer has appeared nearby.'),
                line(6, 'Alara, the Cyaxan Progeny: Have we met before?'),
                line(10, 'Generating level 1 area "HideoutOssuary" with seed 2'),
                line(11, ': You have entered Hideout.'),
                line(12, 'Sister Cassia: Synthetic outside dialogue.'),
                line(14, 'Client-Safe Instance ID = 1'),
                line(15, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
                line(16, ': You have entered Synthetic <script>map</script>.'),
                line(17, 'Sister Cassia: Synthetic return dialogue.'),
                line(18, 'The Maven: Synthetic return dialogue.'),
                line(20, 'Generating level 80 area "MapWorldsBeach" with seed 3'),
                line(21, ': You have entered Beach.'),
                line(22, ': A Reflecting Mist has manifested nearby.'),
                line(25, 'Abnormal disconnect: An unexpected disconnection occurred.'),
            ]))

            for language, title, month in (('ru', 'Механики и особые наблюдения на картах', 'Сентябрь 2026'),
                                           ('en', 'Map mechanics and special observations', 'September 2026')):
                result = ReportGenerator().generate(ReportRequest((source, source), root / language,
                                                                  report_language = language))
                public = result.report_path.parent
                data = json.loads((public.parent / 'project/data/map_observations.json').read_text())

                self.assertEqual(data['map_count'], 2)
                self.assertEqual(self.counts(data)['blight'], 1)
                self.assertEqual(self.counts(data)['mercenaries'], 1)
                self.assertEqual(self.counts(data)['maven'], 1)

                blight = next(group for group in data['groups'] if group['code'] == 'blight')

                self.assertEqual(len(blight['months'][0]['days'][0]['rows'][0]['evidence']), 2)

                overview = (public / 'statistics/index.html').read_text()

                self.assertIn(title, overview)
                self.assertIn('Счётчики лога' if language == 'ru' else 'Log counters', overview)
                self.assertIn('statistics/observations/blight/index.html#month-2026-09', overview)
                self.assertIn('statistics/observations/blight/index.html#day-2026-09-01', overview)

                details = (public / 'statistics/observations/blight/index.html').read_text()

                self.assertIn(month, details)
                self.assertIn('Synthetic &lt;script&gt;map&lt;/script&gt;', details)
                self.assertNotIn('Synthetic <script>', details)
                self.assertIn('../../../events/page-2.html#line-504', details)
                self.assertIn('technical/maps/2026-09-01/index.html#run-1', details)
                self.assertFalse((public / 'statistics/observations/delve/index.html').exists())

                manifest = json.loads((public.parent / 'report-manifest.json').read_text())

                self.assertIn('map_observations', manifest['views_sha256'])
                self.assertIn('statistics/observations/blight/index.html', manifest['public_sha256'])

    def test_diverging_source_prefix_counts_map_once_and_keeps_both_branch_events(self):
        with TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp') as directory:
            root = Path(directory)
            source, branch = root / 'one.txt', root / 'two.txt'
            line = CollectionFixture.line
            prefix = (line(0, 'Generating level 80 area "MapWorldsDunes" with seed 1')
                      + line(1, ': You have entered Dunes.')
                      + line(2, 'Sister Cassia: Synthetic shared dialogue.'))
            source.write_text(prefix + line(3, 'Oshabi: Synthetic first branch.'))
            branch.write_text(prefix + line(3, 'The Maven: Synthetic second branch.'))

            result = ReportGenerator().generate(ReportRequest((source, branch), root / 'report'))
            data = json.loads((result.report_path.parent.parent / 'project/data/map_observations.json').read_text())

            self.assertEqual(data['map_count'], 1)
            self.assertEqual(self.counts(data)['blight'], 1)
            self.assertEqual(self.counts(data)['harvest'], 1)
            self.assertEqual(self.counts(data)['maven'], 1)

            maven = next(group for group in data['groups'] if group['code'] == 'maven')

            self.assertEqual(maven['months'][0]['days'][0]['rows'][0]['evidence'][0]['href'], 'events/index.html#line-5')
