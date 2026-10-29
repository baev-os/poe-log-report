# Public release readiness

Status on 2026-10-29: preparation in progress. The repository has not been made
public and no binary release has been published as part of this work. This
record distinguishes completed review from outstanding release checks.

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
`a8a9ed3c8830223dc10b56e7779d1939b247b737`. The initial scan predates the release
preparation changes. Re-run it against the final commit and any newly fetched
refs before publication, and record the new scope/results. A clean scan is not a
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
One unique commit author identity is present; its values were not printed in
the audit summary. Commit identity metadata becomes visible with public history
and must also be reviewed by the maintainer.

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

The following distribution questions remain unresolved in this repository:

| Material | Inventory | Review needed before public source/binary publication |
| --- | --- | --- |
| Map artwork from the game CDN | `site/static/images/maps/`, [asset manifest](report-assets.json) | Record applicable permission for redistributing image files, or replace/remove the bundled artwork |
| Game names, identifiers, and derived area/map data | `site/data/`, [RePoE source snapshot](repoe-snapshot.json) | Review the included subset and record the distribution basis; RePoE's MIT notice does not grant additional game-material rights |
| Mercenary dialogue/greeting text | `site/data/mercenary-greetings.json`, [source manifest](mercenary-greetings.json) | Preserve Exile-UI attribution and review the underlying game dialogue scope |

No written GGG redistribution approval is recorded in the reviewed project
documents. A maintainer must resolve the intended asset scope through applicable
permission, an appropriately reviewed basis, or replacement/removal. Keep this
item open until that decision is documented; do not describe all bundled content
as MIT-licensed. Existing source URLs and hashes provide provenance, not a grant.

## Builds and publication

The planned targets are Ubuntu 24.04 x86_64 and Windows 10/11 x64. Source checks,
native compilation, archive checks, clean-target smoke tests, and native GUI
review are separate evidence. Current preparation does not establish that either
portable archive is ready for users; record actual workflow and target results
when they complete.

The release workflow prepares drafts only. Before publication, confirm:

- The final tagged commit is clean, fully scanned, and matches build provenance.
- Both native builds and their required tests pass; all skips and platform limits
  are described honestly.
- Archives contain the entire portable directory and licenses, with no local
  logs, generated reports, secret files, or build-machine diagnostics.
- Native-library and Tcl/Tk notices match the exact shipped files.
- Game-material distribution scope is resolved and documented.
- The maintainer has approved the separate visibility and release publication
  actions.

The repeatable process is in [releasing.md](releasing.md).
