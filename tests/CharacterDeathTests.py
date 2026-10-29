import json
import unittest
import CharacterProgressionTests

from copy import deepcopy
from datetime import date, datetime, timedelta

from pathlib import Path
from tempfile import TemporaryDirectory

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.execution.GenerationCancelled import GenerationCancelled
from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.stages.composition.CharacterDeathBuilder import CharacterDeathBuilder
from poe_log_analyze.stages.composition.CharacterProgressionBuilder import CharacterProgressionBuilder
from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection


class CharacterDeathTests(unittest.TestCase):
    """Named events without inferring ownership, level, or another source's area by timestamp."""

    def setUp(self):
        self.temporary = TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @staticmethod
    def row(line, name = 'Hero', stamp = '2026-09-01T23:59:00+05:00', kind = 'screen.slain'):
        return {'line_number': line, 'record_id': line, 'status': 'recognized', 'type': kind,
                'timestamp': stamp, 'fields': {'character': name}}

    @staticmethod
    def builder(runs = (), period = ReportPeriod(), zone = 'Asia/Almaty', control = None):
        return CharacterDeathBuilder(list(runs), ReportPeriodSelection(period, zone, control or ExecutionContext()))

    @staticmethod
    def line(second, message):
        moment = datetime(2026, 9, 1, 23, 59) + timedelta(seconds = second)
        return f'{moment:%Y/%m/%d %H:%M:%S} 1 abcd [INFO Client 1] {message}\n'

    @classmethod
    def fixture(cls):
        return '\n' * 500 + ''.join(cls.line(second, message) for second, message in (
            (0, ': Hero (Duelist) is now level 89'),
            (1, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
            (2, ': You have entered Dunes.'),
            (3, ': Hero has been slain.'),
            (4, ': Hero has committed suicide.'),
            (4, ': Hero has been slain.'),
            (5, ': Hero (Duelist) is now level 90'),
            (6, 'Generating level 1 area "HideoutOssuary" with seed 9'),
            (7, ': You have entered Synthetic <Hideout>.'),
            (8, ': Visitor<script> has been slain.'),
            (9, ': Hero (Slayer) is now level 91'),
            (10, 'Abnormal disconnect: An unexpected disconnection occurred.'),
            (11, ': Hero has been slain.'),
            (12, ': You have died 20 times.'),
            (61, ': Hero has been slain.'),
        ))

    def source(self, name, text):
        path = self.root / name
        path.write_text(text)

        return path

    def report(self, name, sources, **kwargs):
        result = ReportGenerator().generate(ReportRequest(tuple(sources), self.root / name, **kwargs))
        return result.report_path.parent

    @staticmethod
    def model(public):
        return json.loads((public.parent / 'project/data/characters.json').read_text())

    def test_counts_local_dates_order_unknown_time_and_no_counter_inference(self):
        rows = [self.row(2, stamp = '2026-09-01T23:00:00+00:00'),
                self.row(1, kind = 'screen.suicide'), self.row(3, stamp = None),
                self.row(4, name = 'hero'), self.row(5, kind = 'screen.death_count'),
                self.row(6, kind = 'chat.local'), self.row(7), self.row(8)]
        rows[-2]['record_id'] = 1
        rows[-1]['status'] = 'unknown'
        original = deepcopy(rows)
        builder = self.builder()

        for row in rows:
            builder.add(row)

        result = builder.result()

        self.assertEqual(rows, original)
        self.assertEqual(set(result), {'Hero', 'hero'})

        hero = result['Hero']

        self.assertEqual((hero['count'], hero['self_inflicted']), (3, 1))
        self.assertEqual([row['line'] for row in hero['rows']], [1, 2, 3])
        self.assertEqual([day['date'] for day in hero['days']], ['2026-09-01', '2026-09-02', 'undated'])
        self.assertTrue(all(row['area'] is None and row['session_href'] is None for row in hero['rows']))
        self.assertEqual(sum(day['count'] for day in hero['days']), hero['count'])
        self.assertEqual(sum(area['count'] for area in hero['areas']), hero['count'])

    def test_context_uses_event_lines_including_returns_and_ambiguous_evidence(self):
        run = {'name': 'Dunes', 'area_id': 'MapWorldsDunes', 'first_line': 1,
               'death_messages': [{'line': 5}, {'line': 15}],
               'visits': [{'entry_line': 1, 'death_messages': [{'line': 5}]},
                          {'entry_line': 10, 'death_messages': [{'line': 15}]}]}
        other = {'name': 'Other', 'area_id': 'Other', 'first_line': 2,
                 'death_messages': [{'line': 5}], 'visits': []}
        runs = [run, other]
        original = deepcopy(runs)
        builder = self.builder(runs)

        for line in (5, 15, 25):
            builder.add(self.row(line))

        rows = builder.result()['Hero']['rows']

        self.assertEqual([row['area_status'] for row in rows], ['ambiguous', 'known', 'unknown'])
        self.assertIsNone(rows[0]['area'])
        self.assertEqual(rows[1]['area']['href'], 'events/index.html#line-10')
        self.assertEqual(runs, original)

    def test_chart_marks_time_without_levels_merges_ties_and_keeps_all_history(self):
        fixture = CharacterProgressionTests.CharacterProgressionTests
        timeline = fixture.timeline([fixture.event(1, '2026-09-01T12:00:00+05:00', 'Hero', 89),
                                     fixture.event(5, '2026-09-01T12:10:00+05:00', 'Hero', 90),
                                     fixture.event(9, '2026-09-01T12:20:00+05:00', 'Hero', 91)])
        builder = self.builder()

        for line, minute in ((2, '05'), (3, '05'), (6, '15'), (10, '25')):
            builder.add(self.row(line, stamp = f'2026-09-01T12:{minute}:00+05:00'))

        builder.add(self.row(11, stamp = None))
        builder.add(self.row(12, name = 'Other'))
        deaths = builder.result()
        original = deepcopy((timeline, deaths))

        result = CharacterProgressionBuilder.build(timeline, ExecutionContext(), deaths = deaths)

        self.assertEqual((timeline, deaths), original)

        hero, other = result['characters']

        self.assertEqual((result['death_count'], result['event_count']), (6, 3))
        self.assertEqual(hero['charts'][0]['deaths'][0]['count'], 2)
        self.assertEqual(hero['charts'][0]['deaths'][0]['x'], 500)
        self.assertEqual(hero['charts'][1]['deaths'][0]['line'], 6)
        self.assertNotIn('level', hero['charts'][0]['deaths'][0])
        self.assertEqual(len(hero['deaths']['rows']), 5)
        self.assertIsNone(other['first'])
        self.assertEqual((other['events'], other['classes'], other['charts'][0]['deaths']), ([], [], []))

    def test_dst_period_selection_and_cancellation(self):
        builder = self.builder(period = ReportPeriod(date(2026, 10, 25), date(2026, 10, 25)), zone = 'Europe/Berlin')

        for line, stamp in enumerate(('2026-10-25T02:30:00+01:00', '2026-10-25T02:30:00+02:00',
                                      '2026-10-26T00:00:00+01:00', None), 1):
            builder.add(self.row(line, stamp = stamp))

        rows = builder.result()['Hero']['rows']

        self.assertEqual([row['line'] for row in rows], [2, 1])
        self.assertEqual([row['time'][-5:] for row in rows], ['+0200', '+0100'])

        with self.assertRaises(GenerationCancelled):
            self.builder(control = ExecutionContext(cancelled = lambda: True))

        builder.selection.control = ExecutionContext(cancelled = lambda: True)

        with self.assertRaises(GenerationCancelled):
            builder.result()

    def test_export_languages_copies_context_pagination_and_escaping(self):
        source = self.source('source.txt', self.fixture())
        before = source.read_bytes()

        for language, title in (('ru', 'Сообщения о гибели'), ('en', 'Death messages')):
            public = self.report(language, (source, source), report_language = language, generate_pdf = language == 'ru')
            model = self.model(public)

            self.assertEqual((model['version'], model['count'], model['death_count'], model['event_count']), ('4', 2, 6, 3))

            hero, visitor = model['characters']

            self.assertEqual([day['count'] for day in hero['deaths']['days']], [4, 1])
            self.assertEqual(hero['deaths']['self_inflicted'], 1)

            rows = hero['deaths']['rows']

            self.assertEqual(rows[0]['area']['name'], 'Dunes')
            self.assertTrue(rows[0]['session_href'])
            self.assertIsNone(rows[-2]['area'])
            self.assertIsNone(rows[-2]['session_href'])
            self.assertEqual(visitor['deaths']['rows'][0]['area']['name'], 'Synthetic <Hideout>')
            self.assertEqual(visitor['events'], [])

            html = (public / 'characters/index.html').read_text()

            self.assertIn(title, html)
            self.assertIn('Visitor&lt;script&gt;', html)
            self.assertNotIn('Visitor<script>', html)
            self.assertIn('Synthetic &lt;Hideout&gt;', html)
            self.assertIn('class="character-counters"', html)
            self.assertIn('id="death-504"', html)
            self.assertIn('../events/page-2.html#line-504', html)

            for character in model['characters']:
                for row in character['deaths']['rows']:
                    target, anchor = row['href'].split('#')

                    self.assertIn(f'id="{anchor}"', (public / target).read_text())

        self.assertEqual(source.read_bytes(), before)

    def test_period_export_without_source_keeps_death_only_character_and_empty_pdf(self):
        source = self.source('source.txt', self.fixture())

        public = self.report('full', (source,))
        analysis = public.parents[1] / 'analysis'
        source.unlink()

        selected = self.report('selected', (analysis,), mode = ReportMode.EXPORT, generate_pdf = True,
                               period = ReportPeriod(date(2026, 9, 2), date(2026, 9, 2)))
        model = self.model(selected)

        self.assertEqual((model['count'], model['death_count'], model['event_count']), (1, 1, 0))
        self.assertIsNone(model['characters'][0]['first'])

        empty = self.report('empty', (analysis,), mode = ReportMode.EXPORT,
                            period = ReportPeriod(date(2026, 9, 3), date(2026, 9, 3)))

        self.assertEqual(self.model(empty)['characters'], [])

    def test_independent_equal_clocks_and_shared_prefix_keep_exact_context(self):
        one = self.source('one.txt', self.fixture())
        two = self.source('two.txt', self.fixture().replace('MapWorldsDunes', 'MapWorldsBeach')
                          .replace('Dunes.', 'Beach.').replace('seed 1', 'seed 2'))
        model = self.model(self.report('independent', (one, two)))
        hero = next(row for row in model['characters'] if row['name'] == 'Hero')

        self.assertEqual(hero['deaths']['count'], 10)

        assigned = [row for row in hero['deaths']['rows'] if row['area']]

        self.assertEqual({row['area']['name'] for row in assigned}, {'Dunes', 'Beach'})
        self.assertEqual(len({row['session_href'] for row in assigned}), 2)

        prefix = self.fixture().split(self.line(4, ': Hero has committed suicide.'))[0]
        one.write_text(prefix + self.line(5, ': Hero has committed suicide.') + self.line(10, 'Abnormal disconnect: Synthetic one.'))
        two.write_text(prefix + self.line(6, ': Hero has been slain.') + self.line(11, 'Abnormal disconnect: Synthetic two.'))
        hero = self.model(self.report('branches', (one, two)))['characters'][0]

        self.assertEqual(hero['deaths']['count'], 3)
        self.assertTrue(all(row['area']['name'] == 'Dunes' for row in hero['deaths']['rows']))
