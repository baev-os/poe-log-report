from poe_log_analyze.stages.reconstruction.MercenaryGreetings import MercenaryGreetings


class MapEncounterTracker:
    """Observations within a visit: NPC dialogue does not prove mechanic completion."""

    SPEAKERS = {
        'delirium': ('Strange Voice',),
        'blight': ('Sister Cassia',),
        'harvest': ('Oshabi',),
        'incursion': ('Alva, Master Explorer',),
        'bestiary': ('Einhar, Beastmaster',),
        'delve': ('Niko, Master of the Depths',),
        'betrayal': (
            'Jun, Veiled Master', 'Aisling Laffrey, The Silent Butcher',
            'Cameria the Coldblooded', "Elreon, Light's Judge", 'Gravicius Reborn',
            'Guff "Tiny" Grenn', 'Haku, Warmaster', 'Hillock, the Blacksmith',
            'It That Fled', 'Janus Perandus', 'Thane Jorgin the Banished',
            'Korell Goya, Son of Stone', 'Leo, Wolf of the Pits',
            'Riker Maloney, Midnight Tinkerer', 'Rin Yuushu', 'Tora, the Culler',
            "Vagan, Victory's Herald", 'Vorici, Silent Brother',
        ),
        'ultimatum': ('The Trialmaster',),
        'maven': ('The Maven',),
        'expedition': ('Dannig, Warrior Skald', 'Gwennen, the Gambler', 'Rog', 'Tujen, the Haggler'),
    }
    BY_SPEAKER = {speaker: code for code, speakers in SPEAKERS.items() for speaker in speakers}
    # These standalone arenas are associated with Map items in the game catalogue.
    BOSS_MAPS = ('MapAtlasShapersRealm', 'Synthesis_MapBoss')
    DISCOVERIES = {'hideout.discoverable': 'hideout', 'screen.nameless_seer': 'nameless_seer',
                   'screen.reflecting_mist': 'reflecting_mist'}

    @classmethod
    def mechanic_area(cls, area_id: str) -> bool:
        return area_id not in cls.BOSS_MAPS and area_id.startswith(('MapWorlds', 'MapAtlas', 'Synthesis_Map'))

    @classmethod
    def discover(cls, context: dict, area_id: str, row: dict) -> None:
        code = cls.DISCOVERIES.get(row['type'])

        if (not code or not cls.mechanic_area(area_id)
                or row['status'] != 'recognized' or row.get('record_id') != row['line_number']):
            return

        hideout = row['fields'].get('hideout')

        if not any(item['code'] == code and item['hideout'] == hideout for item in context['discoveries']):
            context['discoveries'].append({'code': code, 'hideout': hideout,
                                           'line': row['line_number'], 'timestamp': row.get('timestamp')})

    @classmethod
    def add(cls, visit: dict, area_id: str, row: dict) -> None:
        cls.discover(visit, area_id, row)

        if (row['type'] not in ('screen.slain', 'screen.suicide', 'dialogue.named')
                or row['status'] != 'recognized' or row.get('record_id') != row['line_number']):
            return

        event = {'line': row['line_number'], 'timestamp': row.get('timestamp')}

        if row['type'] in ('screen.slain', 'screen.suicide'):
            visit['death_messages'].append({**event, 'code': row['type'], 'character': row['fields']['character']})
        elif row['type'] == 'dialogue.named' and cls.mechanic_area(area_id):
            speaker = row['fields']['speaker']
            code = cls.BY_SPEAKER.get(speaker)

            if code and not any(item['code'] == code for item in visit['mechanics']):
                visit['mechanics'].append({**event, 'code': code})

            utterance = row['fields'].get('utterance', '')

            if (MercenaryGreetings.matches(speaker, utterance)
                    and not any(item['speaker'] == speaker for item in visit['mercenaries'])):
                visit['mercenaries'].append({**event, 'speaker': speaker, 'utterance': utterance})
