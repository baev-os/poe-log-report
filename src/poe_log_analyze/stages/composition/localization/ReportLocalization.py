"""Localize a copy of projections after calculations finish."""

from copy import deepcopy

from poe_log_analyze.runtime.AreaKind import AreaKind

from poe_log_analyze.stages.composition.ReportContent import ReportContent
from poe_log_analyze.stages.composition.localization.EventMessagePresenter import EventMessagePresenter
from poe_log_analyze.stages.composition.localization.TranslationCatalogue import TranslationCatalogue
from poe_log_analyze.stages.composition.localization.ComparisonPresenter import ComparisonPresenter
from poe_log_analyze.stages.composition.localization.WeeklyPacePresenter import WeeklyPacePresenter
from poe_log_analyze.stages.composition.localization.AnalyticsPresenter import AnalyticsPresenter


class ReportLocalization:
    """Explicitly selected presentation fields prevent translation of source values."""

    def __init__(self, catalogue: TranslationCatalogue):
        self.catalogue = catalogue
        self.presenter = EventMessagePresenter(catalogue)

    def localize(self, content: ReportContent) -> ReportContent:
        # History navigation and the raw-line file require no localization.
        history = content.views['events']
        content = deepcopy(content, {id(history): history})
        data = content.analysis
        data["source_label"] = self.catalogue.text("source.player_history")
        data["state"] = self.catalogue.text("state.complete" if data["recognition_complete"] else "state.incomplete")

        if not data["total_lines"]:
            data["percentage"] = self.catalogue.text("state.empty")

        for category in data["diagnostic_categories"]:
            category["category"] = self.catalogue.legacy_label(category["category"])

        for kind in content.timeline["kinds"]:
            kind["label"] = self.catalogue.text("event_title." + kind["type"])

        for day in content.timeline["by_date"].values():
            for event in day["events"]:
                event["kind"] = self.catalogue.text("event_title." + event["type"])
                event["presentation"] = self.presenter.present(event["message"])
                event["description"] = event["presentation"]["text"]

        self.maps(content.maps)

        for day in content.statistics["days"]:
            self.day_label(day)

        for day in content.statistics["by_date"].values():
            self.day_label(day)
            self.positions(day["rows"])

        self.positions(content.flow["rows"])
        views = content.views
        self.basic_views(views)

        for session in views['sessions']['rows']:
            self.positions(session['maps'])
            session['ending_label'] = ' · '.join(self.catalogue.text('session_end.' + code) for code in session['ending_reasons'])

            for track in session['timeline']['tracks']:
                for item in track['items']:
                    event = item.pop('event', None)
                    item['label'] = (event['presentation']['text'] if event else
                                     self.catalogue.text(item['label_key']) if item['label_key'] else '')

        comparison_presenter = ComparisonPresenter(self.catalogue)
        AnalyticsPresenter.present(views, self.catalogue)

        for group in views['map_observation_analytics']['by_code'].values():
            for value in [group, group['undated'], *group['days']]:
                value['share_label'] = comparison_presenter.format(value['share'], 'percent')

            for mode in group['modes'].values():
                for row in mode['groups']:
                    row['difference'] = comparison_presenter.format(row['difference_seconds'], 'duration', signed = True)
                    row['change'] = comparison_presenter.format(row['change_percent'], 'percent', signed = True)

        for run in views['map_run_comparison']['by_run'].values():
            for metric in run['metrics']:
                metric['text'] = comparison_presenter.format(metric['value'], metric['kind'])

        for session in views['session_comparison']['by_session'].values():
            for mode in session['modes'].values():
                for metric in mode['metrics']:
                    metric['text'] = comparison_presenter.format(metric['value'], metric['kind'])

        comparison_presenter.present(views['period_comparison'])
        overview = views['period_overview']

        for highlight in overview['highlights']:
            if highlight['row']:
                metric = highlight['metric']
                kind = {'seconds': 'duration', 'new': 'number', 'loading_share': 'share'}[metric]
                highlight['row']['value'] = comparison_presenter.format(highlight['row'][metric], kind)

        if overview['comparison']['enabled']:
            for row in overview['comparison']['rows']:
                comparison_presenter.row(row)

            for side in ('a', 'b'):
                overview['comparison'][side]['label'] = views['period_comparison'][side]['period']['label']

        WeeklyPacePresenter.present(views['weekly_pace'], self.catalogue)

        for category in views['log_observations']['diagnostics']:
            category['label'] = self.catalogue.legacy_label(category['label'])

            for message in category['messages']:
                message['reason_label'] = self.catalogue.diagnostic_reason(message['reason'])

        self.maps(views["areas"])

        for row in views["area_history"]["rows"]:
            row["kind"] = self.catalogue.text("area." + AreaKind.code(row))

        self.positions(views["area_history"]["rows"])
        views["area_history"]["kinds"] = [self.catalogue.legacy_label(kind) for kind in views["area_history"]["kinds"]]

        observation_months = [month for group in views['map_observations']['groups'] for month in group['months']]

        for month in [*views["timeline_calendar"]["months"],
                      *views['map_details_calendar']['months'], *content.flow['months'],
                      *views['map_observations']['months'], *observation_months]:
            year, number = month["id"].split("-")
            month["label"] = self.catalogue.text("month." + str(int(number))) + " " + year

        for group in views["issues"]["groups"]:
            group["category_code"] = group["category"]
            group["category"] = self.catalogue.text("issue." + group["category"])
            group["title"] = self.catalogue.rule_title(group["code"])

            for event in group["events"]:
                self.unknown_time(event)
                event["presentation"] = self.presenter.present(event["message"])
                event["text"] = event["presentation"]["text"]

        return content

    def localize_basic(self, content: ReportContent) -> ReportContent:
        """Localize only fields used by the basic report."""

        content = deepcopy(content)
        self.basic_views(content.views)

        return content

    def basic_views(self, views: dict) -> None:
        period = views['report_period']
        period['label'] = (self.catalogue.text('period.range', start = period['date_from'] or '…', end = period['date_to'] or '…')
                           if period['active'] else self.catalogue.text('stats.all_time'))

        for day in views['daily_areas']['by_date'].values():
            self.day_label(day)

        for month in views['calendar']['months']:
            year, number = month['id'].split('-')
            month['label'] = self.catalogue.text('month.' + str(int(number))) + ' ' + year

        for group in views["conversations"]["groups"]:
            group["kind"] = self.catalogue.text("chat." + group["kind_code"])

            if group["kind_code"] == "channel":
                group["title"] = self.catalogue.text("chat.channel_title", channel = group["channel"])
            elif group["kind_code"] == "local":
                group["title"] = self.catalogue.text("chat.local")

            for message in group["messages"]:
                self.unknown_time(message)

                if message["direction"] == "Вы →":
                    message["direction"] = self.catalogue.text("chat.outgoing")

    def day_label(self, day: dict) -> None:
        if day["date"] == "undated":
            day["label"] = self.catalogue.text("date.entry_unknown")

    def unknown_time(self, event: dict) -> None:
        if not event["timestamp"]:
            event["time"] = self.catalogue.text("date.time_unknown")

    def positions(self, rows: list) -> None:
        for row in rows:
            row["position_note"] = self.catalogue.legacy_label(row["position_note"])

            if row.get('branched') and not row.get('exited_at'):
                row['exit'] = self.catalogue.text('reason.branches')

    def maps(self, model: dict) -> None:
        for day in model["by_date"].values():
            for run in day["runs"]:
                run["kind_code"] = AreaKind.code(run)
                run["kind"] = self.catalogue.text("area." + run["kind_code"])

                for record in [run, *run["visits"]]:
                    code = record.get("end_reason_code")
                    record["end_reason"] = (self.catalogue.text("reason." + code) if code else
                                            self.catalogue.legacy_label(record["end_reason"]))
