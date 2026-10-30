# Handoff

Privacy audit on 2026-10-30 covered source commit
`f30aab9f797cf62760fbca7fd72dd107dafe7546`: 12 refs, 14 reachable commits,
1,203 Git blobs, and 1,088 current source files. The 38 local unreachable blobs
and one unreachable commit were also reviewed; that commit was not retrievable
through the GitHub API. Commit identities use GitHub noreply addresses.

The GitHub audit covered all three releases and 17 current assets, all 15
workflow log archives, all 46 Actions artifacts, and nine distinct application
archives, including earlier Actions-only builds. Application inspection covered
20,375 member locations and 150 native binaries. All bundled original-notice
archives were verified. Repository metadata, comments, variables, environments,
deployments, webhooks, deploy keys, forks, and Actions caches were checked.

No confirmed secret or private maintainer-data exposure was found in repository
or GitHub content; no unresolved candidates remain. Gitleaks 8.24.3 found zero
history/source findings. All 95 extended content-scan candidates were proven
SHA-256 integrity values. A separate sensitive `temp_clone_token` field came
from the authenticated GitHub metadata API response and was captured only in
the protected local audit snapshot. It was replaced with null; a residual-copy
check and repeat scan passed. The local collector now strips the field before
saving. No token values were printed, tested against providers, or committed.

Expected matches were public GitHub identities, required third-party contacts,
synthetic fixtures, generic CI/compiler paths, a public upstream metadata path
example, and Pillow font data. Image checks covered metadata, hashes, fixture
provenance, and visual review of the source screenshot; OCR and steganography
were outside scope. GitHub Secret Scanning alerts were unavailable through the
API (HTTP 404). Ignored local environments and personal inputs were excluded
from the publishable-source audit. Static checks do not prove the absence of
every possible encoded identifier.

GitHub content and settings were not changed; the repository was confirmed
private. All detailed evidence remains ignored and access-restricted under
`build/privacy-audit-20261030/`; `summary.json` contains the sanitized result and
links to per-finding proofs. Do not publish the raw audit snapshots.

