"""Simple summaries use the same measurements as the detailed report."""

import json
import unittest

from datetime import date

from pathlib import Path
from tempfile import TemporaryDirectory

from pypdf import PdfReader

from poe_log_analyze.Bootstrap import Bootstrap
from poe_log_analyze.core.request.ReportMode import ReportMode
from poe_log_analyze.core.request.ReportOutputs import ReportOutputs
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod
from poe_log_analyze.core.request.ReportRequest import ReportRequest
from poe_log_analyze.runtime.RuntimeResources import RuntimeResources
from poe_log_analyze.stages.composition.localization.TranslationCatalogue import TranslationCatalogue


class BasicSummaryTests(unittest.TestCase):
    """Character, area-group, and total-time summaries in HTML/PDF."""

    @classmethod
    def setUpClass(cls):
        cls.temp = TemporaryDirectory(dir = Path('build/tmp').resolve(), prefix = 'basic-summary-')
        cls.root = Path(cls.temp.name)
        cls.source = cls.root / 'synthetic.log'
        cls.source.write_text(cls.source_text(), encoding = 'utf-8')
        cls.original = cls.source.read_bytes()
        cls.generator = Bootstrap.report_generator()
        cls.analysis = cls.generator.generate(ReportRequest((cls.source,), cls.root / 'analysis', mode = ReportMode.ANALYSIS)).directory

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @staticmethod
    def source_text():
        messages = (
            ('2026/09/01 12:00:00', 'Client-Safe Instance ID = 1'),
            ('2026/09/01 12:00:01', 'Generating level 83 area "MapWorldsBeach" with seed 1'),
            ('2026/09/01 12:00:02', ': You have entered Synthetic Beach.'),
            ('2026/09/01 12:01:00', ': Hero (Witch) is now level 20'),
            ('2026/09/01 12:02:00', ': AFK mode is now ON. Autoreply "Synthetic"'),
            ('2026/09/01 12:03:00', ': AFK mode is now OFF.'),
            ('2026/09/01 12:03:20', ': Hero has been slain.'),
            ('2026/09/01 12:04:10', ': Hero (Witch) is now level 21'),
            ('2026/09/01 12:05:00', 'Generating level 1 area "HideoutOssuary" with seed 2'),
            ('2026/09/01 12:05:02', ': You have entered Synthetic Hideout.'),
            ('2026/09/01 12:06:40', ': Guest<script> has been slain.'),
            ('2026/09/01 12:08:20', 'Generating level 83 area "Delve_Main" with seed 3'),
            ('2026/09/01 12:08:22', ': You have entered Synthetic Mine.'),
            ('2026/09/01 12:10:00', ': Hero (Witch) is now level 22'),
            ('2026/09/01 12:11:40', 'Abnormal disconnect: Synthetic end'),
            ('2026/09/03 12:00:00', 'Client-Safe Instance ID = 1'),
            ('2026/09/03 12:00:01', 'Generating level 83 area "DeepwaterHub" with seed 4'),
            ('2026/09/03 12:00:02', ': You have entered Synthetic Sovereign.'),
            ('2026/09/03 12:01:00', ': Hero (Occultist) is now level 23'),
            ('2026/09/03 12:10:00', 'Abnormal disconnect: Synthetic end'),
            ('2026/09/04 12:00:00', 'Client-Safe Instance ID = 1'),
            ('2026/09/04 12:00:01', 'Generating level 83 area "MapWorldsBeach" with seed 5'),
            ('2026/09/04 12:00:02', ': You have entered Synthetic Beach.'),
        )
        return ''.join(f'{stamp} 1 abcd [INFO Client 1] {message}\n' for stamp, message in messages)

    def export(self, name, **options):
        result = self.generator.generate(ReportRequest((self.analysis,), self.root / name, mode = ReportMode.EXPORT,
            outputs = options.pop('outputs', ReportOutputs(True, True, True, True)), **options))
        return result.report_path.parent.parent

    @staticmethod
    def load(path):
        return json.loads(path.read_text(encoding = 'utf-8'))

    def test_summaries_match_detailed_measurements_in_both_languages_and_pdfs(self):
        for language in ('ru', 'en'):
            with self.subTest(language = language):
                root = self.export(language, report_language = language)
                model = self.load(root / 'project/data/basic.json')
                detailed = root / 'extended/project/data'
                characters = self.load(detailed / 'characters.json')['characters']
                groups = self.load(detailed / 'activities.json')['groups']
                afk = self.load(detailed / 'afk.json')['summary']
                daily = self.load(detailed / 'daily_playtime.json')

                self.assertEqual([row['date'] for row in model['daily']], [row['date'] for row in daily['days']])
                self.assertEqual([row['seconds'] for row in model['daily']], [row['seconds'] for row in daily['days']])
                self.assertIn('2026-09-02', [row['date'] for row in model['daily'] if not row['seconds']])
                self.assertEqual(sum(row['seconds'] for row in model['time_balance']['categories']), afk['seconds'])
                self.assertEqual(model['time_balance']['seconds'], model['seconds'])
                self.assertAlmostEqual(sum(row['share'] for row in model['time_balance']['categories']), 100)
                self.assertEqual(model['time_balance']['afk_duration'], '00:01:00')

                for basic, full in zip(model['characters']['characters'], characters, strict = True):
                    self.assertEqual((basic['name'], basic['classes'], basic['count'], basic['deaths']['count']),
                                     (full['name'], full['classes'], full['count'], full['deaths']['count']))
                    self.assertEqual(basic['first'], {'level': full['first']['level']} if full['first'] else None)
                    self.assertEqual(basic['last'], {'level': full['last']['level']} if full['last'] else None)

                guest = next(row for row in model['characters']['characters'] if row['name'] == 'Guest<script>')

                self.assertEqual((guest['classes'], guest['first'], guest['last'], guest['count'], guest['deaths']['count']),
                                 ([], None, None, 0, 1))
                self.assertEqual(len(model['activities']['summary']), 17)

                for basic, full in zip(model['activities']['summary'], groups, strict = True):
                    self.assertEqual((basic['code'], basic['totals']),
                                     (full['code'], {key: full['totals'][key] for key in ('visits', 'duration')}))
                    self.assertEqual([(row['code'], row['totals']) for row in basic['children']],
                                     [(row['code'], {key: row['totals'][key] for key in ('visits', 'duration')}) for row in full['children']])

                catalogue = TranslationCatalogue(language, RuntimeResources.resource_root())
                tr = catalogue.text

                for prefix in ('basic/public', 'extended/public/basic'):
                    graphs = (root / prefix / 'index.html').read_text(encoding = 'utf-8')

                    self.assertIn('class="daily-overview"', graphs)
                    self.assertIn('class="basic-time-balance"', graphs)
                    self.assertNotIn(tr('activities.incomplete'), graphs)

                    html = (root / prefix / 'characters/index.html').read_text(encoding = 'utf-8')

                    self.assertIn('Guest&lt;script&gt;', html)

                    for key in ('characters.first', 'characters.last', 'characters.level_count', 'characters.deaths'):
                        self.assertIn(tr(key), html)

                self.assertNotIn(tr('activities.incomplete'), (root / 'extended/public/activities/index.html').read_text(encoding = 'utf-8'))

                manifest = self.load(root / 'report-manifest.json')

                for profile in ('basic', 'extended'):
                    self.assertEqual(manifest['pdfs'][profile]['content_version'], '14')

                    reader = PdfReader(root / 'pdf' / profile / 'report.pdf')
                    text = ' '.join(' '.join(page.extract_text().split()) for page in reader.pages)

                    for key in ('characters.first', 'characters.last', 'characters.level_count', 'characters.deaths', 'activities.group', 'afk.unallocated'):
                        self.assertIn(tr(key), text)

                    self.assertIn('Guest<script>', text)

                    for page in reader.pages:
                        text = page.extract_text()

                        if tr('activities.intro') in text:
                            self.assertNotIn(tr('activities.incomplete'), text)

                for forbidden in ('"line":', '"entry_line":', '"incomplete_visits":', 'technical/'):
                    self.assertNotIn(forbidden, json.dumps(model))

                self.assertEqual(self.source.read_bytes(), self.original)

    def test_empty_period_keeps_zero_groups_and_unknown_percentages(self):
        root = self.export('empty', period = ReportPeriod(date(2030, 1, 1), date(2030, 1, 2)))
        model = self.load(root / 'project/data/basic.json')

        self.assertEqual(model['daily'], [])
        self.assertEqual(model['characters']['characters'], [])
        self.assertEqual(model['time_balance']['seconds'], 0)
        self.assertEqual(model['time_balance']['afk_percentage'], '—')
        self.assertTrue(all(row['percentage'] == '—' for row in model['time_balance']['categories']))
        self.assertEqual(len(model['activities']['summary']), 17)
        self.assertTrue(all(not row['linked'] and not row['totals']['visits'] for row in model['activities']['summary']))

    def test_dark_pdfs_without_sites_include_summaries(self):
        root = self.export('dark-only', pdf_dark = True, outputs = ReportOutputs(False, True, False, True))
        manifest = self.load(root / 'report-manifest.json')

        self.assertFalse((root / 'basic').exists())
        self.assertFalse((root / 'extended').exists())

        for profile in ('basic', 'extended'):
            self.assertEqual(manifest['pdfs'][profile]['theme'], 'dark')

            text = ' '.join(' '.join(page.extract_text().split()) for page in PdfReader(root / 'pdf' / profile / 'report.pdf').pages)

            self.assertIn('First recorded level', text)
            self.assertIn('Area group', text)
