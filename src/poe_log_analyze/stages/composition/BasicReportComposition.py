from dataclasses import replace

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod

from poe_log_analyze.runtime.DurationFormatter import DurationFormatter
from poe_log_analyze.runtime.RuntimeResources import RuntimeResources

from poe_log_analyze.stages.composition.ActivityTimelineBuilder import ActivityTimelineBuilder
from poe_log_analyze.stages.composition.AfkStatisticsBuilder import AfkStatisticsBuilder
from poe_log_analyze.stages.composition.AllTimeStatisticsBuilder import AllTimeStatisticsBuilder
from poe_log_analyze.stages.composition.BasicReportBuilder import BasicReportBuilder
from poe_log_analyze.stages.composition.CharacterDeathBuilder import CharacterDeathBuilder
from poe_log_analyze.stages.composition.CharacterProgressionBuilder import CharacterProgressionBuilder
from poe_log_analyze.stages.composition.DailyAreaStatisticsBuilder import DailyAreaStatisticsBuilder
from poe_log_analyze.stages.composition.DailyPlaytimeBuilder import DailyPlaytimeBuilder
from poe_log_analyze.stages.composition.MapCalendarBuilder import MapCalendarBuilder
from poe_log_analyze.stages.composition.MapExplorerBuilder import MapExplorerBuilder
from poe_log_analyze.stages.composition.MapStatisticsBuilder import MapStatisticsBuilder
from poe_log_analyze.stages.composition.MechanicCombinationsBuilder import MechanicCombinationsBuilder
from poe_log_analyze.stages.composition.ReportContent import ReportContent
from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection
from poe_log_analyze.stages.composition.WeeklyIntensityBuilder import WeeklyIntensityBuilder
from poe_log_analyze.stages.composition.analytics.MapPoolBuilder import MapPoolBuilder
from poe_log_analyze.stages.composition.events.BasicEventHistoryBuilder import BasicEventHistoryBuilder
from poe_log_analyze.stages.composition.localization.ReportLocalization import ReportLocalization
from poe_log_analyze.stages.composition.localization.TranslationCatalogue import TranslationCatalogue
from poe_log_analyze.stages.composition.sessions.SessionHistoryBuilder import SessionHistoryBuilder
from poe_log_analyze.stages.merging.UnifiedHistory import UnifiedHistory


class BasicReportComposition:
    """Calculate only the five basic sections; HTML and PDF share one projection."""

    @staticmethod
    def build(history: UnifiedHistory, control: ExecutionContext, language: str, period: ReportPeriod) -> ReportContent:
        control.report('Basic report: calculations without extended statistics', force = True)
        zone = history.data['timezone']
        selection = ReportPeriodSelection(period, zone, control)
        runs, intervals = selection.runs(history.runs), selection.intervals(history.intervals)
        seconds = sum(item['seconds'] for item in intervals)
        activity = {'seconds': seconds, 'duration': DurationFormatter.duration_label(seconds), 'intervals': intervals}
        daily = DailyPlaytimeBuilder.build(activity, zone)
        sessions = SessionHistoryBuilder(history.sessions, history.intervals, runs, selection, extended = False)
        deaths = CharacterDeathBuilder([], selection)
        events = BasicEventHistoryBuilder.build(history.ledger, history.digest, deaths, selection)
        timeline = events['timeline']
        statistics = MapStatisticsBuilder.calendar_counts(runs, control)
        dates = set(statistics['by_date']) | {day['date'] for day in daily['days']} | events['dates']

        control.report('Basic report: area time and AFK', force = True)
        daily_areas = DailyAreaStatisticsBuilder.build(runs, zone, dates, control)
        afk = AfkStatisticsBuilder.build(intervals, runs, sessions, daily, selection, extended = False)

        control.report('Calculate: continuous activity by weekday', force = True)
        weekly = WeeklyIntensityBuilder.build(intervals, zone, control)

        control.report('Basic report: maps and mechanic combinations', force = True)
        memberships = MapExplorerBuilder.memberships(history.runs, runs, selection)
        pool = MapPoolBuilder.summary([row for row in memberships if row['new']], evidence = False)
        mechanics = MechanicCombinationsBuilder.build({'rows': memberships}, control, extended = False)

        control.report('Basic report: calendar, characters, and special areas', force = True)
        views = {'report_period': selection.metadata(), 'period_comparison': {'enabled': False},
                 'daily_playtime': daily, 'daily_areas': daily_areas, 'weekly_intensity': weekly, 'afk': afk,
                 'calendar': MapCalendarBuilder.build(statistics, daily, daily_areas),
                 'statistics_summary': AllTimeStatisticsBuilder.build(runs, control),
                 'map_pool': {'summary': pool}, 'mechanic_combinations': mechanics,
                 'characters': CharacterProgressionBuilder.build(timeline, control, period = period, deaths = deaths.result()),
                 'activities': ActivityTimelineBuilder.build(runs, zone, control),
                 'conversations': events['conversations']}
        content = ReportContent(analysis = history.data, manifest = {}, timeline = timeline, maps = {},
                                statistics = statistics, activity = activity, flow = {},
                                event_rows = history.ledger.with_name('event-pages.jsonl'), views = views)
        catalogue = TranslationCatalogue(language, RuntimeResources.resource_root())
        control.report('Localize basic report', force = True)
        localized = ReportLocalization(catalogue).localize_basic(content)
        basic = BasicReportBuilder.build(localized, catalogue, control)

        return replace(localized, views = {**localized.views, 'basic': basic})
