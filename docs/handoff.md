# Handoff

Release preparation now has source checks, secret scans, and draft-only GitHub
Actions workflows. Both target builds use one resolved source SHA; ordinary
pull requests have read-only repository access. No workflow publishes a release
or changes repository visibility.

Release builds require a clean checkout, an exact version tag, and matching
provenance before and after compilation and packaging. Build metadata records
the application version and optional container image identity. Python notice
discovery supports upstream and Debian layouts; Linux can collect a separate
native notice catalogue from actual package ownership and library hashes while
preserving the original pinned catalogue and strict verification.

Portable packaging keeps the complete application directory and validates
paths, resources, licenses, identity, and file hashes. Archived applications are
checked after relocation to a Unicode path in English and Russian. Windows
child checks use the system command interpreter and exclude developer tools
from PATH. The draft helper requires both verified targets and never overwrites
an existing release. The pinned Ubuntu 24.04 runtime check contains no Python.

Local preparation checks: 60 targeted tests passed, mypy passed for 42 source
files, workflow lint passed with verified actionlint 1.7.12, and pinned Gitleaks
8.24.3 reported no findings across available history and nonignored sources.
The local full run passed 615 tests (three GUI display skips). The first Linux
CI run passed 687 unit tests with a display and mypy for 42 files. Browser checks
then exposed Chromium's Unix socket path limit on the hosted checkout; all
browser launch paths now share build/tmp and reject overly deep paths clearly.
The complete browser matrix and remote workflow acceptance remain in progress.

The native Linux v0.1.0 build succeeded, collected notices for 42 libraries,
and its relocated 57 MiB archive passed both localized self-tests. The minimal
runtime image required Fontconfig and system fonts, now included to represent
a desktop environment while keeping Python and development tools absent.
All 19 local browser scripts passed after the socket fix under a shared 3 GiB
limit. The first Windows source run found one fixture error among 687 tests:
the source-copy check deleted read-only Git objects. It now creates a nested
source copy, preserving the ancestor-Git isolation assertion without deleting
the repository. Corrections move forward to v0.1.2; earlier private tags are
preserved and no release has been published. Local evidence remains ignored
under build/.

Clean client Windows 10/11 acceptance and the game-material distribution review
remain separate from compiler-runner checks. See [releasing.md](releasing.md)
and [public-readiness.md](public-readiness.md). Keep the repository private and
any prepared release in draft until publication is separately requested.
