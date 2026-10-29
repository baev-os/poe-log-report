"""Map-stream calendar blocks in actual exports in both languages."""

import json
import unittest

from pathlib import Path
from tempfile import TemporaryDirectory

from CollectionFixture import CollectionFixture

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.request.ReportRequest import ReportRequest


class MapFlowTests(unittest.TestCase):
    def test_visit_events_sources_pagination_escaping_and_languages(self):
        with TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp') as directory:
            root = Path(directory)
            source, second = root / 'one.txt', root / 'two.txt'
            line = CollectionFixture.line
            source.write_text('\n' * 500 + ''.join([
                line(0, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
                line(1, ': You have entered Dunes.'),
                line(2, 'Sister Cassia: Synthetic first message.'),
                line(3, 'Sister Cassia: Synthetic repeated message.'),
                line(4, 'Alva, Master Explorer: Synthetic message.'),
                line(5, ': Synthetic<hero> has been slain.'),
                line(60, 'Generating level 1 area "HideoutOssuary" with seed 2'),
                line(61, ': You have entered Hideout.'),
                line(62, 'Niko, Master of the Depths: Synthetic hideout dialogue.'),
                line(63, ': OutsideMap has been slain.'),
                line(64, 'Abnormal disconnect: An unexpected disconnection occurred.'),
            ]), encoding = 'utf-8')
            second.write_text(''.join([
                line(120, 'Generating level 80 area "MapWorldsDunes" with seed 3'),
                line(121, ': You have entered Dunes.'),
                line(122, 'The Maven: Synthetic message.'),
                line(123, ': SyntheticSecond has been slain.'),
            ]), encoding = 'utf-8')

            for language, title in (('ru', 'Сообщения о гибели'), ('en', 'Death messages')):
                result = ReportGenerator().generate(ReportRequest((source, second, source), root / language,
                                                                  report_language = language))
                public = result.report_path.parent
                flow = json.loads((public.parent / 'project/data/map_flow.json').read_text())

                self.assertEqual(flow['count'], 2)
                self.assertEqual(flow['death_count'], 2)
                self.assertEqual(flow['months'][0]['death_count'], 2)
                self.assertEqual(flow['months'][0]['days'][0]['death_count'], 2)

                first, last = flow['rows']

                self.assertEqual([event['code'] for event in first['mechanics']], ['blight', 'incursion'])
                self.assertEqual([event['code'] for event in last['mechanics']], ['maven'])
                self.assertEqual(first['mechanics'][0]['href'], 'events/page-2.html#line-503')
                self.assertEqual(last['death_messages'][0]['href'], 'events/page-2.html#line-515')
                self.assertIsNone(last['seconds'])

                html = (public / 'flow/index.html').read_text()

                self.assertIn(title, html)
                self.assertIn('Synthetic&lt;hero&gt;', html)
                self.assertNotIn('Synthetic<hero>', html)
                self.assertNotIn('OutsideMap', html)
                self.assertIn('../events/page-2.html#line-503', html)

    def test_diverging_shared_prefix_does_not_mix_events_between_sources(self):
        with TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp') as directory:
            root = Path(directory)
            first, second = root / 'one.txt', root / 'two.txt'
            line = CollectionFixture.line
            prefix = (line(0, 'Generating level 80 area "MapWorldsDunes" with seed 1')
                      + line(1, ': You have entered Dunes.')
                      + line(2, 'Sister Cassia: Synthetic shared dialogue.'))
            first.write_text(prefix + line(3, 'Oshabi: Synthetic first branch.')
                             + line(4, 'Abnormal disconnect: An unexpected disconnection occurred.'))
            second.write_text(prefix + line(3, 'The Maven: Synthetic second branch.'))

            result = ReportGenerator().generate(ReportRequest((first, second), root / 'report'))
            flow = json.loads((result.report_path.parent.parent / 'project/data/map_flow.json').read_text())

            self.assertEqual(flow['count'], 1)
            self.assertEqual(sorted([event['code'] for event in branch['mechanics']]
                                    for branch in flow['rows'][0]['branches']),
                             [['blight', 'harvest'], ['blight', 'maven']])

            maven = next(event for event in flow['rows'][0]['mechanics'] if event['code'] == 'maven')

            self.assertEqual(maven['href'], 'events/index.html#line-6')

    def test_months_days_totals_escaping_and_duplicate_source(self):
        with TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp') as directory:
            root = Path(directory)
            source = root / 'synthetic.txt'
            lines = []

            for index, date in enumerate(('2026/07/31', '2026/08/01', '2026/08/02'), 1):
                for seconds, message in (
                    (0, f'Generating level 80 area "MapWorldsDunes" with seed {index}'),
                    (1, ': You have entered Test <script>map</script>.'),
                    (60, f'Generating level 1 area "HideoutOssuary" with seed {index + 10}'),
                    (61, ': You have entered Synthetic Hideout.'),
                    (120, 'Abnormal disconnect: An unexpected disconnection occurred.'),
                ):
                    lines.append(CollectionFixture.line(seconds, message).replace('2026/09/01', date))

            source.write_text(''.join(lines), encoding = 'utf-8')

            for language, labels in (('ru', ('Июль 2026', 'Август 2026')),
                                     ('en', ('July 2026', 'August 2026'))):
                result = ReportGenerator().generate(ReportRequest((source, source), root / language,
                                                                  report_language = language))
                public = result.report_path.parent
                flow = json.loads((public.parent / 'project/data/map_flow.json').read_text())

                self.assertEqual(flow['count'], 3)
                self.assertEqual(flow['seconds'], 177)
                self.assertEqual([month['label'] for month in flow['months']], list(labels))

                html = (public / 'flow/index.html').read_text()

                self.assertEqual(html.count('class="flow-month"'), 2)
                self.assertEqual(html.count('class="flow-day"'), 3)
                self.assertEqual(html.count('Test &lt;script&gt;map&lt;/script&gt;'), 3)
                self.assertNotIn('Test <script>', html)
                self.assertNotIn('id="flow-undated"', html)
                self.assertLess(html.index('id="month-2026-07"'), html.index('id="month-2026-08"'))
                self.assertLess(html.index('id="flow-day-2026-08-01"'), html.index('id="flow-day-2026-08-02"'))
                self.assertIn('00:02:57', html)
                self.assertIn('00:01:58', html)
