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
the repository. Windows also required closing the Chrome environment fixture's
log before its temporary directory exits. The native Windows v0.1.1 archive
passed both compiled localized self-tests without skips after relocation.

The Linux CI compiler anonymizes system library paths as ~/lib under an
anonymous container UID. Native notice collection and verification now share a
validated resolver that expands the home prefix and still rejects unreadable
or relative files and changed hashes. Replaying the actual failed CI compiler
report as anonymous UID 12345 collected all 42 libraries and staged the complete
license bundle successfully without recompiling. Evidence is in
build/license-replay-v0.1.3/. Corrections move forward to v0.1.3; earlier private
tags are preserved and no release has been published. Local evidence remains
ignored under build/.

Both v0.1.3 native targets passed archived EN/RU self-tests; clean Ubuntu without
Python also passed. Windows source validation passed 692 tests (7 documented
platform/input/display skips) and mypy for 42 files. Linux unit/type checks
passed, then browser validation exposed an existing focused-tooltip defect:
scroll/resize callbacks hid a tooltip while its point remained focused.

Point tooltips now keep an actual focused owner, refresh only a visible focused
tooltip after geometry changes, and preserve Escape/explicit-change dismissal.
A WeakMap avoids retaining replaced comparison charts. Deterministic regressions
fail the old code and pass the fix, including native mouse input. Seven relevant
browser harnesses passed 76 scenarios/2296 assertions under 3 GiB. The other
12 browser harnesses also passed sequentially on the same unchanged code,
completing all 19 before the v0.1.4 release attempt.

Draft metadata explicitly retains Windows native dependency provenance review:
the bytes/notices are preserved, but OpenSSL/zlib DLL mappings and Visual C
runtime provenance require maintainer review before public distribution.

Clean client Windows 10/11 acceptance and the game-material distribution review
remain separate from compiler-runner checks. See [releasing.md](releasing.md)
and [public-readiness.md](public-readiness.md). Keep the repository private and
any prepared release in draft until publication is separately requested.
