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
The complete unit run, native builds, and remote workflow acceptance are still
in progress at this commit; record their actual results before treating the
archives as verified. Local evidence remains ignored under build/.

Clean client Windows 10/11 acceptance and the game-material distribution review
remain separate from compiler-runner checks. See [releasing.md](releasing.md)
and [public-readiness.md](public-readiness.md). Keep the repository private and
any prepared release in draft until publication is separately requested.
