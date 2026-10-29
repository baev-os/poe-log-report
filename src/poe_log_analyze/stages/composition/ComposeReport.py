

from dataclasses import replace

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod

from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection
from poe_log_analyze.stages.composition.PeriodComparisonBuilder import PeriodComparisonBuilder

from poe_log_analyze.runtime.AreaKind import AreaKind
from poe_log_analyze.runtime.DurationFormatter import DurationFormatter
from poe_log_analyze.runtime.RuntimeResources import RuntimeResources

from poe_log_analyze.stages.composition.AreaHistoryBuilder import AreaHistoryBuilder
from poe_log_analyze.stages.composition.AreaDetailsBuilder import AreaDetailsBuilder
from poe_log_analyze.stages.composition.ActivityTimelineBuilder import ActivityTimelineBuilder
from poe_log_analyze.stages.composition.AfkStatisticsBuilder import AfkStatisticsBuilder
from poe_log_analyze.stages.composition.AfkMeasurements import AfkMeasurements
from poe_log_analyze.stages.composition.CharacterProgressionBuilder import CharacterProgressionBuilder
from poe_log_analyze.stages.composition.CharacterDeathBuilder import CharacterDeathBuilder
from poe_log_analyze.stages.composition.AllTimeStatisticsBuilder import AllTimeStatisticsBuilder
from poe_log_analyze.stages.composition.DailyPlaytimeBuilder import DailyPlaytimeBuilder
from poe_log_analyze.stages.composition.PlaytimeHeatmapBuilder import PlaytimeHeatmapBuilder
from poe_log_analyze.stages.composition.WeeklyIntensityBuilder import WeeklyIntensityBuilder
from poe_log_analyze.stages.composition.DailyAreaStatisticsBuilder import DailyAreaStatisticsBuilder
from poe_log_analyze.stages.composition.MapCalendarBuilder import MapCalendarBuilder
from poe_log_analyze.stages.composition.MapFlowBuilder import MapFlowBuilder
from poe_log_analyze.stages.composition.MapObservationStatisticsBuilder import MapObservationStatisticsBuilder
from poe_log_analyze.stages.composition.MapObservationAnalyticsBuilder import MapObservationAnalyticsBuilder
from poe_log_analyze.stages.composition.MechanicCombinationsBuilder import MechanicCombinationsBuilder
from poe_log_analyze.stages.composition.MapConsistencyBuilder import MapConsistencyBuilder
from poe_log_analyze.stages.composition.DisconnectReturnBuilder import DisconnectReturnBuilder
from poe_log_analyze.stages.composition.analytics.AnalyticsNavigation import AnalyticsNavigation
from poe_log_analyze.stages.composition.analytics.MeasuredSpanIndex import MeasuredSpanIndex
from poe_log_analyze.stages.composition.analytics.RecordedActivityIndex import RecordedActivityIndex
from poe_log_analyze.stages.composition.analytics.MapCycleBuilder import MapCycleBuilder
from poe_log_analyze.stages.composition.analytics.WindowFocusBuilder import WindowFocusBuilder
from poe_log_analyze.stages.composition.analytics.RemainingMonstersBuilder import RemainingMonstersBuilder
from poe_log_analyze.stages.composition.analytics.ReturnProfileBuilder import ReturnProfileBuilder
from poe_log_analyze.stages.composition.analytics.SessionEdgesBuilder import SessionEdgesBuilder
from poe_log_analyze.stages.composition.analytics.ActionObstaclesBuilder import ActionObstaclesBuilder
from poe_log_analyze.stages.composition.analytics.MarkerIntervalsBuilder import MarkerIntervalsBuilder
from poe_log_analyze.stages.composition.analytics.NetworkHealthBuilder import NetworkHealthBuilder
from poe_log_analyze.stages.composition.analytics.PassiveHistoryBuilder import PassiveHistoryBuilder
from poe_log_analyze.stages.composition.analytics.MarkerTimingBuilder import MarkerTimingBuilder
from poe_log_analyze.stages.composition.analytics.AreaRoutePatternsBuilder import AreaRoutePatternsBuilder
from poe_log_analyze.stages.composition.analytics.TradeApiBuilder import TradeApiBuilder
from poe_log_analyze.stages.composition.analytics.LevelProgressBuilder import LevelProgressBuilder
from poe_log_analyze.stages.composition.analytics.AreaPresenceBuilder import AreaPresenceBuilder
from poe_log_analyze.stages.composition.analytics.MemoryHistoryBuilder import MemoryHistoryBuilder
from poe_log_analyze.stages.composition.analytics.StartupHistoryBuilder import StartupHistoryBuilder
from poe_log_analyze.stages.composition.analytics.ClientEnvironmentBuilder import ClientEnvironmentBuilder
from poe_log_analyze.stages.composition.analytics.AcquisitionHistoryBuilder import AcquisitionHistoryBuilder
from poe_log_analyze.stages.composition.analytics.MilestoneHistoryBuilder import MilestoneHistoryBuilder
from poe_log_analyze.stages.composition.analytics.MeasurementCoverageBuilder import MeasurementCoverageBuilder
from poe_log_analyze.stages.composition.analytics.MapPoolBuilder import MapPoolBuilder
from poe_log_analyze.stages.composition.analytics.MarkerOrderBuilder import MarkerOrderBuilder
from poe_log_analyze.stages.composition.analytics.SourceSpanIndex import SourceSpanIndex
from poe_log_analyze.stages.composition.analytics.FaultIntervalsBuilder import FaultIntervalsBuilder
from poe_log_analyze.stages.composition.analytics.FilterHistoryBuilder import FilterHistoryBuilder
from poe_log_analyze.stages.composition.MapProjection import MapProjection
from poe_log_analyze.stages.composition.MapPaceBuilder import MapPaceBuilder
from poe_log_analyze.stages.composition.MapExplorerBuilder import MapExplorerBuilder
from poe_log_analyze.stages.composition.MapOutlierBuilder import MapOutlierBuilder
from poe_log_analyze.stages.composition.MapRunDetailsBuilder import MapRunDetailsBuilder
from poe_log_analyze.stages.composition.MapRunComparisonBuilder import MapRunComparisonBuilder
from poe_log_analyze.stages.composition.PeriodOverviewBuilder import PeriodOverviewBuilder
from poe_log_analyze.stages.composition.LoadingRouteStatisticsBuilder import LoadingRouteStatisticsBuilder
from poe_log_analyze.stages.composition.StabilityStatisticsBuilder import StabilityStatisticsBuilder
from poe_log_analyze.stages.composition.DayOverviewBuilder import DayOverviewBuilder
from poe_log_analyze.stages.composition.WeeklyPaceBuilder import WeeklyPaceBuilder
from poe_log_analyze.stages.composition.MapStatisticsBuilder import MapStatisticsBuilder
from poe_log_analyze.stages.composition.ReportContent import ReportContent
from poe_log_analyze.stages.composition.BasicReportBuilder import BasicReportBuilder
from poe_log_analyze.stages.composition.BasicReportComposition import BasicReportComposition
from poe_log_analyze.stages.composition.TimelineBuilder import TimelineBuilder
from poe_log_analyze.stages.composition.TimelineCalendarBuilder import TimelineCalendarBuilder
from poe_log_analyze.stages.composition.events.EventHistoryBuilder import EventHistoryBuilder
from poe_log_analyze.stages.composition.events.TradeActivityBuilder import TradeActivityBuilder
from poe_log_analyze.stages.composition.sessions.SessionHistoryBuilder import SessionHistoryBuilder
from poe_log_analyze.stages.composition.sessions.SessionTimelineBuilder import SessionTimelineBuilder
from poe_log_analyze.stages.composition.sessions.SessionComparisonBuilder import SessionComparisonBuilder
from poe_log_analyze.stages.composition.sessions.SessionRhythmBuilder import SessionRhythmBuilder
from poe_log_analyze.stages.composition.localization.ReportLocalization import ReportLocalization
from poe_log_analyze.stages.composition.localization.TranslationCatalogue import TranslationCatalogue
from poe_log_analyze.stages.composition.specification.SpecificationBuilder import SpecificationBuilder
from poe_log_analyze.stages.merging.UnifiedHistory import UnifiedHistory


