"""Catalogue comparison using synthetic data without network access or game exports."""


class RepoeFixture:
    """Synthetic inputs and test helpers."""

    @staticmethod
    def tables():
        """Minimal catalogues with deliberately ambiguous names."""

        return {
            'world_areas.json': {key: {'name': 'Synthetic Area', 'act': 1, 'area_level': 10,
                'is_town': False, 'has_waypoint': True} for key in ('AreaA', 'AreaB')},
            'passive_skill_trees/Default.json': {'passives': {'123': {
                'id': 'skill_a', 'hash': 123, 'name': 'New Name', 'stats': {'synthetic_stat': 10}}}},
            'cluster_jewel_notables.json': [], 'cluster_jewels.json': {},
            'characters.json': [{'name': 'Synthetic Class', 'integer_id': 1}],
            'base_items.json': {}, 'uniques.json': {}, 'gems_minimal.json': [],
            'flavour.json': {'flavour_key': 'Synthetic flavour'},
            'audio.json': {'speech_key': {'text': 'First part.\r\n\r\nLast part.',
                                        'npcs': [{'name': 'Izaro', 'id': 'Metadata/NPC/Synthetic'}]}},
        }

    @staticmethod
    def row(kind, fields, **extra):
        """Create a synthetic parsed record."""

        return {'line_number': 1, 'type': kind, 'fields': fields, 'status': 'recognized', **extra}
