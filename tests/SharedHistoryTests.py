import json
import unittest

from datetime import date
from itertools import permutations

from pathlib import Path
from tempfile import TemporaryDirectory

from pypdf import PdfReader

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod
from poe_log_analyze.core.request.ReportRequest import ReportRequest


class SharedHistoryTests(unittest.TestCase):
    """Partial copies, branches, and returns share counts and measurements."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @staticmethod
    def line(second, message):
        return f'2026/09/01 00:00:{second:02} 1 abcd [INFO Client 1] {message}\n'

    @classmethod
    def prefix(cls):
        return ''.join(cls.line(second, message) for second, message in (
            (0, 'Client-Safe Instance ID = 1'),
            (0, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
            (2, ': You have entered Dunes.'),
            (4, ': AFK mode is now ON. Autoreply "Synthetic AFK"'),
            (10, 'Sister Cassia: Synthetic common observation.'),
        ))

    @classmethod
    def ending(cls, afk, exit_time, disconnect, message):
        return ''.join(cls.line(second, text) for second, text in (
            (afk, ': AFK mode is now OFF.'),
            (afk + 1, message),
            (exit_time, 'Generating level 1 area "HideoutOssuary" with seed 2'),
            (exit_time + 1, ': You have entered Hideout.'),
            (disconnect, 'Abnormal disconnect: An unexpected disconnection occurred.'),
        ))

    def source(self, name, text):
        path = self.root / name
        path.write_text(text)

        return path

    def report(self, name, sources, **options):
        result = ReportGenerator().generate(ReportRequest(tuple(sources), self.root / name, **options))
        return result.report_path.parent

    @staticmethod
    def data(public, name):
        return json.loads((public.parent / 'project/data' / (name + '.json')).read_text())

    @classmethod
    def runs(cls, public):
        return [run for day in cls.data(public, 'maps')['by_date'].values() for run in day['runs']]

    def test_two_branches_have_one_map_visit_and_count_shared_time_once(self):
        first = self.source('one.txt', self.prefix() + self.ending(12, 20, 30, 'Oshabi: Synthetic first branch.'))
        second = self.source('two.txt', self.prefix() + self.ending(14, 25, 40, 'The Maven: Synthetic second branch.'))
        originals = [path.read_bytes() for path in (first, second)]

        for language in ('ru', 'en'):
            public = self.report(language, [first, second], report_language = language, generate_pdf = True)
            run = self.runs(public)[0]

            self.assertEqual(len(self.runs(public)), 1)
            self.assertEqual((run['entrances'], run['seconds'], run['afk_seconds']), (1, 33, 12))
            self.assertEqual(len(run['visits'][0]['branches']), 2)
            self.assertIsNone(run['visits'][0]['ended_at'])
            self.assertEqual(sorted(p['seconds'] for p in run['visits'][0]['segments']), [8, 10, 15])

            flow = self.data(public, 'map_flow')

            self.assertEqual((flow['count'], flow['seconds'], flow['incomplete']), (1, 33, 0))

            summary = self.data(public, 'statistics_summary')

            self.assertEqual((summary['maps']['count'], summary['maps']['visits'], summary['maps']['seconds']), (1, 1, 33))
            self.assertEqual(self.data(public, 'map_observations')['map_count'], 1)
            self.assertEqual(self.data(public, 'map_statistics')['count'], 1)
            self.assertEqual(self.data(public, 'map_statistics')['by_date']['2026-09-01']['rows'][0]['seconds'], 33)
            self.assertEqual(self.data(public, 'activity')['seconds'], 58)

            daily = self.data(public, 'daily_areas')['by_date']['2026-09-01']
            dunes = next(zone for zone in daily['zones'] if zone['area_id'] == 'MapWorldsDunes')

            self.assertEqual((dunes['visits'], dunes['seconds']), (1, 33))

            group = next(g for g in self.data(public, 'activities')['groups'] if g['code'] == 'maps')

            self.assertEqual(group['totals']['seconds'], 33)
            self.assertEqual(sum(v['end'] - v['start'] for c in group['children'] for v in c['visits']), 33)

            pdf = '\n'.join(page.extract_text() for page in PdfReader(public / 'report.pdf').pages)

            self.assertIn('00:00:33', pdf)
            self.assertIn('00:00:58', pdf)
            self.assertEqual([path.read_bytes() for path in (first, second)], originals)

    def test_three_nested_branches_and_all_input_orders_keep_totals(self):
        first = self.source('one.txt', self.prefix() + self.ending(12, 20, 30, 'Oshabi: Synthetic first branch.'))
        second = self.source('two.txt', self.prefix() + self.ending(14, 25, 40, 'The Maven: Synthetic second branch.'))
        third = self.source('three.txt', self.prefix() + self.ending(12, 28, 45, 'Einhar, Beastmaster: Synthetic third branch.'))

        for index, sources in enumerate(permutations((first, second, third))):
            public = self.report(str(index), sources)
            runs = self.runs(public)

            self.assertEqual((len(runs), runs[0]['entrances'], runs[0]['seconds'], runs[0]['afk_seconds']), (1, 1, 49, 12))
            self.assertEqual(self.data(public, 'activity')['seconds'], 91)
            self.assertEqual(self.data(public, 'map_flow')['count'], 1)
            self.assertEqual(self.data(public, 'analysis')['overlap']['removed_map_seconds'], 18)

    def test_short_eof_copy_is_replaced_by_confirmed_continuation(self):
        short = self.source('short.txt', self.prefix())
        complete = self.source('complete.txt', self.prefix() + self.ending(12, 20, 30, 'Oshabi: Synthetic continuation.'))

        for index, sources in enumerate(((short, complete, short), (complete, short, complete))):
            public = self.report(str(index), sources)
            run = self.runs(public)[0]

            self.assertEqual((run['seconds'], run['entrances'], run['unbounded_visits']), (18, 1, 0))
            self.assertEqual((self.data(public, 'activity')['seconds'], self.data(public, 'activity')['incomplete']), (28, 0))

    def test_unmeasured_branch_preserves_known_part_without_inventing_exit(self):
        first = self.source('one.txt', self.prefix() + self.ending(12, 20, 30, 'Oshabi: Synthetic first branch.'))
        second = self.source('two.txt', self.prefix() + self.line(14, 'The Maven: Synthetic incomplete branch.'))

        public = self.report('report', (first, second))
        run = self.runs(public)[0]

        self.assertEqual((run['seconds'], run['unbounded_visits']), (18, 1))

        visit = run['visits'][0]

        self.assertFalse(visit['bounded'])
        self.assertIsNone(visit['ended_at'])
        self.assertIsNone(visit['seconds'])
        self.assertEqual(self.data(public, 'map_flow')['seconds'], 18)
        self.assertEqual(self.data(public, 'map_flow')['incomplete'], 1)
        self.assertEqual(self.data(public, 'statistics_summary')['maps']['seconds'], 18)
        self.assertEqual(self.data(public, 'daily_areas')['by_date']['2026-09-01']['zone_totals']['seconds'], 18)
        self.assertEqual(self.data(public, 'activity')['seconds'], 32)

        day = self.data(public, 'map_statistics')['by_date']['2026-09-01']

        self.assertEqual((day['duration'], day['incomplete']), ('00:00:18', 1))
        self.assertTrue(day['rows'][0]['incomplete'])
        self.assertIsNone(day['rows'][0]['exited_at'])

    def test_calendar_includes_measured_visit_before_incomplete_return_in_both_languages(self):
        completed_visit = self.ending(12, 20, 30, 'Oshabi: Synthetic observation.')
        source = self.source('return.txt', self.prefix()
                             + ''.join(completed_visit.splitlines(keepends = True)[:-1])
                             + self.line(35, 'Client-Safe Instance ID = 1')
                             + self.line(35, 'Generating level 80 area "MapWorldsDunes" with seed 1')
                             + self.line(36, ': You have entered Dunes.'))

        for language, note in (('ru', 'учтено частично'), ('en', 'partially measured')):
            public = self.report(language, (source,), report_language = language)
            day = self.data(public, 'map_statistics')['by_date']['2026-09-01']

            self.assertEqual((day['count'], day['duration'], day['incomplete']), (1, '00:00:18', 1))
            self.assertEqual(day['rows'][0]['seconds'], self.data(public, 'statistics_summary')['maps']['seconds'])
            self.assertIsNone(day['rows'][0]['exited_at'])

            html = (public / 'maps/2026-09-01/index.html').read_text()

            self.assertIn(f'00:00:18 <small>· {note}</small>', html)

    def test_returns_from_different_branches_remain_separate_visits_of_one_map(self):
        prefix = self.prefix() + self.ending(12, 20, 25, 'Oshabi: Synthetic shared observation.')
        prefix = ''.join(prefix.splitlines(keepends = True)[:-1]) + self.line(25, ': Trade accepted.')
        paths = []

        for name, start, end in (('one.txt', 30, 40), ('two.txt', 35, 45)):
            tail = (self.line(start, 'Client-Safe Instance ID = 1')
                    + self.line(start, 'Generating level 80 area "MapWorldsDunes" with seed 1')
                    + self.line(start + 1, ': You have entered Dunes.')
                    + self.line(end, 'Generating level 1 area "HideoutOssuary" with seed 2'))
            paths.append(self.source(name, prefix + tail))

        public = self.report('report', paths)
        run = self.runs(public)[0]

        self.assertEqual((len(self.runs(public)), run['entrances'], run['returns'], run['seconds']), (1, 3, 2, 36))
        self.assertIsNone(run['between_visits_seconds'])
        self.assertEqual((self.data(public, 'map_flow')['count'], self.data(public, 'map_flow')['seconds']), (3, 36))
        self.assertEqual(self.data(public, 'statistics_summary')['zone_totals']['seconds'], 55)

    def test_periods_clip_shared_segments_and_mechanics_independently(self):
        prefix = ''.join(f'{stamp} 1 abcd [INFO Client 1] {message}\n' for stamp, message in (
            ('2026/09/01 23:59:49', 'Generating level 80 area "MapWorldsDunes" with seed 1'),
            ('2026/09/01 23:59:50', ': You have entered Dunes.'),
            ('2026/09/01 23:59:55', 'Sister Cassia: Synthetic first day.'),
            ('2026/09/02 00:00:00', 'Sister Cassia: Synthetic second day.')))
        first = self.source('one.txt', prefix + self.line(1, 'Oshabi: Synthetic first branch.').replace('09/01', '09/02')
                            + self.line(10, 'Generating level 1 area "HideoutOssuary" with seed 2').replace('09/01', '09/02'))
        second = self.source('two.txt', prefix + self.line(2, 'The Maven: Synthetic second branch.').replace('09/01', '09/02')
                             + self.line(20, 'Generating level 1 area "HideoutOssuary" with seed 2').replace('09/01', '09/02'))

        public = self.report('report', [first, second], period = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2)),
                             comparison_period = ReportPeriod(date(2026, 9, 1), date(2026, 9, 1)), generate_pdf = True)
        comparison = self.data(public, 'period_comparison')

        self.assertEqual((comparison['a']['map_seconds'], comparison['b']['map_seconds']), (10, 30))
        self.assertEqual((comparison['a']['play_seconds'], comparison['b']['play_seconds']), (10, 30))
        self.assertEqual((comparison['a']['map_count'], comparison['b']['map_count']), (1, 1))
        self.assertEqual((comparison['a']['mechanics']['blight'], comparison['b']['mechanics']['blight']), (1, 1))
        self.assertEqual((comparison['a']['mechanics']['harvest'], comparison['b']['mechanics']['harvest']), (0, 1))
        self.assertEqual(self.data(public, 'map_flow')['seconds'], 30)
        self.assertEqual(self.data(public, 'daily_areas')['by_date']['2026-09-02']['zone_totals']['seconds'], 30)
        self.assertEqual(self.runs(public)[0]['seconds'], 40)

    def test_equal_entries_after_divergence_are_not_evidence_of_a_copy(self):
        text = self.prefix() + self.ending(12, 20, 30, 'Oshabi: Synthetic observation.')
        first = self.source('one.txt', 'different first line\n' + text)
        second = self.source('two.txt', 'another first line\n' + text)

        public = self.report('report', (first, second))

        self.assertEqual(len(self.runs(public)), 2)
        self.assertEqual(self.data(public, 'map_flow')['seconds'], 36)
        self.assertEqual(self.data(public, 'activity')['seconds'], 56)

    def test_dst_jump_does_not_add_an_hour_to_the_shared_part(self):
        prefix = ''.join(f'2026/03/29 {clock} 1 abcd [INFO Client 1] {message}\n' for clock, message in (
            ('01:59:49', 'Generating level 80 area "MapWorldsDunes" with seed 1'),
            ('01:59:50', ': You have entered Dunes.'),
            ('03:00:00', 'Sister Cassia: Synthetic shared observation.')))
        paths = []

        for name, second in (('one.txt', 10), ('two.txt', 20)):
            paths.append(self.source(name, prefix + f'2026/03/29 03:00:{second} 1 abcd [INFO Client 1] '
                                     + 'Generating level 1 area "HideoutOssuary" with seed 2\n'))

        public = self.report('report', paths, timezone = 'Europe/Berlin')

        self.assertEqual(self.runs(public)[0]['seconds'], 40)
        self.assertEqual(self.data(public, 'activity')['seconds'], 40)
        self.assertEqual(self.data(public, 'daily_playtime')['days'][0]['seconds'], 40)

    def test_identical_zero_duration_visits_count_once(self):
        source = self.source('zero.txt', self.line(0, 'Generating level 80 area "MapWorldsDunes" with seed 1')
                             + self.line(0, ': You have entered Dunes.')
                             + self.line(0, 'Generating level 1 area "HideoutOssuary" with seed 2'))

        public = self.report('report', [source, source])
        run = self.runs(public)[0]

        self.assertEqual((run['seconds'], run['entrances'], run['unbounded_visits']), (0, 1, 0))
        self.assertEqual(self.data(public, 'map_flow')['count'], 1)
        self.assertEqual(self.data(public, 'statistics_summary')['maps']['measured_visits'], 1)
