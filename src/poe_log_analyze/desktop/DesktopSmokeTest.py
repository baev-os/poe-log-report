import hashlib
import json

from poe_log_analyze.Bootstrap import Bootstrap

from pathlib import Path
from time import monotonic

from poe_log_analyze.desktop.MainWindow import MainWindow

from poe_log_analyze.runtime.Workspace import Workspace

class DesktopSmokeTest:
    """Standalone Tkinter end-to-end check using a synthetic log."""

    def run(self, directory: str, report_language: str = "en") -> int:
        """Check the automatic analysis and HTML workflow for two sources."""

        self.root = Workspace.local_output(Path(directory))
        self.report_language = report_language
        self.root.mkdir(parents = True, exist_ok = False)
        self.phase = 'initial'
        self.source = self.root / "Проверка (дом).txt"
        self.source.write_text(
            "synthetic unknown\n\n"
            "2026/07/20 21:00:00 123 abcd [INFO Client 42] Client-Safe Instance ID = 123\n"
            '2026/07/20 21:00:00 123 abcd [INFO Client 42] Generating level 83 area "MapWorldsBeach" with seed 456\n'
            "2026/07/20 21:00:02 123 abcd [INFO Client 42] : You have entered Test Beach.\n"
            "2026/07/20 21:00:06 123 abcd [INFO Client 42] Sister Cassia: Synthetic dialogue.\n"
            '2026/07/20 21:00:12 123 abcd [INFO Client 42] Generating level 60 area "HideoutOssuary" with seed 789\n'
            "2026/07/20 21:00:14 123 abcd [INFO Client 42] : You have entered Test Hideout.\n"
            "2026/07/20 21:00:15 123 abcd [INFO Client 42] : Trade accepted.\n"
            "2026/07/20 21:00:15 123 abcd [INFO Client 42] : 7 Items identified\n"
            "2026/07/20 21:00:16 123 abcd [INFO Client 42] @From TestPlayer: hello\n"
            "2026/07/20 21:00:16 123 abcd [INFO Client 42] <TEST> SyntheticGuest: Synthetic local chat.\n"
            "2026/07/21 21:00:00 123 abcd [INFO Client 42] : 100 Items identified\n",
            encoding = "utf-8")
        self.second_source = self.root / "Проверка (работа).txt"
        self.second_source.write_bytes(self.source.read_bytes())
        self.original = self.source.read_bytes()
        self.window = MainWindow(Bootstrap.report_generator(), self.root / "report")
        self.window.inputs.add_files([self.source, self.second_source])
        self.window.inputs.set_report_language(report_language)

        period = self.window.inputs.period
        period.use_start.set(True)
        period.use_end.set(True)
        period.start.set("2026-07-20")
        period.end.set("2026-07-20")

        self.window.inputs.compare.set(True)

        baseline = self.window.inputs.comparison_period
        baseline.use_start.set(True)
        baseline.use_end.set(True)
        baseline.start.set("2026-07-21")
        baseline.end.set("2026-07-21")

        self.window.inputs.extended_report.set(True)
        self.window.start_analysis()
        self.started = monotonic()
        self.exit_code = 1
        self.window.after(25, self.tick)
        self.window.mainloop()

        return self.exit_code

    def tick(self):
        if self.window.closed:
            return

        self.window.after(25, self.tick)

        if monotonic() - self.started > 60:
            self.window.cancel_task()

            if self.window.task is None:
                print('The check did not finish within 60 seconds')
                self.window.close()

            return

        if self.window.task is not None:
            return

        try:
            if self.phase == 'cancel':
                self.check_cancellation()
                return

            if self.phase == 'replace':
                self.check_replacement()
                return

            if self.window.session.report_path is None or not self.window.session.report_path.is_file():
                raise ValueError(self.window.progress.message.get())

            public = self.root / "report/extended/public"
            specification = public / "technical/specification/index.html"

            if not specification.is_file() or 'id="rule-area.generate"' not in specification.read_text(encoding = "utf-8"):
                raise ValueError('The log specification is missing from the report')

            timeline = public / "technical/timeline/2026-07-20/index.html"

            if not timeline.is_file() or "Test Beach" not in timeline.read_text(encoding = "utf-8"):
                raise ValueError('The timeline page does not contain the test event')

            maps = public / "technical/maps/2026-07-20/index.html"
            data = json.loads((public.parent / "project/data/maps.json").read_text(encoding = "utf-8"))

            if not maps.is_file() or "Test Beach" not in maps.read_text(encoding = "utf-8") or data["seconds"] != 10:
                raise ValueError("Map analysis did not confirm the test's 10-second visit")

            simple = (public / "maps/2026-07-20/index.html").read_text(encoding = "utf-8")
            exit_label = "Время выхода" if self.report_language == "ru" else "Exit time"

            if "00:00:10" not in simple or exit_label not in simple or "Seed" in simple:
                raise ValueError('The map application table failed verification')

            flow = json.loads((public.parent / "project/data/map_flow.json").read_text(encoding = "utf-8"))
            activity = json.loads((public.parent / "project/data/activity.json").read_text(encoding = "utf-8"))

            if flow["count"] != 1 or flow["seconds"] != 10 or activity["seconds"] != 14:
                raise ValueError('Shared source-history deduplication failed')

            flow_label = "Карты потоком" if self.report_language == "ru" else "Map stream"

            if flow_label not in (public / "flow/index.html").read_text(encoding = "utf-8"):
                raise ValueError('The map-stream page was not created')


            for route in ('events', 'areas', 'conversations', 'playtime', 'technical/issues'):
                if not (public/route/'index.html').is_file():
                    raise ValueError('Missing shared-history page: '+route)

            chat = json.loads((public.parent/'project/data/conversations.json').read_text(encoding = "utf-8"))

            if chat['count'] != 2 or len(chat['groups']) != 2:
                raise ValueError('The merged conversation contains duplicates')

            if (public/'sources').exists() or 'calendar-month' not in (public/'maps/index.html').read_text(encoding = "utf-8"):
                raise ValueError('The unified calendar was not created')

            observations = json.loads((public.parent / 'project/data/map_observations.json').read_text(encoding = 'utf-8'))
            blight = next(row for row in observations['rows'] if row['code'] == 'blight')

            if observations['map_count'] != 1 or blight['count'] != 1:
                raise ValueError('The map-observation summary contains duplicates')

            if not (public / 'statistics/observations/blight/index.html').is_file():
                raise ValueError('The map list for the observation was not created')

            if not (public/'vendor/bootstrap.min.css').is_file():
                raise ValueError('Local Bootstrap resources are missing')

            if not (self.root / "index.html").is_file() or (self.root / "build").exists():
                raise ValueError('The report entry was not created or temporary files remain')

            manifest = json.loads((public.parent / "report-manifest.json").read_text(encoding = "utf-8"))
            selected = json.loads((public.parent / 'project/data/period_log_observations.json').read_text(encoding = "utf-8"))
            full = json.loads((public.parent / 'project/data/log_observations.json').read_text(encoding = "utf-8"))

            if (manifest['report_period']['date_from'] != '2026-07-20'
                    or selected['items_identified'] != 7 or full['items_identified'] != 107):
                raise ValueError('The shared period failed to constrain statistics or changed the complete history')

            if not (self.root / 'report/pdf/basic/report.pdf').is_file() or not (self.root / 'report/pdf/extended/report.pdf').is_file():
                raise ValueError('The selected-period PDF was not created')

            comparison = json.loads((public.parent / 'project/data/period_comparison.json').read_text(encoding = "utf-8"))
            pace = json.loads((public.parent / 'project/data/map_pace.json').read_text(encoding = "utf-8"))['summary']

            for metric, key in (('map_count', 'count'), ('new_maps', 'new'), ('map_returns', 'returns'),
                                ('maps_per_hour', 'rate'), ('mean_map_seconds', 'mean_seconds'),
                                ('measured_maps', 'complete'), ('excluded_maps', 'excluded')):
                if comparison['b'][metric] != pace[key]:
                    raise ValueError('Map pace disagrees with period comparison: ' + metric)

            if pace['mean_seconds'] != 10 or pace['new'] != 1 or pace['returns'] != 0:
                raise ValueError('Map duration and new-entry counts were not confirmed')

            if (not (public / 'comparison/index.html').is_file()
                    or comparison['a']['map_count'] != 0 or comparison['b']['map_count'] != 1
                    or comparison['a']['play_seconds'] != 0 or comparison['b']['play_seconds'] != 14
                    or manifest['comparison_period']['date_from'] != '2026-07-21'):
                raise ValueError('Period comparison did not confirm independent A and B values')

            if manifest["report_language"] != self.report_language or f'lang="{self.report_language}"' not in self.window.session.report_path.read_text(encoding = "utf-8"):
                raise ValueError('The selected language was not saved in the report')

            if self.phase == 'initial':
                self.before_cancel = self.report_hashes()
                self.source.write_bytes(b'synthetic unknown\n' * 100000)
                self.phase = 'cancel'
                self.window.start_analysis()
                self.window.cancel_task()
                return

            self.source.unlink()
            self.second_source.unlink()

            summary = {"passed": True, "sources": 2, "report_language": self.report_language,
                       "play_seconds": activity["seconds"], "cancellation_preserved_report": True,
                       "replacement_removed_pdf": True, "temporary_files_removed": True,
                       "entry": str(self.root / "index.html"), "report": str(self.window.session.report_path)}

            (self.root / "self-test.json").write_text(json.dumps(summary, ensure_ascii = False, indent = 2), encoding = "utf-8")
            print(json.dumps(summary, ensure_ascii = False))

            self.exit_code = 0
            self.window.close()
        except Exception as error:
            print(f"Standalone check failed: {error}")
            self.window.close()

    def report_hashes(self):
        paths = [self.root / 'index.html',
                 *(path for path in (self.root / 'report').rglob('*') if path.is_file())]
        return {path.relative_to(self.root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in paths}

    def check_cancellation(self):
        if ('cancelled' not in self.window.progress.message.get()
                or self.report_hashes() != self.before_cancel or (self.root / 'build').exists()):
            raise ValueError('Cancellation changed the previous report or left temporary files')

        self.source.write_bytes(self.original)
        self.window.inputs.extended_report.set(False)
        self.phase = 'replace'
        self.window.start_analysis()

    def check_replacement(self):
        public = self.root / 'report/public'
        manifest = json.loads((public.parent / 'report-manifest.json').read_text(encoding = "utf-8"))

        if (set(manifest['pdfs']) != {'basic'}
                or not (self.root / 'report/pdf/basic/report.pdf').is_file()
                or (self.root / 'report/extended').exists() or (self.root / 'report/pdf/extended').exists()
                or (self.root / 'report.pdf').exists()
                or (public / 'report.pdf').exists() or (self.root / 'build').exists()
                or 'report.pdf' not in (public / 'index.html').read_text(encoding = "utf-8")):
            raise ValueError('Basic report replacement failed to preserve its PDF or left previous documents or temporary files')

        self.window.inputs.extended_report.set(True)
        self.phase = 'final'
        self.window.start_analysis()
