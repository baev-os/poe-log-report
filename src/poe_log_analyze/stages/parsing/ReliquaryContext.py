from poe_log_analyze.stages.parsing.RuleCatalogue import RuleCatalogue


class ReliquaryContext:
    """One chest message after confirmed generation, entry, and loading."""

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.area = None
        self.pid = None
        self.scene = False
        self.entered = False
        self.loaded = False
        self.last_tick = None

    def prepare(self, header) -> None:
        tick = int(header['tick'])

        if self.pid != header['pid'] or self.last_tick is not None and tick < self.last_tick:
            self.reset()

        self.pid = header['pid']
        self.last_tick = tick

    def accepts(self, header) -> bool:
        return self.loaded and header['level'] == 'INFO'

    def observe(self, record: dict) -> None:
        if record['status'] != 'recognized':
            self.reset()
            return

        kind, fields = record['type'], record['fields']

        if kind == 'area.generate':
            self.area = RuleCatalogue.RELIQUARY_AREAS.get(fields['area'])
            self.scene = self.entered = self.loaded = False
        elif kind == 'scene.source':
            self.scene = bool(self.area and fields['source'] == self.area)

            if not self.scene and (self.entered or fields['source'] != '(null)'):
                self.reset()
        elif kind == 'area.enter':
            self.entered = bool(self.scene and fields['area'] == self.area)
            self.loaded = False

            if not self.entered:
                self.reset()
        elif kind == 'loading.duration':
            self.loaded = bool(self.entered and fields['area'] == self.area)

            if not self.loaded:
                self.reset()
        elif kind in ('reliquary.message', 'log.open', 'game.closing', 'network.instance_connect') or kind.startswith('network.') and 'disconnect' in kind:
            self.reset()
