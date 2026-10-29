from MapPaceTests import MapPaceTests


class ExtendedAnalyticsFixture:
    """Synthetic client and gameplay observation markers without real data."""

    PAGES = ('memory', 'startup', 'environment', 'acquisitions', 'milestones', 'coverage')
    VIEWS = ('memory_history', 'startup_history', 'client_environment', 'acquisition_history',
             'milestone_history', 'measurement_coverage')

    @staticmethod
    def text(start = '2026-09-01T00:00:00'):
        rows = (
            (0, '[ENGINE] Init'), (1, '[ENGINE] Running Engine version 1.2.3'),
            (2, '[ENGINE] Build Revision: 100'), (3, '[RENDER] Starting device: Vulkan'),
            (4, '[RENDER] Driver Version: 1.2.3'), (5, '[STARTUP] Game Start'),
            (6, '[STARTUP] Game in 0 seconds'),
            (7, '[MEMORY] Used=0 MB, OsUsed=2 GB, Total=4 GB'), (8, '[STARTUP] Device in 2.5 seconds'),
            (10, 'Client-Safe Instance ID = 1'), (10, 'Generating level 80 area "MapWorldsDunes" with seed 1'),
            (10, ': You have entered Synthetic <Map & One>.'),
            (11, '[MEMORY] Used=128 MB, OsUsed=2.5 GB, Total=4 GB'),
            (12, '[LOADING SCREEN] (Synthetic <Map & One>) Duration = 2.5 seconds'),
            (13, 'Connect time to instance server was 0ms'),
            (14, ': Added 5x Greater Black Scythe Artifact to your Expedition Locker'),
            (15, ': Added 3x Grand Black Scythe Artifact to your Expedition Locker'),
            (16, ': This Beast has been successfully added to your Bestiary.'), (17, ': 3 Items identified'),
            (18, ': (1 from Synthetic <Quest & Reward>)'), (19, ': 2 total Ascendancy Skill Points (0 allocated)'),
            (20, ': You have played for 1 hour, 2 minutes, and 3 seconds.'),
            (21, ': Your character was created 1 day, 2 hours, 3 minutes, and 4 seconds ago.'),
            (22, ': You have received +10% to all Elemental Resistances.'), (23, 'Achivement stored: Synthetic_One'),
            (24, '[MEMORY] Used=1 GB, OsUsed=3 GB, Total=4 GB'),
            (25, '[RENDER] Starting device: DirectX11'), (26, '[ENGINE] Build Revision: 101'),
            (27, '[LOADING SCREEN] (Synthetic <Map & One>) Duration = 5 seconds'),
            (28, 'Connect time to instance server was 30ms'), (29, '[RENDER] Failed to start device'),
            (30, 'Closing game gracefully'))
        return '\n' * 500 + ''.join(MapPaceTests.line(second, message, start) for second, message in rows)
