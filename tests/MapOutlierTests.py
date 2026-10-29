import json
import unittest
import MapPaceTests
import SharedHistoryTests

from copy import deepcopy
from datetime import date

from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory

from unittest.mock import patch

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.stages.composition.MapOutlierBuilder import MapOutlierBuilder


class MapOutlierTests(unittest.TestCase):
    """Outliers use comparable instances and proven context only."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @staticmethod
    def fixture():
        events = []

        for index in range(7):
            start = index * 1000
            events.extend((
                (start, f'Client-Safe Instance ID = {index + 1}'),
                (start, f'Generating level 80 area "MapWorldsDunes" with seed {index + 1}'),
                (start, ': You have entered Synthetic <Dunes & Hills>.')))

            if index == 5:
                events.extend((
                    (start + 10, ': AFK mode is now ON. Autoreply "Synthetic"'),
                    (start + 150, ': AFK mode is now OFF.'),
                    (start + 160, ': SyntheticHero has been slain.'),
                    (start + 170, 'Sister Cassia: Synthetic observation.'),
                    (start + 180, 'Generating level 1 area "HideoutOssuary" with seed 99'),
                    (start + 182, ': You have entered Synthetic Hideout.'),
                    (start + 208, f'Client-Safe Instance ID = {index + 1}'),
                    (start + 208, f'Generating level 80 area "MapWorldsDunes" with seed {index + 1}'),
                    (start + 210, ': You have entered Synthetic <Dunes & Hills>.'),
                    (start + 220, ': AFK mode is now ON. Autoreply "Synthetic"'),
                    (start + 260, ': AFK mode is now OFF.')))

            end = start + (270 if index == 5 else 180 if index == 6 else 60)
            events.extend(((end, 'Generating level 1 area "HideoutOssuary" with seed 99'),
                           (end + 2, ': You have entered Synthetic Hideout.')))

        events.append((6200, 'Closing game gracefully'))

        return '\n' * 500 + ''.join(MapPaceTests.MapPaceTests.line(second, message, '2026-09-01T23:00:00')
                                     for second, message in events)

    @staticmethod
    def record(line, seconds, *, level = 80, area_id = 'MapWorldsDunes'):
        return {'line': line, 'name': 'Synthetic Map', 'area_id': area_id, 'icon': '', 'type': 'areas/synthetic/index.html',
                'entry': 'Synthetic time', 'href': f'events/index.html#line-{line}', 'session_href': None,
                'duration': str(seconds), 'afk_duration': '0', 'remaining_duration': str(seconds),
                'seconds': seconds, 'remaining_seconds': seconds, 'returns': 0, 'excluded': [], 'evidence': [],
                'visits': [{'line': line, 'level': level, 'href': f'areas/synthetic/index.html#visit-{line}'}]}

    @classmethod
    def model(cls, rows):
        visits = [{'line': visit['line'], 'entry': 'Synthetic time', 'day_label': 'Synthetic day', 'duration': '',
                   'afk_duration': '', 'remaining_duration': '', 'href': '', 'death_messages': []}
                  for row in rows for visit in row['visits']]
        return MapOutlierBuilder.build({'rows': rows}, {'pages': [{'days': [{'rows': visits}]}]},
                                       {'rows': []}, ExecutionContext())

    @staticmethod
    def data(public, name = 'map_outliers'):
        return json.loads((public.parent / 'project/data' / (name + '.json')).read_text())

    def report(self, name, sources, **options):
        return ReportGenerator().generate(ReportRequest(tuple(sources), self.root / name, **options)).report_path.parent

    def test_peer_median_even_odd_ties_and_zero(self):
        for values in ([0, 0, 0, 0, 0, 120], [10, 20, 30, 40, 50, 60, 700], [0, 5, 5, 5, 9, 20]):
            for index in range(len(values)):
                self.assertEqual(MapOutlierBuilder.peer_median(values, index), median(values[:index] + values[index + 1:]))

    def test_reference_excludes_self_other_ids_levels_and_short_samples(self):
        rows = [self.record(i, value) for i, value in enumerate((30, 40, 50, 60, 70, 180))]
        rows += [self.record(10, 900, level = 81), self.record(11, 900, area_id = 'MapWorldsBeach')]
        before = deepcopy(rows)
        model = self.model(rows)['modes']['all']

        self.assertEqual((model['count'], model['compared'], model['insufficient'], model['excluded']), (1, 6, 2, 0))

        row = model['rows'][0]

        self.assertEqual((row['median_seconds'], row['peers'], row['excess_seconds'], row['excess_percent']), (50, 5, 130, 260))
        self.assertEqual(len(model['groups']), 3)
        self.assertEqual(rows, before)
        self.assertEqual(self.model(rows[:5])['modes']['all']['compared'], 0)

    def test_both_thresholds_zero_baseline_and_unknown_afk(self):
        for baseline, candidate, expected in ((60, 180, 1), (60, 179.999, 0), (200, 399, 0), (200, 400, 1),
                                               (0, 120, 1), (0, 0, 0)):
            rows = [self.record(i, baseline) for i in range(5)] + [self.record(5, candidate)]
            model = self.model(rows)['modes']['all']

            self.assertEqual(model['count'], expected)

            if expected and baseline == 0:
                self.assertIsNone(model['rows'][0]['excess_percent'])
                self.assertEqual(model['rows'][0]['percent_label'], '—')

        rows = [self.record(i, 60) for i in range(5)] + [self.record(5, 240)]
        rows[0]['remaining_seconds'] = None
        model = self.model(rows)

        self.assertEqual(model['modes']['all']['count'], 1)
        self.assertEqual((model['modes']['without_afk']['count'], model['modes']['without_afk']['excluded'],
                          model['modes']['without_afk']['insufficient']), (0, 1, 5))

    def test_ineligible_measurements_and_unknown_or_conflicting_levels(self):
        rows = [self.record(i, 60) for i in range(5)] + [self.record(5, 300)]

        for index, reason in enumerate(('incomplete', 'clipped', 'branched', 'identity', 'multiple_sessions'), 10):
            row = self.record(index, 10000)
            row['excluded'] = [reason]
            rows.append(row)

        rows.extend((self.record(20, 10000, level = None), self.record(21, 10000, area_id = '')))
        mixed = self.record(22, 10000)
        mixed['visits'].append({'line': 23, 'level': None, 'href': ''})
        rows.append(mixed)
        inconsistent = self.record(24, 10000)
        inconsistent['visits'].append({'line': 25, 'level': 81, 'href': ''})
        rows.append(inconsistent)
        model = self.model(rows)['modes']['all']

        self.assertEqual((model['compared'], model['excluded'], model['rows'][0]['median_seconds']), (6, 9, 60))

    def test_ru_en_context_copy_deduplication_and_unchanged_inputs(self):
        source = self.root / 'synthetic.txt'
        source.write_text(self.fixture())
        before = source.read_bytes()

        for language in ('ru', 'en'):
            public = self.report(language, (source, source), report_language = language, generate_pdf = True)
            model = self.data(public)
            all_rows = model['modes']['all']['rows']

            self.assertEqual([row['seconds'] for row in all_rows], [240, 180])
            self.assertEqual([row['median_seconds'] for row in all_rows], [60, 60])
            self.assertEqual([row['seconds'] for row in model['modes']['without_afk']['rows']], [180])
            self.assertEqual(model['modes']['all']['total'], 7)

            context = all_rows[0]['context']

            self.assertEqual((len(context['visits']), len(context['deaths']), len(context['mechanics'])), (2, 1, 1))
            self.assertEqual(context['gaps'][0]['seconds'], 30)
            self.assertEqual(context['deaths'][0]['character'], 'SyntheticHero')
            self.assertTrue(context['deaths'][0]['href'].startswith('events/page-2.html#'))
            self.assertEqual(self.data(public, 'map_pace')['summary']['map_seconds'], 720)

            html = (public / 'pace/index.html').read_text()

            self.assertIn('id="outliers"', html)
            self.assertIn('Synthetic &lt;Dunes &amp; Hills&gt;', html)
            self.assertNotIn('Synthetic <Dunes', html)

            manifest = json.loads((public.parent / 'report-manifest.json').read_text())

            self.assertIn('map_outliers', manifest['views_sha256'])
            self.assertEqual(manifest['pdf']['content_version'], '12')

        self.assertEqual(source.read_bytes(), before)

    def test_period_recomputes_peers_export_without_source_and_independent_clocks(self):
        source = self.root / 'synthetic.txt'
        source.write_text(self.fixture())

        public = self.report('full', (source,))
        independent = self.root / 'independent.txt'
        independent.write_text(self.fixture().replace('Client-Safe Instance ID = ', 'Client-Safe Instance ID = 9'))
        combined = self.data(self.report('independent', (source, independent)))

        self.assertEqual((combined['modes']['all']['total'], combined['modes']['all']['count']), (14, 4))

        source.unlink()
        selected = self.data(self.report('selected', (public.parents[1] / 'analysis',), mode = ReportMode.EXPORT,
            period = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2))))

        self.assertEqual(selected['modes']['all']['compared'], 0)
        self.assertEqual(selected['modes']['all']['insufficient'], 3)

    def test_branched_histories_empty_selection_and_cancellation(self):
        fixture = SharedHistoryTests.SharedHistoryTests
        first, second = self.root / 'first.txt', self.root / 'second.txt'
        first.write_text(fixture.prefix() + fixture.ending(12, 20, 30, 'Oshabi: Synthetic.'))
        second.write_text(fixture.prefix() + fixture.ending(14, 25, 40, 'The Maven: Synthetic.'))
        model = self.data(self.report('branches', (first, second)))

        self.assertEqual((model['modes']['all']['count'], model['modes']['all']['excluded']), (0, 1))
        self.assertEqual(self.model([])['modes']['all']['total'], 0)

        with patch.object(ExecutionContext, 'check', side_effect = GenerationCancelled):
            with self.assertRaises(GenerationCancelled):
                self.model([])

    def test_cancellation_keeps_current_report_and_cleans_workspace(self):
        source = self.root / 'synthetic.txt'
        source.write_text(self.fixture())
        request = ReportRequest((source,), self.root / 'report', replace_report = True)
        generator = ReportGenerator()

        generator.generate(request)
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}

        with patch.object(MapOutlierBuilder, 'context', side_effect = GenerationCancelled('Синтетическая отмена')):
            with self.assertRaises(GenerationCancelled):
                generator.generate(request)

        self.assertEqual(before, {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()})
