# Handoff

Private release preparation uses tag `v0.1.4` at
`e58fad5ca46bb58e726b72dfde13a7be6e4c07f6`. Both native archive jobs passed in
[workflow 40838577731](https://github.com/baev-os/poe-log-report/actions/runs/40838577731),
which completed successfully, including both source jobs and draft creation.
The [private draft](https://github.com/baev-os/poe-log-report/releases/tag/untagged-487ac730e2bf6ce0d203)
contains both archives, manifests, checksums, provenance, and verification receipts.
The downloaded draft assets pass `SHA256SUMS`. Repository visibility remains
private; no release has been published.

The workflows resolve one immutable SHA for source checks and both builds.
Ordinary checks have read-only repository access. Only the final draft job has
release-write permission, and it cannot publish or overwrite a release.
Builds require a clean checkout and matching version/tag before and after
compilation and packaging. Embedded metadata and archive manifests retain that
identity. Full native build evidence stays separate from release assets.

Portable packages contain the outer launcher and complete application directory,
including resources, libraries, and original license notices. Packaging rejects
unsafe paths, external symlinks, development inputs, and mismatched hashes.
Both archives passed relocated compiled English/Russian self-tests from an
unrelated working directory. The Windows child checks remove developer tools
from PATH. The Ubuntu 24.04 archive also passed in a separate desktop runtime
without Python or development tools. Windows runner evidence is for Server 2022;
clean Windows 10/11 client desktop acceptance remains outstanding.

Linux source CI completed 692 unit tests with two platform/display skips, mypy
for 42 files, and all 19 browser harnesses (546 scenarios, 38,246 assertions).
Windows source CI completed 692 tests with seven explicit POSIX/input/display
skips and mypy for 42 files. The readiness record lists the skipped coverage.
Local final preparation also passed 65 focused release/architecture tests,
both mypy platform profiles, and workflow lint with verified actionlint 1.7.12.
All 19 browser harnesses passed locally under a shared 3 GiB limit. Gitleaks
8.24.3 reported zero findings across the tagged history and nonignored source
snapshot and was repeated after the final documentation update; detailed
redacted scope and hashes are in
[public-readiness.md](public-readiness.md).

Native notice collection validates actual Debian package ownership or exact
wheel RECORD hashes and stages original notices. Anonymous Linux compiler
paths using `~/lib` share one validated home-expanding resolver with catalogue
verification. Actual CI-report replay as an anonymous UID verified all 42
libraries without recompilation. The final archives preserve the reviewed
Windows nine-DLL and Linux 42-library inventories and all notice hashes.
Windows OpenSSL/zlib source-to-notice mappings and exact Visual C runtime
provenance remain a manual publication review item.

Cross-platform fixture fixes keep Chrome sockets in short temporary paths,
close browser logs before Windows cleanup, and isolate no-Git source copies
without deleting read-only Git objects. The clean Linux display includes
Fontconfig and system fonts while explicitly rejecting installed Python.

Chart point tooltips retain their actual focused owner across scroll/resize,
refresh only an already-visible focused tooltip, and preserve Escape and
explicit-change dismissal. A WeakMap avoids retaining replaced comparison
charts. Deterministic regressions fail the old code and pass the fix, including
separate native mouse-input evidence. Seven focused browser harnesses passed
76 scenarios and 2,296 assertions before the complete local and CI matrix.

The game-material distribution scope, Windows native provenance review, and
clean client Windows 10/11 acceptance remain explicit manual checks. See
[releasing.md](releasing.md) and [public-readiness.md](public-readiness.md).
The repository must stay private and the release must stay in draft until
publication is separately requested. Earlier private tags were preserved;
no shared tag or history was rewritten. Local evidence stays ignored in `build/`.
