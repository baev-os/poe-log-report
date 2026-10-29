"""Resource names and native build requirements."""

import platform
import struct

from dataclasses import dataclass


@dataclass(frozen = True, slots = True)
class NativePlatform:
    """Supported targets: Linux and Windows with 64-bit Python on x86_64."""

    system: str
    machine: str
    bits: int

    def __post_init__(self) -> None:
        if self.system not in ("Linux", "Windows") or self.machine.lower() not in ("x86_64", "amd64") or self.bits != 64:
            raise RuntimeError('Linux or Windows x86_64 with 64-bit Python is required')

    @staticmethod
    def current() -> "NativePlatform":
        return NativePlatform(platform.system(), platform.machine(), struct.calcsize("P") * 8)

    @property
    def windows(self) -> bool:
        return self.system == "Windows"

    @property
    def application_name(self) -> str:
        return "poe-log-analyze.exe" if self.windows else "poe-log-analyze"
