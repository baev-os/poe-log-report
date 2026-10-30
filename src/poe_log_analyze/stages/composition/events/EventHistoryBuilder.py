import json

from pathlib import Path
from typing import Any

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod

from poe_log_analyze.stages.composition.LoadingStatisticsBuilder import LoadingStatisticsBuilder
from poe_log_analyze.stages.composition.CharacterDeathBuilder import CharacterDeathBuilder
from poe_log_analyze.stages.composition.events.ConversationBuilder import ConversationBuilder
from poe_log_analyze.stages.composition.events.TechnicalIssueBuilder import TechnicalIssueBuilder
from poe_log_analyze.stages.composition.events.LogHistoryBuilder import LogHistoryBuilder
from poe_log_analyze.stages.composition.events.LogObservationsBuilder import LogObservationsBuilder
from poe_log_analyze.stages.composition.events.CounterHistoryBuilder import CounterHistoryBuilder
from poe_log_analyze.stages.composition.events.TradeActivityBuilder import TradeActivityBuilder
from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection
from poe_log_analyze.stages.composition.sessions.SessionHistoryBuilder import SessionHistoryBuilder


class EventHistoryBuilder:
    """One pass for the full line overview, conversations, faults, and counters."""

    @staticmethod
    def build(ledger: Path, descriptions: dict[str, str], control: ExecutionContext,
              *, event_rows: Path, period: ReportPeriod = ReportPeriod(), zone_name: str = 'Europe/London',
              comparison_period: ReportPeriod | None = None,
              sessions: SessionHistoryBuilder | None = None,
              deaths: CharacterDeathBuilder | None = None) -> dict[str, Any]:

        chat, issues = ConversationBuilder(), TechnicalIssueBuilder(descriptions)
        observations = LogObservationsBuilder()
        counters = CounterHistoryBuilder()
        trading = TradeActivityBuilder(ReportPeriodSelection(period, zone_name, control), sessions) if sessions is not None else None
        loading = LoadingStatisticsBuilder(period, zone_name, control, sessions)
        selected = LogObservationsBuilder() if period.active else observations
        selected_counters = CounterHistoryBuilder() if period.active else counters
        comparison = LogObservationsBuilder() if comparison_period is not None else None

        with ledger.open('rb') as stream, event_rows.open('x', encoding = 'utf-8', newline = '\n') as pages:
            history = LogHistoryBuilder(pages, control)

            for raw in stream:
                control.check()
                row = json.loads(raw)
                history.add(row)
                observations.add(row)
                loading.add(row)

                if trading is not None:
                    trading.add(row)

                if deaths is not None:
                    deaths.add(row)

                if sessions is not None:
                    sessions.add(row)

                if period.active and period.contains(row.get('timestamp'), zone_name):
                    selected.add(row)
                    selected_counters.add(row)

                if comparison is not None and comparison_period is not None and comparison_period.contains(row.get('timestamp'), zone_name):
                    comparison.add(row)

                counters.add(row)
                chat.add(row)
                issues.add(row)

            events = history.result()

        control.check()

        return {'loading': loading.result(), 'conversations': chat.result(), 'issues': issues.result(),
                'trade_activity': trading.result() if trading is not None else None,
                'log_observations': observations.result(), 'events': events,
                'counter_history': counters.result(), 'period_log_observations': selected.result(),
                'period_counter_history': selected_counters.result(),
                'comparison_log_observations': comparison.result() if comparison is not None else None}
