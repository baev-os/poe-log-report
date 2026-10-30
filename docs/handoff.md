# Handoff

Unreleased source update on 2026-10-30: the desktop selector, CLI, core request,
analysis services, and composition fallbacks now default to `Europe/London`.
Timestamp dates determine GMT/BST offsets. Explicit time zones and the time zone
stored in existing analyses remain authoritative. README and desktop usage
describe the new default. Published v0.1.5 archives have not been rebuilt.
Focused analysis, CLI, collection, report, period, timeline, map, event-history,
parser, and architecture checks passed, including seasonal offsets, explicit
overrides, and export of an existing Almaty analysis. The display-dependent GUI
suite was skipped because no display was available. Mypy passed for 42 source
files. Logs remain ignored in `build/check-timezone-targeted.log`,
`build/check-timezone-composition.log`, and `build/check-timezone-mypy.log`.

The maintainer confirmed on 2026-10-30 that v0.1.5 has been published. The
repository remains private, and changing its visibility is not authorized.
README now links to the versioned release, both portable archives, and
`SHA256SUMS`, and explains extraction and startup without installing Python.
Publication status is recorded from maintainer confirmation; release attachments
were not downloaded again for this documentation update.
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
