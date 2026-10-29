class ReportPalette:
    """Shared palette for print documents and the large area image."""

    def __init__(self, dark = False):
        self.dark = dark
        self.background = '#131d27' if dark else '#ffffff'
        self.surface = '#1e2c39' if dark else '#eef3f5'
        self.ink = '#e4edf3' if dark else '#243947'
        self.muted = '#a6bac9' if dark else '#526675'
        self.grid = '#3c5263' if dark else '#dce4e8'
        self.accent = '#6ed4e0' if dark else '#24788b'
        self.header = '#245d70'

    def replace(self, value):
        if not self.dark:
            return value

        return {'#ffffff': self.background, '#f7fafc': self.background,
                '#eef3f5': self.surface, '#243947': self.ink, '#203744': self.ink,
                '#18596b': self.accent, '#24788b': self.accent, '#526675': self.muted,
                '#dce4e8': self.grid, '#d6e0e6': self.grid, '#aa4455': '#f08b9c'}.get(value.lower(), value)

    def blend(self, color, opacity):
        foreground = [int(color[index:index + 2], 16) for index in (1, 3, 5)]
        background = [int(self.surface[index:index + 2], 16) for index in (1, 3, 5)]
        return '#' + ''.join(f'{round(back + (front - back) * opacity):02x}' for front, back in zip(foreground, background))
