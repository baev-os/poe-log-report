"""Mercenary greetings: visit evidence, provenance, and bundled catalogue."""

import hashlib
import json
import unittest

from pathlib import Path
from tempfile import TemporaryDirectory

from unittest.mock import patch

from CollectionFixture import CollectionFixture

from poe_log_analyze.core.ReportGenerator import ReportGenerator
from poe_log_analyze.core.request.ReportRequest import ReportRequest

from poe_log_analyze.runtime.RuntimeResources import RuntimeResources

from poe_log_analyze.stages.reconstruction.MercenaryGreetings import MercenaryGreetings
from poe_log_analyze.stages.rendering.ReportTemplates import ReportTemplates


class MercenaryTests(unittest.TestCase):
    FIRST = 'Alara, the Cyaxan Progeny'
    SECOND = 'Zargan, the Keitan Brute'

    def test_exact_greetings_require_known_family_and_preserve_punctuation(self):
        for text in MercenaryGreetings.greetings():
            self.assertTrue(MercenaryGreetings.matches(self.FIRST, text))
            self.assertTrue(MercenaryGreetings.matches(self.FIRST, text + ' \t'))
            self.assertFalse(MercenaryGreetings.matches(self.FIRST, 'Synthetic prefix: ' + text))
            self.assertFalse(MercenaryGreetings.matches(self.FIRST, text + ' Synthetic suffix.'))

        self.assertTrue(MercenaryGreetings.matches(self.FIRST, 'Death waits with open arms...'))

        for speaker, utterance in (
            (self.FIRST, 'Synthetic combat dialogue.'), (self.FIRST, ''),
            (self.FIRST, 'have we met before?'), (self.FIRST, 'Death waits with open arms!'),
            ('Synthetic, the Cyaxan Impostor', 'Have we met before?'),
            ('Sister Cassia', 'Have we met before?'), ('SyntheticPlayer', 'Have we met before?'),
        ):
            self.assertFalse(MercenaryGreetings.matches(speaker, utterance))

    def test_pinned_data_and_packaged_resource_work_without_source_checkout(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / 'docs/mercenary-greetings.json').read_text())

        for item in manifest['files']:
            self.assertEqual(hashlib.sha256((root / item['path']).read_bytes()).hexdigest(), item['sha256'])

        resource = 'site/data/mercenary-greetings.json'

        self.assertIn(resource, ReportTemplates.files())

        with TemporaryDirectory(dir = root / 'build/tmp') as directory:
            packaged = Path(directory)
            (packaged / resource).parent.mkdir(parents = True)
            (packaged / resource).write_bytes((root / resource).read_bytes())
            MercenaryGreetings.greetings.cache_clear()
            self.addCleanup(MercenaryGreetings.greetings.cache_clear)

            with patch.object(RuntimeResources, 'resource_root', return_value = packaged):
                self.assertTrue(MercenaryGreetings.matches(self.FIRST, 'Have we met before?'))

    def test_export_languages_sources_pagination_and_escaped_greetings(self):
        with TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp') as directory:
            root = Path(directory)
            source, second = root / 'one.txt', root / 'two.txt'
            line = CollectionFixture.line
            source.write_text('\n' * 500 + ''.join([
                line(0, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
                line(1, ': You have entered Dunes.'),
                line(2, f'{self.FIRST}: Have we met before? '),
                line(3, f'{self.FIRST}: Have we met before?'),
                line(4, f'{self.SECOND}: Synthetic combat dialogue.'),
                line(5, f'@From SyntheticPlayer: {self.SECOND}: Have we met before?'),
                line(6, 'Abnormal disconnect: An unexpected disconnection occurred.'),
            ]))
            second.write_text(''.join([
                line(10, 'Generating level 80 area "MapWorldsDunes" with seed 2'),
                line(11, ': You have entered Dunes.'),
                line(12, f'{self.SECOND}: Synthetic <script>greeting</script>'),
            ]))
            # A synthetic catalogue extension checks escaping of the original dialogue.
            greetings = MercenaryGreetings.greetings() | {'Synthetic <script>greeting</script>'}

            for language, label in (('ru', 'Приветствия наёмников'), ('en', 'Mercenary greetings')):
                with patch.object(MercenaryGreetings, 'greetings', return_value = greetings):
                    result = ReportGenerator().generate(ReportRequest((source, second, source), root / language,
                                                                      report_language = language))

                public = result.report_path.parent
                flow = json.loads((public.parent / 'project/data/map_flow.json').read_text())
                first, last = flow['rows']

                self.assertEqual([item['speaker'] for item in first['mercenaries']], [self.FIRST])
                self.assertEqual([item['speaker'] for item in last['mercenaries']], [self.SECOND])
                self.assertEqual(first['mercenaries'][0]['utterance'], 'Have we met before? ')
                self.assertEqual(first['mercenaries'][0]['href'], 'events/page-2.html#line-503')
                self.assertEqual(last['mercenaries'][0]['href'], 'events/page-2.html#line-510')
                self.assertIsNone(last['seconds'])

                html = (public / 'flow/index.html').read_text()

                self.assertIn(label, html)
                self.assertEqual(html.count('class="flow-deaths flow-mercenaries"'), 2)
                self.assertIn('../events/page-2.html#line-510', html)
                self.assertIn('Synthetic &lt;script&gt;greeting&lt;/script&gt;', html)
                self.assertNotIn('<script>greeting</script>', html)
                self.assertNotIn('Synthetic combat dialogue.', html)

    def test_diverging_sources_keep_mercenary_evidence_in_its_own_visit(self):
        with TemporaryDirectory(dir = Path(__file__).resolve().parents[1] / 'build/tmp') as directory:
            root = Path(directory)
            first, second = root / 'one.txt', root / 'two.txt'
            line = CollectionFixture.line
            prefix = (line(0, 'Generating level 80 area "MapWorldsDunes" with seed 1')
                      + line(1, ': You have entered Dunes.'))
            first.write_text(prefix + line(2, f'{self.FIRST}: Have we met before?')
                             + line(3, 'Abnormal disconnect: An unexpected disconnection occurred.'))
            second.write_text(prefix + line(2, f'{self.SECOND}: Have we met before?'))

            result = ReportGenerator().generate(ReportRequest((first, second), root / 'report'))
            flow = json.loads((result.report_path.parent.parent / 'project/data/map_flow.json').read_text())

            self.assertEqual(flow['count'], 1)
            self.assertEqual(sorted([event['speaker'] for event in branch['mercenaries']]
                                    for branch in flow['rows'][0]['branches']), [[self.FIRST], [self.SECOND]])

            second = next(event for event in flow['rows'][0]['mercenaries'] if event['speaker'] == self.SECOND)

            self.assertEqual(second['href'], 'events/index.html#line-5')
