"""Application tables: time, repeated entries, midnight, and incomplete runs."""

import unittest

from copy import deepcopy

from poe_log_analyze.stages.composition.MapStatisticsBuilder import MapStatisticsBuilder
from poe_log_analyze.stages.composition.MapFlowBuilder import MapFlowBuilder

from poe_log_analyze.runtime.DurationFormatter import DurationFormatter

from MapStatisticsFixture import MapStatisticsFixture


class MapStatisticsTests(unittest.TestCase):
    """Check output without technical detail or invented exit times."""

    def test_residence_differs_from_span_midnight_and_order(self):
        maps = {"timezone": "Asia/Almaty", "by_date": {
            "2026-07-20": {"runs": [
                MapStatisticsFixture.run(2, "2026-07-20T23:58:00+05:00", "2026-07-21T00:05:00+05:00", 300),
                MapStatisticsFixture.run(1, "2026-07-20T20:00:00+05:00", "2026-07-20T20:05:00+05:00", 300),
                MapStatisticsFixture.run(3, "2026-07-20T21:00:00+05:00", None, 0, kind = "Арена", incomplete = 1),
            ]},
            "2026-07-21": {"runs": [
                MapStatisticsFixture.run(4, "2026-07-21T12:00:00+05:00", None, 30, incomplete = 1),
            ]},
        }}

        result = MapStatisticsBuilder.build_map_statistics(maps)

        self.assertEqual([d["date"] for d in result["days"]], ["2026-07-21", "2026-07-20"])

        rows = result["by_date"]["2026-07-20"]["rows"]

        self.assertEqual([r["entry"] for r in rows], ["20:00:00", "23:58:00"])
        self.assertEqual(rows[1]["exit"], "21.07.2026 00:05:00")
        self.assertEqual(rows[1]["duration"], "00:05:00")
        self.assertEqual(result["by_date"]["2026-07-20"]["duration"], "00:10:00")
        self.assertEqual(result["count"], 3)
        self.assertNotIn("id", rows[0])
        self.assertNotIn("seed", rows[0])

        incomplete = result["by_date"]["2026-07-21"]

        self.assertEqual(incomplete["rows"][0]["duration"], "—")
        self.assertEqual(incomplete["rows"][0]["exit"], "—")
        self.assertEqual(incomplete["duration"], "00:00:00")
        self.assertEqual(incomplete["incomplete"], 1)
        self.assertEqual(incomplete["older"], "2026-07-20")

    def test_empty_and_duration_longer_than_day(self):
        self.assertEqual(MapStatisticsBuilder.build_map_statistics({"timezone": "Asia/Almaty", "by_date": {}})["days"], [])
        self.assertEqual(DurationFormatter.duration_label(90061), "25:01:01")

    def test_measured_return_parts_preserve_incomplete_counts_and_unknown_exit(self):
        entered = '2026-09-01T12:00:00+05:00'
        complete = MapStatisticsFixture.run(1, entered, '2026-09-01T12:00:10+05:00', 10)
        partial = deepcopy(complete)
        partial['unbounded_visits'] = 1
        partial['visits'].append({'entered_at': '2026-09-01T12:01:00+05:00',
                                  'ended_at': None, 'seconds': None, 'bounded': False})
        zero = MapStatisticsFixture.run(2, entered, entered, 0)
        unknown = MapStatisticsFixture.run(3, entered, None, 0, incomplete = 1)
        maps = {'timezone': 'Asia/Almaty', 'by_date': {'2026-09-01': {
            'runs': [partial, zero, unknown]}}}
        before = deepcopy(maps)
        day = MapStatisticsBuilder.build_map_statistics(maps)['by_date']['2026-09-01']

        self.assertEqual(maps, before)
        self.assertEqual((day['count'], day['duration'], day['incomplete']), (3, '00:00:10', 2))
        self.assertEqual([(r['seconds'], r['incomplete']) for r in day['rows']],
                         [(10, True), (0, False), (None, True)])
        self.assertEqual(day['rows'][0]['exit'], '—')
        self.assertIsNone(day['rows'][0]['exited_at'])
        self.assertEqual(day['rows'][1]['duration'], '00:00:00')
        self.assertEqual(day['rows'][2]['duration'], '—')

    def test_flow_orders_visits_by_utc_and_keeps_returns_and_copies(self):
        visits = [
            {"entered_at": "2026-09-02T00:00:00+05:00", "ended_at": "2026-09-02T00:00:10+05:00", "seconds": 10},
            {"entered_at": "2026-09-02T00:05:00+05:00", "ended_at": None, "seconds": None},
        ]
        model = {"by_date": {"2026-09-02": {"runs": [
            {"kind": "Карта", "name": "Beach", "source": "Дом", "visits": visits},
            {"kind": "Карта", "name": "Beach", "source": "Работа", "visits": visits},
            {"kind": "Карта", "name": "Earlier", "source": "Работа", "visits": [
                {"entered_at": "2026-09-01T18:59:00+00:00", "ended_at": "2026-09-01T18:59:10+00:00", "seconds": 10}]},
        ]}}}

        flow = MapFlowBuilder.build_map_flow(model)

        self.assertEqual(flow["count"], 5)
        self.assertEqual(flow["seconds"], 30)
        self.assertEqual(flow["incomplete"], 2)
        self.assertEqual(flow["rows"][0]["name"], "Earlier")
        self.assertEqual([r["source"] for r in flow["rows"][1:]], ["Дом", "Работа", "Дом", "Работа"])

    def test_unknown_times_keep_source_order_without_inventing_duration(self):
        first = self._item("First", 10, "2026-09-01T12:00:00+05:00", None)
        unknown = self._item("Unknown", 20, None, None)
        last = self._item("Last", 30, "2026-09-01T12:10:00+05:00", None)
        maps = {"timezone": "Asia/Almaty", "by_date": {
            "2026-09-01": {"runs": [first, last]}, "undated": {"runs": [unknown]}}}

        flow = MapFlowBuilder.build_map_flow(maps)

        self.assertEqual([row["name"] for row in flow["rows"]], ["First", "Unknown", "Last"])

        middle = flow["rows"][1]

        self.assertEqual(middle["position_at"], first["started_at"])
        self.assertIsNone(middle["entered_at"])
        self.assertIsNone(middle["exited_at"])
        self.assertEqual(middle["duration"], "—")
        self.assertEqual(flow["count"], 3)

        daily = MapStatisticsBuilder.build_map_statistics(maps)

        self.assertEqual(daily["days"][-1]["label"], "Дата входа неизвестна")
        self.assertEqual(daily["count"], 3)
        self.assertEqual(daily["by_date"]["undated"]["rows"][0]["entry"], "—")

    def test_leading_unknown_exit_only_and_clock_regression(self):
        visits = [
            {"entry_line": 1, "entered_at": None, "ended_at": None, "seconds": None},
            {"entry_line": 2, "entered_at": None, "ended_at": "2026-09-01T12:10:00+05:00", "seconds": None},
            {"entry_line": 3, "entered_at": "2026-09-01T12:05:00+05:00", "ended_at": None, "seconds": None},
        ]
        model = {"timezone": "Asia/Almaty", "by_date": {"undated": {
            "runs": [{"kind": "Карта", "name": "Beach", "visits": visits}]}}}

        flow = MapFlowBuilder.build_map_flow(model)

        self.assertEqual([row["entered_at"] for row in flow["rows"]], [visits[2]["entered_at"], None, None])
        self.assertEqual(flow["rows"][1]["position_at"], visits[1]["ended_at"])
        self.assertEqual(flow["rows"][2]["exit"], "01.09.2026 12:10:00")
        self.assertEqual(flow["seconds"], 0)

    def test_known_entry_orders_daily_and_flow_even_without_exit(self):
        runs = []

        for line, clock in enumerate(["00:32:00", "00:06:21", "00:30:20", "00:34:41"], 1):
            entry = f"2026-07-27T{clock}+05:00"
            item = MapStatisticsFixture.run(line, entry, None, 0, incomplete = 1)
            item.update(first_line = line, name = clock)
            item["visits"][0].update(entry_line = line, entered_at = entry, seconds = None)
            runs.append(item)

        model = {"timezone": "Asia/Almaty", "by_date": {"2026-07-27": {"runs": runs}}}
        daily = MapStatisticsBuilder.build_map_statistics(model)["by_date"]["2026-07-27"]

        flow = MapFlowBuilder.build_map_flow(model)

        for rows in (daily["rows"], flow["rows"]):
            self.assertEqual([r["name"] for r in rows], ["00:06:21", "00:30:20", "00:32:00", "00:34:41"])
            self.assertTrue(all(r["exited_at"] is None and r["duration"] == "—" for r in rows))

        self.assertEqual(daily["incomplete"], 4)
        self.assertEqual(flow["seconds"], 0)

    def test_known_exit_precedes_context_anchor_in_daily_and_flow(self):
        runs = []

        for line, clock in enumerate(["00:32:00", "00:30:20", "00:34:41"], 1):
            exit = f"2026-07-27T{clock}+05:00"
            item = MapStatisticsFixture.run(line, None, exit, 0, incomplete = 1)
            item.update(first_line = line, name = clock, position_at = "2026-07-27T00:00:00+05:00")
            item["visits"][0].update(entry_line = line, entered_at = None, seconds = None,
                                     position_at = item["position_at"])
            runs.append(item)

        model = {"timezone": "Asia/Almaty", "by_date": {"undated": {"runs": runs}}}
        daily = MapStatisticsBuilder.build_map_statistics(model)["by_date"]["undated"]

        flow = MapFlowBuilder.build_map_flow(model)

        for rows in (daily["rows"], flow["rows"]):
            self.assertEqual([r["name"] for r in rows], ["00:30:20", "00:32:00", "00:34:41"])
            self.assertTrue(all(r["position_at"] == r["exited_at"] for r in rows))
            self.assertTrue(all(r["entered_at"] is None and r["duration"] == "—" for r in rows))
            self.assertTrue(all("по выходу" in r["position_note"] for r in rows))

    def test_flow_groups_local_months_and_days_without_inventing_dates(self):
        boundary = self._item('Boundary', 1, '2026-12-31T23:59:00+05:00', '2027-01-01T00:01:00+05:00')
        boundary['visits'][0]['seconds'] = 120
        returned = self._item('Boundary', 2, '2026-12-31T19:02:00+00:00', '2026-12-31T19:03:00+00:00')
        returned['visits'][0]['seconds'] = 60
        exit_only = self._item('Exit', 4, None, '2027-01-02T12:10:00+05:00')
        unknown = self._item('Unknown', 3, None, None)
        maps = {'timezone': 'Asia/Almaty', 'by_date': {'undated': {
            'runs': [exit_only, returned, boundary, unknown]}}}
        before = deepcopy(maps)

        flow = MapFlowBuilder.build_map_flow(maps)

        self.assertEqual(maps, before)
        self.assertEqual([month['id'] for month in flow['months']], ['2026-12', '2027-01'])

        december, january = flow['months']

        self.assertEqual([day['date'] for day in january['days']], ['2027-01-01', '2027-01-02'])
        self.assertEqual(december['seconds'], 120)
        self.assertEqual(january['seconds'], 60)
        self.assertEqual(january['count'], 2)
        self.assertEqual(january['incomplete'], 1)
        self.assertEqual(january['days'][0]['rows'][0]['entry'], '01.01.2027 00:02:00')
        self.assertEqual(december['days'][0]['rows'][0]['exit'], '01.01.2027 00:01:00')
        self.assertEqual(flow['undated']['count'], 1)
        self.assertIsNotNone(flow['undated']['rows'][0]['position_at'])
        self.assertIsNone(flow['undated']['rows'][0]['entered_at'])

        groups = [*flow['months'], flow['undated']]

        for key in ('count', 'seconds', 'incomplete'):
            self.assertEqual(sum(group[key] for group in groups), flow[key])

    def test_empty_flow_has_no_date_groups(self):
        flow = MapFlowBuilder.build_map_flow({'by_date': {}})

        self.assertEqual(flow['months'], [])
        self.assertEqual(flow['undated']['rows'], [])
        self.assertEqual(flow['count'], 0)

    def _item(self, name, line, entry, exit):
        return {"kind": "Карта", "name": name, "source": "Дом", "id": line,
                "first_line": line, "started_at": entry, "unbounded_visits": 1,
                "seconds": 0, "visits": [{"entry_line": line, "entered_at": entry,
                                           "ended_at": exit, "seconds": None}]}
