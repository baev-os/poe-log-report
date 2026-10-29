# Public release readiness

Status on 2026-10-29: [private v0.1.4 draft](https://github.com/baev-os/poe-log-report/releases/tag/untagged-487ac730e2bf6ce0d203)
created after both source and native build jobs passed. The repository remains
private and no binary release has been published. Outstanding manual checks
below remain required before public distribution.

## Secret and privacy review

The initial audit used Gitleaks **8.24.3**, downloaded from the
[official release](https://github.com/gitleaks/gitleaks/releases/tag/v8.24.3).
The Linux x64 archive matched the official SHA-256 checksum:
`9991e0b2903da4c8f6122b5c3186448b927a5da4deef1fe45271c3793f4ee29c`.
The scanner and local evidence are ignored under `build/tools/` and `build/audit/`.

| Scope at the initial scan | Result |
| --- | --- |
| All locally available refs with `git --log-opts="--all --full-history"`; 2 reachable commits | Exit 0; 0 Gitleaks findings |
| Snapshot of tracked and untracked, nonignored working-tree files; 1,053 files | Exit 0; 0 Gitleaks findings |

Both scans used the built-in rules, full secret redaction, decoding depth 2,
and `--ignore-gitleaks-allow`; no finding baseline was supplied. The working-tree
snapshot excluded Git-ignored files, symlinks, and non-files. Local logs,
environments, downloaded tools, diagnostics, and generated outputs were therefore
outside that snapshot. These files must not enter a release archive.

The source revision at the start of review was
`a8a9ed3c8830223dc10b56e7779d1939b247b737`. The scan was repeated for the final
v0.1.4 build commit, `e58fad5ca46bb58e726b72dfde13a7be6e4c07f6`: all 10 locally
available refs (7 reachable commits) and 1,083 nonignored source files passed
with zero findings. The same strict settings were used. Re-scan after any
subsequent changes or newly fetched refs before publication. A clean scan is not
proof that no undiscovered secret exists.

Tracked paths and paths in the available history contained no named raw game
logs, local data inputs, credential files, databases, or generated report output
directories. `data/` contains only its README; `reports/` contains report text,
translations, and fonts, while tracked HTML files are templates.

A pattern review covered 613 unique UTF-8 text blobs reachable from the available
refs; 435 binary or non-UTF-8 blobs were excluded. It checked local-user paths,
email addresses, IPv4 candidates, and raw log timestamps. No local-user paths or
raw timestamp records were found. Reviewed candidates were synthetic test
fixtures, version strings, and third-party license author/contact attributions.
Required original notices were preserved. This is not an inspection of binary
metadata or a guarantee that every personal identifier would match a pattern.
The initial history had one unique commit author identity; its values were not
printed in the audit summary. Preparation commits use the maintainer's public
GitHub noreply identity. Commit identity metadata becomes visible with public
history and must also be reviewed by the maintainer.

Do not upload raw scan reports or local logs as public workflow artifacts.
Keep only a redacted summary of reviewed findings in the public record.

## Licenses and game materials

The project's own code has an MIT license. Dependencies, fonts, Bootstrap,
Exile-UI dialogue sources, Tcl/Tk, and Linux native libraries have separate
notices; see [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md). Bundling notices
and recording sources/hashes do not establish permission for game materials.

The primary [Grinding Gear Games terms](https://www.pathofexile.com/legal/terms-of-use-and-privacy-policy)
were reviewed on 2026-10-29. Clause 4 covers game graphics, text, names, and
virtual items. Clause 6 describes a personal, noncommercial licence. Clause 7(a)
restricts reproduction and distribution beyond that licence without prior
written approval. The gameplay video provision in clause 8 does not establish
permission for this bundled asset collection. This is a scope review, not a
legal determination.

On 2026-10-29, the maintainer decided to retain the following materials in good
faith for this fan-made, noncommercial log-analysis project. The maintainer's
reference to fair use records the project's rationale. It is not an established
legal determination, confirmation of an applicable exception, or GGG permission.
The noncommercial purpose does not change the MIT license for original code.

| Material | Inventory | Recorded inclusion purpose |
| --- | --- | --- |
| Map artwork from the game CDN | `site/static/images/maps/`, [asset manifest](report-assets.json) | Illustrate map visits in local log-analysis reports |
| Game names, identifiers, and derived area/map data | `site/data/`, [RePoE source snapshot](repoe-snapshot.json) | Recognize and label locations and events found in game logs |
| Mercenary dialogue/greeting text | `site/data/mercenary-greetings.json`, [source manifest](mercenary-greetings.json) | Recognize relevant dialogue events while preserving Exile-UI attribution |

The inclusion decision is now recorded; permission remains unconfirmed. No
written GGG redistribution approval is recorded in the reviewed project
documents. GGG retains its rights and may request removal of its materials.
The maintainer will promptly remove or replace affected materials on a request
from GGG, including in source and downloads controlled by the project, and
update the associated inventory. Existing source URLs and hashes provide
provenance, not a grant. Do not describe all bundled content as MIT-licensed.
The continuing policy is recorded in [GAME_DATA.md](../licenses/GAME_DATA.md).

## Builds and publication

### Native notice inventory

A private v0.1.4 inventory review verified archive, embedded build, license-file,
and original notice-text hashes. All nine Windows DLLs matched the compiler
report. Their bytes and all seven license-bundle files matched the independently
reviewed v0.1.3 package. No packaged code was executed during this inventory review.

The Linux package records all 42 reported native libraries: 24 Debian-package
records and 18 Pillow-wheel records. All 31 referenced native notice entries
exist; the final libraries, provenance records, and notice hashes match the
reviewed v0.1.3 package and anonymous-user compiler-report replay.

### Windows provenance follow-up

All nine copied DLLs have now been matched byte-for-byte to official CPython
3.14.4 x64 packages whose SHA-256 values match the Python release records.
Six match the official embeddable ZIP; Tcl, Tk, and `zlib1.dll` match files
extracted as data from the official installer. No upstream executable was run
during this review. The complete per-DLL mapping is in
[WindowsNative.json](../licenses/WindowsNative.json), with unchanged original
notices in [WindowsNative.txt](../licenses/WindowsNative.txt).

| DLLs | Component version | Verified binary source |
| --- | --- | --- |
| `libcrypto-3.dll`, `libssl-3.dll` | OpenSSL 3.0.19 | CPython 3.14.4 x64 embeddable ZIP |
| `zlib1.dll` | zlib 1.3.1 | CPython 3.14.4 x64 installer, Tcl/Tk component |
| `vcruntime140.dll`, `vcruntime140_1.dll` | Microsoft Visual C++ Runtime 14.42.34438.0 | CPython 3.14.4 x64 embeddable ZIP |
| `libffi-8.dll` | libffi 3.4.4 | CPython 3.14.4 x64 embeddable ZIP and pinned dependency records |
| `tcl86t.dll`, `tk86t.dll` | Tcl/Tk 8.6.15 | CPython 3.14.4 x64 installer |
| `python314.dll` | CPython 3.14.4 | CPython 3.14.4 x64 embeddable ZIP |

The source pins distinguish Tcl/Tk's zlib from CPython's separate zlib-ng.
Microsoft producer/version metadata and CPython's build sources identify the
runtime collection chain; no unverified complete Visual Studio installer
package is claimed. Original Microsoft conditions are preserved in full; see
[WINDOWS_RUNTIME.md](../licenses/WINDOWS_RUNTIME.md) for the exact source and
downstream obligations. Technical provenance does not establish compliance
with every redistribution condition or approve publication.

New Windows builds require a complete compiler report, known source paths and
hashes, and an exact match of all shipped DLLs. Packaging and relocated
verification repeat the DLL and original-notice checks. A scoped `included_dll`
summary must match across build metadata, release manifest, and verification
receipt before the draft helper clears the copied-DLL review item. This scope
does not claim a separate provenance audit of every Python extension. Older
archives without that summary retain their pending item.

### v0.1.4 native acceptance

The immutable build commit is `e58fad5ca46bb58e726b72dfde13a7be6e4c07f6`.
Both native build jobs passed in
[workflow 40838577731](https://github.com/baev-os/poe-log-report/actions/runs/40838577731).
The archives were downloaded again and matched their manifests and verification
receipts, including the exact version, tag, source commit, and archive hash.
Both archives were then downloaded from the draft itself and checked against
its combined `SHA256SUMS`; the attached metadata and three verification receipts
identify the same tag, commit, and bytes.

| Archive | Size in bytes | SHA-256 |
| --- | ---: | --- |
| `poe-log-report-0.1.4-windows-x64.zip` | 36,625,791 | `358862f7e48d879f9f43395a8bb424d01f0a4064df57a2dd2721e51917d819b7` |
| `poe-log-report-0.1.4-linux-x86_64.tar.gz` | 58,758,221 | `78fabf34458d641a9d9511f0e31c550b9afb5d4cdc058c192e8d526c480c8f4a` |

Both complete portable archives passed English and Russian compiled self-tests
after relocation into a path with spaces and Cyrillic characters and launch
from an unrelated working directory. The checks cover synthetic analysis,
HTML/PDF generation, cancellation, report replacement, and temporary cleanup.
The Windows runner was **Windows Server 2022 x64**. The Linux baseline was
**Ubuntu 24.04 x86_64**; its archive also passed both languages in the separate
Ubuntu runtime with a display and system fonts, no Python, and no development
tools. These automated checks do not establish manual Windows 10/11 desktop
acceptance or support for other Linux distributions.

### Source validation

Windows CI completed 692 unit tests with seven explicit skips and mypy for
42 source files. Four skips cover POSIX launcher/executable/symlink/tar behavior;
the remaining three require the X11 file dialog, optional native mouse input,
or a separate display of at least 1800 by 1080 pixels. These skips do not stand
in for clean client Windows 10/11 manual acceptance.

On the same build commit, Linux CI completed 692 unit tests with two skips
(native mouse input and the separate high-DPI display test), mypy for 42 source
files, and all 19 browser harnesses: 546 scenarios and 38,246 assertions. The
browser matrix uses synthetic reports across languages, themes, and viewport
sizes. The tagged Linux source scan covered all 6 CI refs, 7 reachable commits,
and 1,083 snapshot files with zero findings in both history and working tree.

The browser checks exposed and verified a fix for focused chart tooltips:
visible tooltips now follow their focused point during viewport changes while
preserving Escape dismissal. Deterministic regressions fail the previous code
and pass the fix; native mouse-input evidence was also collected locally.

The release workflow prepares drafts only. Before publication, confirm:

- The final tagged commit is clean, fully scanned, and matches build provenance.
- Both native builds and their required tests pass; all skips and platform limits
  are described honestly.
- Archives contain the entire portable directory and licenses, with no local
  logs, generated reports, secret files, or build-machine diagnostics.
- Native-library and Tcl/Tk notices match the exact shipped files.
- The recorded game-material inclusion decision, unconfirmed GGG permission,
  and removal policy remain accurate and documented.
- The maintainer has approved the separate visibility and release publication
  actions.

The repeatable process is in [releasing.md](releasing.md).
