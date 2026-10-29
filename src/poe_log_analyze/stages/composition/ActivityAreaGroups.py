import re

from poe_log_analyze.runtime.GameAreaCatalogue import GameAreaCatalogue


class ActivityAreaGroups:
    """Disjoint groups and subareas identified by game catalogue IDs."""

    SUBGROUPS = {
        'deepwater': ('sovereign', 'fathomless'),
        'keepers': ('keepers',),
        'harbour': ('harbour',),
        'heist': ('heist',),
        'expedition': ('expedition',),
        'betrayal': ('betrayal',),
        'incursion': ('incursion',),
        'legion': ('legion',),
        'kingsmarch': ('kingsmarch',),
        'sanctum': ('sanctum',),
        'delve': ('mine_encampment', 'azurite_mine', 'delve_depths'),
        'menagerie': ('menagerie',),
        'labyrinth': ('aspirants_plaza', 'labyrinth_rooms'),
        'hideout': ('hideout',),
        'acts': ('acts',),
        'maps': ('maps',),
        'bosses': ('bosses',),
    }
    CODES = tuple(SUBGROUPS)
    COLORS = ('#5bbf9e', '#cfaa78', '#829fef', '#cba56d', '#d29b77', '#aabf91',
              '#7ac1b9', '#ae9fd2', '#e794c0', '#c395ef', '#52b8d0',
              '#a6be64', '#e6bc56', '#94b6c1', '#e58f72', '#70b5ee', '#e47783')
    BOSS_IDS = ('MavenBoss', 'MavenHub', 'MapAtlasShapersRealm', 'MapAtziri1', 'MapAtziri2',
                'Synthesis_Boss', 'Synthesis_MapBoss', 'BetrayalMastermindFight',
                'HarvestLeagueBoss', 'AzmeriLeagueBoss', 'FaridunLeagueBoss',
                'ChayulaLeagueTowerBoss', 'UltimatumBossArena')
    BOSS_PREFIXES = ('AtlasExilesBoss', 'BreachBoss', 'BestiaryLeague_', 'SettlersBoss',
                     'HeistBoss_', 'ExpeditionArena', 'AbyssLeagueBoss')

    @staticmethod
    def classify(area_id: str) -> str | None:
        subgroup = ActivityAreaGroups.subgroup(area_id)

        for code, children in ActivityAreaGroups.SUBGROUPS.items():
            if subgroup in children:
                return code

        return None

    @staticmethod
    def subgroup(area_id: str) -> str | None:
        area = GameAreaCatalogue.areas().get(area_id)

        if area is None:
            return None

        if area_id in ('Delve_Hub', 'Delve_Endless'):
            return 'mine_encampment'

        if area_id in ('Delve_Main', 'Delve_Empty') or re.fullmatch(r'Delve_Mines[2-8]?', area_id):
            return 'azurite_mine'

        if area_id.startswith('Delve'):
            return 'delve_depths'

        if area_id.startswith('Sanctum'):
            return 'sanctum'

        if area_id in ('Labyrinth_Airlock', '1_Labyrinth_AirlockClean'):
            return 'aspirants_plaza'

        if re.match(r'^(?:[123]|EndGame)_Labyrinth_', area_id) or area_id.startswith('Labyrinth_'):
            return 'labyrinth_rooms'

        if area_id == 'DeepwaterHub':
            return 'sovereign'

        if area_id.startswith('Deepwater') and 'Filming' not in area_id:
            return 'fathomless'

        if area_id == 'ChayulaLeague':
            return 'keepers'

        if re.match(r'^(?:1_[1-5]|2_(?:[6-9]|10))_', area_id):
            return 'acts'

        if area_id.startswith('Menagerie_'):
            return 'menagerie'

        if area_id == 'KalguuranSettlersLeague':
            return 'kingsmarch'

        if area_id in ('HeistHub', 'HeistHubEndless'):
            return 'harbour'

        if area_id.startswith('Hideout'):
            return 'hideout'

        if (area['kind'] == 'Арена' or area_id in ActivityAreaGroups.BOSS_IDS
                or area_id.startswith(ActivityAreaGroups.BOSS_PREFIXES)):
            return 'bosses'

        if re.fullmatch(r'Heist(?:Bunker|Courts|Dungeon|Library|Mansion|Mines|Reliquary|RobotTunnels|Sewers)\d+_?', area_id):
            return 'heist'

        if area_id.startswith('Expedition'):
            return 'expedition'

        if area_id.startswith('BetrayalSafeHouse'):
            return 'betrayal'

        if re.fullmatch(r'Incursion_Temple\d+_?', area_id):
            return 'incursion'

        if re.fullmatch(r'LegionLeague\d*', area_id):
            return 'legion'

        if area_id.startswith(('MapWorlds', 'MapAtlas', 'Synthesis_Map')) and area['kind'] == 'Карта':
            return 'maps'

        return None
