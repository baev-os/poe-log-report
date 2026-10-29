import unittest

from poe_log_analyze.core.execution.ExecutionContext import ExecutionContext
from poe_log_analyze.core.request.ReportPeriod import ReportPeriod

from poe_log_analyze.stages.composition.ReportPeriodSelection import ReportPeriodSelection
from poe_log_analyze.stages.composition.events.TradeActivityBuilder import TradeActivityBuilder


class TradeActivityTests(unittest.TestCase):
    """A request does not prove a trade; copied branches cannot form a shared pair."""

    def setUp(self):
        self.rows = {1: {'path': 'sessions/1/index.html'}}
        self.selection = ReportPeriodSelection(ReportPeriod(), 'UTC', ExecutionContext())

    @staticmethod
    def session(line):
        return 1 if line < 100 else None

    @staticmethod
    def event(line, kind = 'screen.trade', **fields):
        return {'line_number': line, 'type': kind, 'status': 'recognized', 'fields': fields,
                'timestamp': f'2026-09-01T00:{line // 60:02}:{line % 60:02}+00:00', 'text': 'Synthetic <event & value>'}

    def test_requests_are_separate_from_exchange_outcomes(self):
        builder = TradeActivityBuilder(self.selection, self)
        builder.add(self.event(1, state = 'accepted'))
        builder.add(self.event(2, state = 'cancelled'))
        builder.add(self.event(3, 'chat.whisper', direction = 'From', character = 'Synthetic',
                               message = 'Hi, I would like to buy your Synthetic listed for 1 synthetic in Synthetic League'))
        builder.add(self.event(4, 'chat.whisper', direction = 'To', character = 'Synthetic',
                               message = 'Hi, I would like to buy your Synthetic for my 1 synthetic in Synthetic League'))
        builder.add(self.event(5, 'chat.whisper', direction = 'From', character = 'Synthetic', message = 'Hello!'))
        result = builder.result()

        self.assertEqual(result['summary'], {'accepted': 1, 'cancelled': 1, 'incoming_request': 1, 'outgoing_request': 1})
        self.assertEqual(result['unclassified_whispers'], 1)
        self.assertEqual(result['rows'][0]['message'], 'Synthetic <event & value>')

    def test_maps_between_confirmed_exchanges_and_gap_evidence(self):
        builder = TradeActivityBuilder(self.selection, self)

        for line in (1, 10, 20):
            builder.add(self.event(line, state = 'accepted'))

        builder.add(dict(self.event(30, state = 'accepted'), history_boundary = True))
        result = builder.result()
        explorer = {'rows': [{'line': line, 'session_id': '1', 'new': line != 6} for line in (5, 6, 15, 25)]}
        gap = {'session_id': '1', 'started_at': '2026-09-01T00:00:00+00:00',
               'ended_at': '2026-09-01T00:00:12+00:00', 'from_line': 8, 'line': 12}
        TradeActivityBuilder.enrich(result, explorer, {'rows': [gap]}, self.selection)

        self.assertEqual([row['maps'] for row in result['between_exchanges']], [[5], [15]])
        self.assertEqual(result['gaps'][0]['accepted'], 1)
        self.assertEqual(result['gaps'][0]['events'][0]['line'], 10)

    def test_undated_empty_and_unassigned_events(self):
        builder = TradeActivityBuilder(self.selection, self)
        builder.add(dict(self.event(100, state = 'accepted'), timestamp = None))
        result = builder.result()

        self.assertEqual(result['days'][0]['date'], 'undated')
        self.assertIsNone(result['sessions'][0]['id'])

        TradeActivityBuilder.enrich(result, {'rows': []}, {'rows': []}, self.selection)

        self.assertEqual(result['between_exchanges'], [])