Version [v0.1.6](https://github.com/baev-os/poe-log-report/releases/tag/v0.1.6)
was published on 2026-10-30 after the maintainer requested the release. The
repository was confirmed private before and after publication; its visibility
must remain private. Tag `v0.1.6` identifies
`3d5719041a78e6818b6ccade11714150328de16c`. The application and analysis
manifest versions both read 0.1.6.

[Workflow 40977605249](https://github.com/baev-os/poe-log-report/actions/runs/40977605249)
passed both native builds and both complete source jobs. Each OS completed 717
unit tests (two Linux skips, seven Windows skips) and mypy for 42 files. All 19
Linux browser harnesses passed: 546 scenarios and 38,246 assertions. CI scanned
eight refs, 13 reachable commits, and 1,088 source files with zero findings.
Both archives passed relocated English/Russian GUI self-tests; Linux also passed
in the clean runtime without Python. Manual clean Windows 10/11 acceptance
remains outstanding.

All 11 attachments were downloaded from the draft and verified against GitHub
asset digests, archive manifests, verification receipts, and the combined
`SHA256SUMS`. Publication notes describe the changed default and actual platform
results; `RELEASE_METADATA.json` records the published state. The downloaded
Linux binary independently confirmed winter/summer offsets, explicit Almaty
selection, and analysis version 0.1.6 from an unrelated working directory.
Exact archive hashes and platform limitations are in
[public-readiness.md](public-readiness.md). Local evidence remains under
`build/release-v016-assets/`, `build/release-v016-downloads/`,
`build/release-v016-checks/`, and `build/check-v016-compiled-london.json`.
Documentation checks confirmed 34 local link targets and all four README release
links against the published version and asset names; evidence is in
`build/check-v016-doc-links.json`.

Local release preparation passed 48 version, packaging, draft, and analysis
tests. Gitleaks 8.24.3 found no findings in the available history or the 1,088-file
source snapshot. Evidence remains in ignored `build/check-v016-release-preparation.log`
and `build/audit-v016-preparation/results.json`.

In v0.1.6, the desktop selector, CLI, core request, analysis services, and
composition fallbacks default to `Europe/London`.
Timestamp dates determine GMT/BST offsets. Explicit time zones and the time zone
stored in existing analyses remain authoritative. README and desktop usage
describe the new default.
Local focused analysis, CLI, collection, report, period, timeline, map,
event-history, parser, and architecture checks passed, including seasonal offsets, explicit
overrides, and export of an existing Almaty analysis. The display-dependent GUI
suite was skipped locally because no display was available. Mypy passed for
42 source files. Logs remain ignored in `build/check-timezone-targeted.log`,
`build/check-timezone-composition.log`, and `build/check-timezone-mypy.log`.

The maintainer confirmed on 2026-10-30 that v0.1.5 has been published. The
repository remains private, and changing its visibility is not authorized.
The v0.1.5 README update linked its release, both portable archives, and
`SHA256SUMS`, and explained extraction and startup without installing Python.
That update recorded publication from maintainer confirmation; its release
attachments were not downloaded again for that documentation update.
Documentation validation passed for 16 local link targets and four versioned
release URLs matching the project version. Whitespace checks passed; local
evidence is in the ignored build/check-readme-links.json file.

Version v0.1.5 uses tag `v0.1.5` at
`495194643e901af310ab1c3a05a6c09fa6bbece1`. Both native archive jobs passed in
[workflow 40849045733](https://github.com/baev-os/poe-log-report/actions/runs/40849045733).
The complete workflow passed, including both source jobs and creation of the
initial draft for [v0.1.5](https://github.com/baev-os/poe-log-report/releases/tag/v0.1.5).
The draft's downloaded attachments passed the combined `SHA256SUMS`; metadata
and verification receipts identified the same source and archive bytes.

All nine copied Windows DLLs match official CPython 3.14.4 x64 binary packages.
The checked catalogue is `licenses/WindowsNative.json` and its original-notice
archive. It records exact file hashes, versions, source pins, reference package
hashes, and notice mappings, including OpenSSL 3.0.19, Tcl/Tk's zlib 1.3.1, and
Microsoft runtime 14.42.34438.0. Official installer contents were read as data;
no upstream executable was run during the provenance review.

Windows staging requires a complete standalone compiler report, known Python
source paths and hashes, an exact shipped DLL inventory, and original notices.
Packaging and relocated verification recheck the shipped bytes and notice
archive. An identical scoped `included_dll` summary passes through build
metadata, license metadata, release manifest, and verification receipt before
the draft helper clears the copied-DLL review item. Legacy archives without
that evidence keep their pending item; the scope does not claim a separate
audit of every Python extension.

The downloaded Windows archive passed independent validation of the complete
chain: nine DLLs, 35 original notice entries, seven new native entries with exact
original bytes, and eight license-folder files including the manifest and
`WINDOWS_RUNTIME.md`. Original Microsoft conditions and downstream obligations
remain separate from technical verification; see
[WINDOWS_RUNTIME.md](../licenses/WINDOWS_RUNTIME.md).

The maintainer decided to include game materials in good faith and remove or
replace affected materials in source and downloads on GGG's request. Fair use
records the project's rationale; GGG permission and a legal determination are
not claimed. The policy is in [GAME_DATA.md](../licenses/GAME_DATA.md), appears
verbatim in both archives, and is recorded separately in draft metadata.

Both complete portable archives passed relocated English/Russian compiled
self-tests from an unrelated working directory. The Ubuntu 24.04 archive also
passed in a separate desktop runtime without Python or development tools.
Windows runner evidence is for Server 2022; clean Windows 10/11 client desktop
acceptance remains outstanding. Archive sizes and hashes are recorded in
[public-readiness.md](public-readiness.md).

Local preparation passed 77 focused notice/build/release/architecture tests.
Final source CI passed 714 tests on each OS (seven Windows and two Linux
platform/input/display skips), mypy for 42 files on each target, and all
19 browser harnesses: 546 scenarios and 38,246 assertions. The tagged CI secret
scan covered seven refs, nine reachable commits, and 1,088 source files with
zero findings in history and working tree. Exact skip coverage is recorded in
[public-readiness.md](public-readiness.md).

Real Windows compiler-report replay with all nine independently verified DLLs
passed source/shipped-file and original-notice checks; modified input or shipped
DLLs, missing notices, and unexpected libraries were rejected. An independent
code review covered Windows path handling, pre/post-arrange layouts, dependency
staging, full summary consistency, and legacy behavior. Gitleaks 8.24.3 reported
zero findings across available history and 1,088 source snapshot files. The scan
was repeated after the final documentation-only acceptance update.

The workflows resolve one immutable source SHA. Ordinary checks have read-only
repository access. Only the final draft job has release-write permission, with
no overwrite or publish path. Build provenance is checked before and after
compilation and packaging. Keep the repository private. Future releases remain
in draft until publication is separately requested. See [releasing.md](releasing.md).
Local evidence stays ignored under `build/`.
