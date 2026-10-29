class AnalyticsNavigation:
    """Shared allowlist of pages for rendering, navigation, and inventory verification."""

    PAGES = ('rhythm', 'mechanics', 'trading', 'consistency', 'recovery',
             'cycles', 'focus', 'remaining', 'returns', 'session_edges', 'obstacles', 'marker_intervals',
             'network', 'passives', 'marker_timing', 'routes', 'trade_api', 'level_progress', 'presence',
             'memory', 'startup', 'environment', 'acquisitions', 'milestones', 'coverage',
             'pool', 'marker_order', 'fault_intervals', 'filters')

    @classmethod
    def build(cls) -> dict:
        return {'version': '1', 'pages': [{'id': name, 'path': f'analytics/{name}/index.html',
                                          'label_key': 'analytics.' + name} for name in cls.PAGES]}
