import MapPaceTests


class PatternAnalyticsFixture:
    """Synthetic maps, markers, deck outcomes, and filter versions."""

    PAGES = ('pool', 'marker_order', 'acquisitions', 'fault_intervals', 'filters')
    VIEWS = ('map_pool', 'marker_order', 'acquisition_history', 'fault_intervals', 'filter_history')

    @staticmethod
    def text(start = '2026-09-01T00:00:00'):
        rows = (
            (0, 'Client-Safe Instance ID = 1'), (0, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
            (0, ': You have entered Synthetic <Dunes & One>.'), (1, 'Sister Cassia: Synthetic marker.'),
            (2, 'Einhar, Beastmaster: Synthetic marker.'), (3, 'Sister Cassia: Synthetic marker again.'),
            (4, ': Card drawn from the deck: <divination>{Synthetic <Card & A>}'),
            (5, ': Card drawn from the deck: <divination>{Synthetic Card B}'),
            (6, ': Card drawn from the deck: <divination>{Synthetic <Card & A>}'),
            (7, '[Item Filter] Preparing to download online filter syntheticFilter'),
            (8, '[Item Filter] Successfully saved online filter syntheticFilter. Hash is now: a'),
            (9, '[Item Filter] Finished reloading online filter syntheticFilter. Result: true. Hash: a. Type: Normal. Message: Synthetic'),
            (10, '[Item Filter] Finished reloading online filter syntheticFilter. Result: true. Hash: a. Type: Normal. Message: Synthetic'),
            (11, '[Item Filter] Finished reloading online filter syntheticFilter. Result: false. Hash: c. Type: Normal. Message: Synthetic failure'),
            (12, '[Item Filter] Finished reloading online filter syntheticFilter. Result: true. Hash: b. Type: Normal. Message: Synthetic'),
            (13, '[Item Filter] Finished reloading online filter syntheticFilter. Result: true. Hash: b. Type: Normal. Message: Synthetic'),
            (14, '[Item Filter] Online item filter syntheticFilter returned status: 404'),
            (15, '[RENDER] Failed to start device'),
            (20, 'Client-Safe Instance ID = 2'), (20, 'Generating level 80 area "MapWorldsDunes" with seed 2'),
            (20, ': You have entered Synthetic <Dunes & Two>.'), (25, 'Synthetic warning'), (30, '[RENDER] Failed to start device'),
            (35, 'Client-Safe Instance ID = 3'), (35, 'Generating level 80 area "MapWorldsCitySquare" with seed 3'),
            (35, ': You have entered Synthetic City.'), (40, 'Abnormal disconnect: Failed to connect to instance'),
            (42, 'Generating level 1 area "HideoutOssuary" with seed 9'), (42, ': You have entered Synthetic Hideout.'),
            (50, 'Abnormal disconnect: Failed to connect to instance'), (60, 'Closing game gracefully'),
            (604800, 'Client-Safe Instance ID = 4'), (604800, 'Generating level 80 area "MapWorldsDunes" with seed 4'),
            (604800, ': You have entered Synthetic <Dunes & Week>.'), (604810, 'Closing game gracefully'))
        return '\n' * 500 + ''.join(
            (MapPaceTests.MapPaceTests.line(second, message, start).replace('[INFO Client 1]', '[WARN Client 1]')
             if second == 25 else MapPaceTests.MapPaceTests.line(second, message, start))
            for second, message in rows).replace('Hash is now: a', 'Hash is now: ' + 'a' * 64).replace(
                'Hash: a.', 'Hash: ' + 'a' * 64 + '.').replace('Hash: b.', 'Hash: ' + 'b' * 64 + '.').replace(
                'Hash: c.', 'Hash: ' + 'c' * 64 + '.')
