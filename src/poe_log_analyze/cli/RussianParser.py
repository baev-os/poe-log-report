import argparse

class RussianParser(argparse.ArgumentParser):
    """Present argument errors with a readable explanation."""

    def error(self, message: str) -> None:
        self.exit(2, 'Invalid arguments. Check the options with --help.\n')
