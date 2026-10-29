"""Nonblocking interprocess lock for the single current report."""

import os

from pathlib import Path


class ReportLock:
    """The operating system releases the lock even if the application crashes."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.descriptor: int | None = None

    def acquire(self) -> None:
        if self.path.is_symlink():
            raise ValueError('The lock file must not be a symbolic link')

        descriptor = None

        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
                                 | getattr(os, "O_TEMPORARY", 0), 0o600)

            if os.name == "nt":
                import msvcrt

                if os.fstat(descriptor).st_size == 0:
                    os.write(descriptor, b"0")

                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)

            if not os.path.samestat(os.fstat(descriptor), self.path.stat()):
                raise RuntimeError('Another run is releasing the report workspace; retry analysis')
        except OSError as error:
            if descriptor is not None:
                os.close(descriptor)

            raise RuntimeError('Another application run is already generating a report') from error
        except BaseException:
            if descriptor is not None:
                os.close(descriptor)

            raise

        self.descriptor = descriptor

    def release(self) -> None:
        if self.descriptor is not None:
            try:
                # Windows O_TEMPORARY removes the file after its handles are closed.
                if os.name != "nt":
                    self.path.unlink(missing_ok = True)
            finally:
                os.close(self.descriptor)
                self.descriptor = None