class ComposeReport:
    """Build merged-history views for subsequent localization."""

    def execute(self, history: UnifiedHistory, control: ExecutionContext, report_language: str,
                *, period: ReportPeriod = ReportPeriod(), comparison_period: ReportPeriod | None = None,
                extended: bool = True) -> ReportContent:

        if not extended:
            return BasicReportComposition.build(history, control, report_language, period)

        data, models, runs, intervals = history.data, history.models, history.runs, history.intervals
        zone = data['timezone']
        control.report('Prepare shared timeline', force = True)
        timeline = TimelineBuilder.build_timeline(history.ledger, zone, history.digest, control)
        maps = MapProjection.build([run for run in runs if AreaKind.code(run) in ('map', 'arena')], models, data)
        areas = MapProjection.build([run for run in runs if AreaKind.code(run) not in ('map', 'arena')], models, data)
        maps['ledger_sha256'] = areas['ledger_sha256'] = history.digest
        selection = ReportPeriodSelection(period, zone, control)
        runs, intervals = selection.runs(runs), selection.intervals(intervals)
        selected_maps = selection.model([run for run in runs if AreaKind.code(run) in ('map', 'arena')], zone)
        selected_areas = selection.model([run for run in runs if AreaKind.code(run) not in ('map', 'arena')], zone)
        statistics = MapStatisticsBuilder.build_map_statistics(selected_maps)
        seconds = sum(item['seconds'] for item in intervals)
        activity = {'version': '3', 'seconds': seconds, 'duration': DurationFormatter.duration_label(seconds),
                    'incomplete': sum(item['incomplete'] for item in intervals), 'intervals': intervals}
        specification = SpecificationBuilder.build_specification((RuntimeResources.resource_root()/'docs/rules.md').read_text(encoding = 'utf-8'))
        descriptions = {rule.rule_id: rule.description for family in specification.families for rule in family.rules}
        event_rows = history.ledger.with_name('event-pages.jsonl')
        sessions = SessionHistoryBuilder(history.sessions, history.intervals, runs, selection)
        deaths = CharacterDeathBuilder(history.runs, selection, sessions)
        control.report('Read events, conversations, and client messages', force = True)
        views = EventHistoryBuilder.build(history.ledger, descriptions, control, event_rows = event_rows, period = period, zone_name = zone,
                                        comparison_period = comparison_period, sessions = sessions, deaths = deaths)

        control.report('Calculate: loading routes', force = True)
        views['loading_routes'] = LoadingRouteStatisticsBuilder.build(views['loading'], history.loading_routes, control)

        control.report('Calculate: game stability', force = True)
        views['stability'] = StabilityStatisticsBuilder.build(views['issues'], history.technical_context, sessions, selection)
        comparison = {'version': '4', 'enabled': False}

        if comparison_period is not None:
            comparison = PeriodComparisonBuilder.build(history.runs, history.intervals, zone, comparison_period, period,
                views['comparison_log_observations'], views['period_log_observations'], control, history.sessions)

        daily_playtime = DailyPlaytimeBuilder.build(activity, zone)
        dates = set(statistics['by_date']) | {day['date'] for day in daily_playtime['days']}
        dates.update(DayOverviewBuilder.dates(timeline, views['loading'], selection))
        dates.update(views['stability']['by_date'])
        daily_areas = DailyAreaStatisticsBuilder.build(runs, zone, dates, control)

        control.report('Calculate: recorded AFK', force = True)
        views['afk'] = AfkStatisticsBuilder.build(intervals, runs, sessions, daily_playtime, selection)

        control.report('Calculate: time without AFK', force = True)
        views['daily_playtime_without_afk'] = DailyPlaytimeBuilder.build(
            {'intervals': AfkMeasurements.without(intervals, control)}, zone, reference = daily_playtime)

        control.report('Calculate: time by weekday and hour', force = True)
        views['playtime_heatmap'] = PlaytimeHeatmapBuilder.build(intervals, runs, zone, daily_areas, control,
                                                               afk_rows = views['afk']['rows'])

        control.report('Calculate: continuous activity by weekday', force = True)
        views['weekly_intensity'] = WeeklyIntensityBuilder.build(intervals, zone, control)

        control.report('Calculate: area cards', force = True)
        views['area_details'] = AreaDetailsBuilder.build(history.runs, runs, selection, sessions, daily_areas,
                                                       afk = views['afk'])

        control.report('Calculate: map pace', force = True)
        views['map_pace'] = MapPaceBuilder.build(history.runs, runs, selection, sessions, daily_playtime, daily_areas,
                                               afk = views['afk'])

        control.report('Calculate: map selection', force = True)
        views['map_explorer'] = MapExplorerBuilder.build(views['map_pace'], runs, selection, afk = views['afk'])

        control.report('Calculate: unusually long maps', force = True)
        views['map_outliers'] = MapOutlierBuilder.build(views['map_explorer'], views['area_details'],
                                                       views['map_pace']['gaps'], control)

        control.report('Calculate: weekly trends', force = True)
        views['weekly_pace'] = WeeklyPaceBuilder.build(history.runs, runs, selection, sessions, daily_playtime, daily_areas,
                                                     afk = views['afk'])
        control.report('Calendar, characters, and area summaries', force = True)
        views.update(areas = areas, area_history = AreaHistoryBuilder.build(selected_areas),
                     sessions = sessions.result(timeline),
                     report_period = selection.metadata(),
                     period_comparison = comparison,
                     map_observations = MapObservationStatisticsBuilder.build(selected_maps, control),
                     characters = CharacterProgressionBuilder.build(timeline, control, period = period, deaths = deaths.result()),
                     activities = ActivityTimelineBuilder.build(runs, zone, control),
                     timeline_calendar = TimelineCalendarBuilder.build(timeline, control),
                     map_details_calendar = MapCalendarBuilder.build_details(maps),
                     calendar = MapCalendarBuilder.build(statistics, daily_playtime, daily_areas),
                     daily_playtime = daily_playtime, daily_areas = daily_areas,
                     statistics_summary = AllTimeStatisticsBuilder.build(runs, control))
        SessionTimelineBuilder.build(views['sessions'], runs, intervals, views['loading'], sessions, selection,
                                     afk = views['afk'])

        control.report('Calculate: session comparison', force = True)
        views['session_comparison'] = SessionComparisonBuilder.build(views, sessions, runs, control)

        control.report('Calculate: session rhythm', force = True)
        views['session_rhythm'] = SessionRhythmBuilder.build(history.sessions, intervals, runs,
                                                            views['map_pace'], sessions, selection)

        control.report('Calculate: map-run cards', force = True)
        views['map_run_details'] = MapRunDetailsBuilder.build(history.runs, runs, views, sessions, selection)

        control.report('Calculate: map observations', force = True)
        views['map_observation_analytics'] = MapObservationAnalyticsBuilder.build(
            views['map_observations'], views['map_explorer'], views['map_run_details'], control)

        control.report('Calculate: mechanic combinations', force = True)
        views['mechanic_combinations'] = MechanicCombinationsBuilder.build(views['map_explorer'], control)
        TradeActivityBuilder.enrich(views['trade_activity'], views['map_explorer'], views['map_pace']['gaps'], selection)

        control.report('Calculate: map-duration spread', force = True)
        views['map_consistency'] = MapConsistencyBuilder.build(views['map_explorer'], control)

        control.report('Calculate: returns after disconnection', force = True)
        views['disconnect_returns'] = DisconnectReturnBuilder.build(history.disconnect_returns, sessions, selection)
        spans = MeasuredSpanIndex(intervals, runs, sessions, selection)
        recorded = RecordedActivityIndex(history.activity_evidence, history.runs, views['map_run_details'], sessions, selection)

        control.report('Calculate: map cycles', force = True)
        views['map_cycles'] = MapCycleBuilder.build(history.runs, spans, views['map_run_details'])

        control.report('Calculate: window focus', force = True)
        views['window_focus'] = WindowFocusBuilder.build(history.activity_evidence, spans)

        control.report('Calculate: remaining monsters', force = True)
        views['remaining_monsters'] = RemainingMonstersBuilder.build(recorded, views['map_explorer'])

        control.report('Calculate: repeated visits', force = True)
        views['return_profile'] = ReturnProfileBuilder.build(history.runs, runs, views['map_explorer'], spans,
                                                            views['afk'], views['map_run_details'])

        control.report('Calculate: session beginnings and endings', force = True)
        views['session_edges'] = SessionEdgesBuilder.build(history.runs, spans)

        control.report('Calculate: action obstacles', force = True)
        views['action_obstacles'] = ActionObstaclesBuilder.build(recorded, views['map_pace']['gaps'])

        control.report('Calculate: mechanic intervals', force = True)
        views['marker_intervals'] = MarkerIntervalsBuilder.build(views['map_observations'], views['map_explorer'], spans)
        observations = RecordedActivityIndex(history.observation_evidence, history.runs, views['map_run_details'], sessions, selection)

        control.report('Calculate: connections and network', force = True)
        views['network_health'] = NetworkHealthBuilder.build(observations)

        control.report('Calculate: passive tree', force = True)
        views['passive_history'] = PassiveHistoryBuilder.build(observations)

        control.report('Calculate: time to first markers', force = True)
        views['marker_timing'] = MarkerTimingBuilder.build(history.runs, views['map_explorer'], spans, views['map_run_details'])

        control.report('Calculate: recurring routes', force = True)
        views['area_route_patterns'] = AreaRoutePatternsBuilder.build(observations, spans)

        control.report('Calculate: trade API', force = True)
        views['trade_api'] = TradeApiBuilder.build(observations, spans)

        control.report('Calculate: level progression', force = True)
        views['level_progress'] = LevelProgressBuilder.build(observations, spans)

        control.report('Calculate: character presence', force = True)
        views['area_presence'] = AreaPresenceBuilder.build(observations, spans)

        control.report('Calculate: client memory history', force = True)
        views['memory_history'] = MemoryHistoryBuilder.build(observations)

        control.report('Calculate: client startup stages', force = True)
        views['startup_history'] = StartupHistoryBuilder.build(observations, spans)

        control.report('Calculate: client environment', force = True)
        views['client_environment'] = ClientEnvironmentBuilder.build(observations)

        control.report('Calculate: acquisitions', force = True)
        views['acquisition_history'] = AcquisitionHistoryBuilder.build(observations)

        control.report('Calculate: rewards and achievements', force = True)
        views['milestone_history'] = MilestoneHistoryBuilder.build(observations, spans)

        control.report('Calculate: map pool', force = True)
        views['map_pool'] = MapPoolBuilder.build(views['map_explorer'], spans)

        control.report('Calculate: marker order', force = True)
        views['marker_order'] = MarkerOrderBuilder.build(observations, views['map_explorer'], spans)

        control.report('Calculate: fault intervals', force = True)
        views['fault_intervals'] = FaultIntervalsBuilder.build(observations, SourceSpanIndex(intervals, selection))

        control.report('Calculate: filter versions', force = True)
        views['filter_history'] = FilterHistoryBuilder.build(observations)

        control.report('Calculate: measurement coverage', force = True)
        views['measurement_coverage'] = MeasurementCoverageBuilder.build(views, control)

        control.report('Calculate: analytics navigation', force = True)
        views['analytics_navigation'] = AnalyticsNavigation.build()

        control.report('Calculate: run comparison', force = True)
        views['map_run_comparison'] = MapRunComparisonBuilder.build(views['map_run_details'], control)

        control.report('Calculate: day overview', force = True)
        views['day_overview'] = DayOverviewBuilder.build(timeline, views['loading'], views['sessions'], intervals,
                                                       daily_playtime, daily_areas, selection)

        control.report('Calculate: period overview', force = True)
        views['period_overview'] = PeriodOverviewBuilder.build(views, activity, control)
        content = ReportContent(analysis = data, manifest = history.sources[0].manifest if len(history.sources)==1 else {'artifacts_sha256': {}}, timeline = timeline,
            maps = maps, statistics = statistics, activity = activity, flow = MapFlowBuilder.build_map_flow(selected_maps),
            event_rows = event_rows, views = views)

        catalogue = TranslationCatalogue(report_language, RuntimeResources.resource_root())
        control.report('Localize report', force = True)
        localized = ReportLocalization(catalogue).localize(content)
        control.report('Prepare basic view', force = True)
        basic = BasicReportBuilder.build(localized, catalogue, control)

        return replace(localized, views = {**localized.views, 'basic': basic})
