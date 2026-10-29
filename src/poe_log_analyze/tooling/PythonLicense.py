"""Find the original notice shipped with the installed CPython interpreter."""

import sys

from pathlib import Path


class PythonLicense:
    """Support upstream CPython and Debian/Ubuntu installation layouts."""

    @staticmethod
    def find(prefix: Path | None = None) -> Path:
        root = Path(sys.base_prefix) if prefix is None else prefix
        version = f"python{sys.version_info.major}.{sys.version_info.minor}"
        candidates = (root / "LICENSE.txt", root / "LICENSE",
                      root / "share/doc" / version / "copyright",
                      root / "share/doc" / (version + "-minimal") / "copyright")

        for path in candidates:
            if path.is_file():
                content = path.read_bytes()

                if not content.strip() or b"\x00" in content:
                    raise ValueError('The installed Python license is empty or contains binary data')

                return path

        raise ValueError('The installed CPython license was not found under ' + str(root))
