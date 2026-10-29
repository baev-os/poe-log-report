"""Observation samples, shared time methodology, and verifiable HTML evidence."""

import hashlib
import json
import unittest
import MapOutlierTests
import MapPaceTests

from copy import deepcopy
from datetime import date

from itertools import permutations

from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import patch

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.stages.composition.MapObservationAnalyticsBuilder import MapObservationAnalyticsBuilder


class MapObservationAnalyticsTests(unittest.TestCase):
    """Markers prove neither completion nor causation; show small groups explicitly."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @staticmethod
    def fixture():
        events = []

        for index in range(13):
            start = index * 300 if index < 12 else 86400
            marked = index < 5
            area = 'MapWorldsBeach' if index == 11 else 'MapWorldsDunes'
            level = 81 if index == 10 else 80
            duration = 120 if marked else 900 if index in (10, 11) else 60

            # Long unrelated type/level samples do not intersect other maps.
            if index == 11:
                start = 4200

            events.extend(((start, f'Client-Safe Instance ID = {index + 1}'),
                           (start, f'Generating level {level} area "{area}" with seed {index + 1}'),
                           (start, ': You have entered Synthetic <Dunes & Hills>.')))

            if marked:
                events.extend(((start + 5, 'Sister Cassia: Synthetic marker.'),
                               (start + 10, ': AFK mode is now ON. Autoreply "Synthetic"'),
                               (start + 40, ': AFK mode is now OFF.')))

            if index == 0:
                events.extend(((50, ': SyntheticHero has been slain.'),
                               (60, 'Generating level 1 area "HideoutOssuary" with seed 99'),
                               (62, ': You have entered Synthetic Hideout.'),
                               (100, 'Client-Safe Instance ID = 1'),
                               (100, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
                               (102, ': You have entered Synthetic <Dunes & Hills>.'),
                               (110, 'Sister Cassia: Synthetic return marker.')))
                duration = 162

            events.extend(((start + duration, 'Generating level 1 area "HideoutOssuary" with seed 99'),
                           (start + duration + 2, ': You have entered Synthetic Hideout.')))

        events.append((86500, 'Closing game gracefully'))

        return '\n' * 500 + ''.join(MapPaceTests.MapPaceTests.line(second, message, '2026-09-01T00:00:00')
                                     for second, message in events)

    @staticmethod
    def model(rows, members):
        selected = [{'line': row['line']} for row in rows if row['line'] in members]
        observations = {'map_count': len(rows), 'months': [{'days': [{'date': '2026-09-01', 'map_count': len(rows)}]}],
                        'undated': {'map_count': 0},
                        'groups': [{'code': 'blight', 'count': len(selected),
                                    'months': [{'days': [{'date': '2026-09-01', 'rows': selected}]}], 'undated': []}]}
        pages = [{'line': row['line'], 'path': f"maps/runs/{row['line']}/index.html",
                  'visits': [{'death_messages': [{'line': 1000, 'character': 'SyntheticHero'}]}]}
                 for row in rows]

        return MapObservationAnalyticsBuilder.build(observations, {'rows': rows}, {'pages': pages}, ExecutionContext())

    @staticmethod
    def records():
        rows = [dict(MapOutlierTests.MapOutlierTests.record(index, 120 if index < 5 else 60), new = 1, observed = True)
                for index in range(10)]

        for row in rows:
            row['remaining_seconds'] = 90 if row['line'] < 5 else 60

        return rows

    def source(self, text = None, name = 'synthetic.txt'):
        path = self.root / name
        path.write_text(self.fixture() if text is None else text, encoding = 'utf-8')

        return path

    def report(self, name, sources, **options):
        return ReportGenerator().generate(ReportRequest(tuple(sources), self.root / name, **options)).report_path.parent

    @staticmethod
    def data(public, name = 'map_observation_analytics'):
        return json.loads((public.parent / 'project/data' / (name + '.json')).read_text(encoding = 'utf-8'))

    def test_matching_medians_afk_zero_and_no_mutation(self):
        rows = self.records()
        before = deepcopy(rows)
        model = self.model(rows, set(range(5)))
        group = model['by_code']['blight']

        self.assertEqual((group['count'], group['total'], group['share'], group['death_messages']), (5, 10, 50, 1))
        self.assertEqual(group['modes']['all']['groups'][0]['difference_seconds'], 60)
        self.assertEqual(group['modes']['without_afk']['groups'][0]['difference_seconds'], 30)
        self.assertEqual(group['modes']['all']['groups'][0]['change_percent'], 100)
        self.assertEqual(rows, before)

        for row in rows:
            row['seconds'] = row['remaining_seconds'] = 0

        pair = self.model(rows, set(range(5)))['by_code']['blight']['modes']['all']['groups'][0]

        self.assertTrue(pair['ready'])
        self.assertEqual(pair['difference_seconds'], 0)
        self.assertIsNone(pair['change_percent'])

    def test_small_samples_absent_controls_and_unknown_afk(self):
        rows = self.records()
        rows[0]['remaining_seconds'] = None
        group = self.model(rows, set(range(5)))['by_code']['blight']

        self.assertTrue(group['modes']['all']['groups'][0]['ready'])

        pair = group['modes']['without_afk']['groups'][0]

        self.assertEqual((pair['observed']['complete'], pair['observed']['excluded']), (4, 1))
        self.assertFalse(pair['ready'])
        self.assertIsNone(pair['difference_seconds'])
        self.assertEqual(pair['observed']['median_seconds'], 90)

        group = self.model(rows[:5], set(range(5)))['by_code']['blight']
        pair = group['modes']['all']['groups'][0]

        self.assertEqual(pair['unobserved']['count'], 0)
        self.assertIsNone(pair['unobserved']['median_seconds'])
        self.assertIsNone(pair['difference_seconds'])
        self.assertEqual(self.model([], set())['by_code']['blight']['share'], None)

    def test_types_levels_and_common_exclusions_are_not_mixed(self):
        rows = self.records()

        for index, reason in enumerate(('incomplete', 'clipped', 'branched', 'identity', 'multiple_sessions'), 20):
            rows.append(dict(MapOutlierTests.MapOutlierTests.record(index, 99999), new = 1, observed = True, excluded = [reason]))

        rows.append(dict(MapOutlierTests.MapOutlierTests.record(30, 99999, level = 81), new = 1, observed = True))
        rows.append(dict(MapOutlierTests.MapOutlierTests.record(31, 99999, area_id = 'MapWorldsBeach'), new = 1, observed = True))
        unknown = dict(MapOutlierTests.MapOutlierTests.record(32, 99999, level = None), new = 1, observed = False)
        rows.append(unknown)
        conflicting = dict(MapOutlierTests.MapOutlierTests.record(33, 99999), new = 1, observed = True)
        conflicting['visits'].append({'level': 81})
        rows.append(conflicting)
        group = self.model(rows, {0, 1, 2, 3, 4, 32, 33})['by_code']['blight']
        pair = group['modes']['all']['groups'][0]

        self.assertEqual((pair['observed']['complete'], pair['unobserved']['complete'], pair['unobserved']['excluded']), (5, 5, 5))
        self.assertEqual(pair['difference_seconds'], 60)
        self.assertEqual(group['unmatched_maps'], 2)
        self.assertEqual(len(group['modes']['all']['groups']), 1)

    def test_ru_en_reports_context_deduplication_and_manifest(self):
        source = self.source()
        original = source.read_bytes()

        for language in ('ru', 'en'):
            public = self.report(language, (source, source), report_language = language, generate_pdf = True)
            model = self.data(public)
            group = model['by_code']['blight']

            self.assertEqual((group['count'], group['total']), (5, 13))
            self.assertAlmostEqual(group['share'], 500 / 13)
            self.assertEqual([(day['count'], day['total']) for day in group['days']], [(5, 12), (0, 1)])
            self.assertEqual(group['modes']['all']['summary']['median_seconds'], 120)
            self.assertEqual(group['modes']['without_afk']['summary']['median_seconds'], 90)
            self.assertEqual((group['modes']['all']['summary']['returns'], group['death_messages']), (1, 1))

            pair = group['modes']['all']['groups'][0]

            self.assertEqual((pair['observed']['complete'], pair['unobserved']['complete'], pair['difference_seconds']), (5, 6, 60))
            self.assertEqual(len(pair['observed_lines']), 5)
            self.assertEqual(len(pair['unobserved_lines']), 6)
            self.assertEqual(self.data(public, 'map_observations')['map_count'], 13)

            html = (public / 'statistics/observations/blight/index.html').read_text(encoding = 'utf-8')

            self.assertIn('Synthetic &lt;Dunes &amp; Hills&gt;', html)
            self.assertNotIn('Synthetic <Dunes', html)
            self.assertIn('id="observation-analytics"', html)
            self.assertIn('data-observation-day="2026-09-02"', html)
            self.assertIn('data-observation-samples', html)
            self.assertIn('SyntheticHero', html)
            self.assertIn('../../../events/page-2.html#line-', html)

            manifest = json.loads((public.parent / 'report-manifest.json').read_text(encoding = 'utf-8'))

            self.assertEqual(manifest['report_schema_version'], '39')
            self.assertEqual(manifest['pdf']['content_version'], '12')
            self.assertIn('map_observation_analytics', manifest['views_sha256'])
            self.assertTrue((public / 'report.pdf').is_file())

        self.assertEqual(source.read_bytes(), original)

    def test_export_without_source_selected_empty_and_unmarked_periods(self):
        source = self.source()
        analysis = self.root / 'analysis'

        ReportGenerator().generate(ReportRequest((source,), analysis, mode = ReportMode.ANALYSIS))
        source.unlink()

        for day, total, count in ((1, 12, 5), (2, 1, 0), (3, 0, 0)):
            period = ReportPeriod(date(2026, 9, day), date(2026, 9, day))

            public = self.report('day-' + str(day), (analysis,), mode = ReportMode.EXPORT, period = period)
            group = self.data(public)['by_code']['blight']

            self.assertEqual((group['count'], group['total']), (count, total))
            self.assertEqual(group['share'], count * 100 / total if total else None)
            self.assertEqual((public / 'statistics/observations/blight/index.html').exists(), bool(count))

    def test_dst_and_midnight_slice_use_utc_and_existing_exclusions(self):
        prefix = ''.join(MapPaceTests.MapPaceTests.line(second, message, '2026-03-29T01:59:00') for second, message in (
            (0, 'Client-Safe Instance ID = 1'), (0, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
            (0, ': You have entered Dunes.'), (10, 'Sister Cassia: Synthetic marker.'),
            (3720, 'Generating level 1 area "HideoutOssuary" with seed 9'), (3722, ': You have entered Hideout.'),
            (3730, 'Closing game gracefully')))

        public = self.report('dst', (self.source(prefix, 'dst.txt'),), timezone = 'Europe/Berlin')

        self.assertEqual(self.data(public)['by_code']['blight']['modes']['all']['summary']['median_seconds'], 120)

        text = ''.join(MapPaceTests.MapPaceTests.line(second, message, '2026-09-01T23:59:30') for second, message in (
            (0, 'Client-Safe Instance ID = 2'), (0, 'Generating level 80 area "MapWorldsDunes" with seed 2'),
            (0, ': You have entered Dunes.'), (60, 'Sister Cassia: Synthetic marker.'),
            (120, 'Generating level 1 area "HideoutOssuary" with seed 9'), (122, ': You have entered Hideout.'),
            (130, 'Closing game gracefully')))
        source = self.source(text, 'midnight.txt')

        public = self.report('midnight', (source,))

        self.assertEqual(self.data(public)['by_code']['blight']['days'][0]['date'], '2026-09-01')

        public = self.report('clipped', (source,), period = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2)))
        group = self.data(public)['by_code']['blight']

        self.assertEqual((group['count'], group['total']), (1, 1))
        self.assertEqual(group['modes']['all']['summary']['excluded'], 1)
        self.assertIsNone(group['modes']['all']['summary']['median_seconds'])

    def test_branches_and_independent_equal_clocks_preserve_membership(self):
        line = MapPaceTests.MapPaceTests.line
        prefix = ''.join(line(second, message) for second, message in (
            (0, 'Client-Safe Instance ID = 1'), (0, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
            (0, ': You have entered Dunes.'), (5, 'Sister Cassia: Synthetic shared marker.')))
        sources = [self.source(prefix + line(end, 'Generating level 1 area "HideoutOssuary" with seed 9')
                               + line(end + 2, ': You have entered Hideout.'), f'branch-{end}.txt') for end in (60, 80, 100)]

        for index, ordered in enumerate(permutations(sources)):
            group = self.data(self.report('branch-' + str(index), ordered))['by_code']['blight']

            self.assertEqual((group['count'], group['total']), (1, 1))
            self.assertEqual(group['modes']['all']['summary']['complete'], 0)
            self.assertIsNone(group['modes']['all']['summary']['median_seconds'])

        first = self.source(self.fixture(), 'one.txt')
        second = self.source(self.fixture().replace('Synthetic <Dunes & Hills>', 'Synthetic Other'), 'two.txt')
        group = self.data(self.report('independent', (first, second)))['by_code']['blight']

        self.assertEqual((group['count'], group['total']), (10, 26))
        self.assertEqual(group['modes']['all']['summary']['returns'], 2)
        self.assertEqual(group['death_messages'], 2)

    def test_cancellation_preserves_current_report_and_removes_temporary_files(self):
        source = self.source()
        request = ReportRequest((source,), self.root / 'report', replace_report = True)

        ReportGenerator().generate(request)
        before = self.hashes(self.root / 'report')
        entry = (self.root / 'index.html').read_bytes()

        with patch.object(MapObservationAnalyticsBuilder, 'build', side_effect = GenerationCancelled):
            with self.assertRaises(GenerationCancelled):
                ReportGenerator().generate(request)

        self.assertEqual(self.hashes(self.root / 'report'), before)
        self.assertEqual((self.root / 'index.html').read_bytes(), entry)
        self.assertFalse((self.root / 'build').exists())

        with self.assertRaises(GenerationCancelled):
            MapObservationAnalyticsBuilder.build({}, {}, {}, ExecutionContext(cancelled = lambda: True))

    @staticmethod
    def hashes(root):
        return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in root.rglob('*') if path.is_file()}
