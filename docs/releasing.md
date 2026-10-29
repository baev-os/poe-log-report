# Release process

This process prepares reviewed **draft** releases. Making the repository public
and publishing a release are separate maintainer actions. Neither is part of an
automatic build. The first release is still in preparation; platform results
are recorded in [public-readiness.md](public-readiness.md).

## Build targets

| Target | Proposed baseline | Required validation |
| --- | --- | --- |
| Linux x86_64 | Ubuntu 24.04, pinned container and package snapshot, Python 3.14.4 | Native build and analysis on a clean Ubuntu 24.04 runtime without a separately installed Python |
| Windows x64 | Python 3.14 and MSVC x64 | Native build and analysis on Windows; verify Windows 10/11 support before claiming it |

The Linux baseline does not imply support for older glibc versions or other
distributions. Record any additional tested platforms in the release notes.

## Workflows

`.github/workflows/checks.yml` runs source checks for pushes and pull requests,
and exposes the same checks through `workflow_call`. Synthetic fixtures are
used throughout. GUI and browser checks must have the runtime services they
require; a skipped check must remain visible in the result.

`.github/workflows/release.yml` accepts `v*` tag pushes and a manual
`workflow_dispatch` with a tag input. It builds the selected revision for both
targets, validates the packages, creates checksums, and prepares a GitHub draft
release. Check the workflow files for exact permissions and pinned inputs.
Successful workflow completion does not approve publication or settle the
outstanding rights review.

## Prepare the source

1. Resolve the outstanding items in [public-readiness.md](public-readiness.md),
   especially game-material distribution scope and private-data review.
2. Choose a version, update `pyproject.toml` and `CHANGELOG.md`, and finish the
   release notes. Describe known limitations and the platforms actually tested.
3. Run the source checks from [tests/README.md](../tests/README.md). Run native
   builds and package checks for both targets. Save diagnostics only in `build/`.
4. Scan all available Git refs and the final working tree for secrets. Review
   personal data and commit author identities before changing repository
   visibility. Re-scan after any fixes or newly fetched history.
5. Commit the reviewed changes and tag the clean commit as `v<version>` only
   when release preparation is authorized. The tag must match the project
   version. A release build must record that commit SHA and a clean Git state.

Do not build distributable binaries from an unknown SHA or a dirty checkout.
Do not rewrite public or shared history as a routine release step; coordinate
any necessary removal separately.

## Build Linux in the pinned environment

On Linux x86_64, install Docker and check out the clean version tag. The helper
builds the Ubuntu 24.04 toolchain image, compiles the application, packages it,
and runs the extracted archive in English and Russian:

```bash
./scripts/build_linux.sh --release-tag v0.1.0 --output build/linux-v0.1.0
```

Replace the example with the actual tag. The output directory must be new and
inside `build/`. A local Python installation or virtual environment is not
required. The helper uses BuildKit when available and falls back to the classic
Docker builder when the local Docker installation has no buildx plugin.

The build image is pinned by the Ubuntu image digest, the configured Ubuntu
package snapshot, the CPython source SHA-256, and dependency versions in the
requirements files. Its image ID is recorded as `source_image` in the application
metadata. The compilation container has no network access, uses at most 7 GiB
of memory, and receives the source read-only with only `build/` writable.
Original native-library notices are collected from the actual installed
packages into the build output and verified again when bundled. This leaves
the repository's pinned notice catalogue intact.

The output contains `native/` build evidence and `release/` archives, manifests,
checksums, and verification logs. For a separate check on Ubuntu 24.04 without
Python or the build tools, use the clean runtime image with those exact assets:

```bash
docker build -f scripts/linux/Runtime.Dockerfile -t poe-log-report-runtime:24.04 .
mkdir -p build/clean-runtime
docker run --rm --init --memory=7g --memory-swap=7g --network=none \
  --user "$(id -u):$(id -g)" \
  -v "$PWD/build/linux-v0.1.0/release:/assets:ro" \
  -v "$PWD/build/clean-runtime:/release" \
  -e TMPDIR=/release/tmp -e TEMP=/release/tmp -e TMP=/release/tmp \
  poe-log-report-runtime:24.04 sh -eu -c '
    ! command -v python
    ! command -v python3
    mkdir -p /release/tmp
    tar -xzf /assets/poe-log-report-0.1.0-linux-x86_64.tar.gz -C /release
    app=/release/poe-log-report-0.1.0-linux-x86_64
    xvfb-run -a "$app/poe-log-analyze" --self-test "$app/build/clean-en" --report-language en
    xvfb-run -a "$app/poe-log-analyze" --self-test "$app/build/clean-ru" --report-language ru
  '
```

Use the actual version and a fresh runtime output directory. When using a Docker
installation without buildx, prefix the image-build command with
`DOCKER_BUILDKIT=0`. Retain both `self-test.json` files as clean-runtime evidence.

## Review the packages

Package the whole `poe_desktop.dist` directory: the outer launcher and README,
`app/`, shared libraries, templates, assets, fonts, time zones, build metadata,
and license notices. Use a ZIP on Windows and tar archive on Linux so the Linux
launcher retains its executable permission. Publish SHA-256 checksums for the
final archives as `SHA256SUMS`.

After a native build, the packaging command on Linux is:

```bash
.venv/bin/python scripts/package_release.py \
  --distribution build/standalone/poe_desktop.dist \
  --output build/release --tag v0.1.0 --commit FULL_COMMIT_SHA --verify
```

On Windows, use `.\.venv\Scripts\python.exe` and PowerShell line continuation,
or put the arguments on one line. Replace the example tag and SHA with the
reviewed version and full commit. Use a fresh output directory.

The naming convention is `poe-log-report-<version>-linux-x86_64.tar.gz` and
`poe-log-report-<version>-windows-x64.zip`. Each archive has a corresponding
`.json` manifest and `.sha256` file; `SHA256SUMS` contains the archive checksums.
`--verify` extracts and runs the packaged application in both report languages;
its logs and `verification.json` are retained under `build/release/verification/`.
To recheck a downloaded archive on its target OS, run
`scripts/verify_release.py --archive PATH --manifest PATH --output build/verify`
with the source tooling environment. Keep all verification evidence in `build/`.

Do not package the repository, `.git`, local inputs, generated reports, virtual
environments, caches, compiler reports, or the rest of `build/`. Inspect archive
members and extracted contents. Reject unexpected files, absolute paths,
traversal paths, external symlinks, and missing runtime resources. Verify the archived
files against the distribution manifest and repeat checks after extraction.

The license bundle must describe the actual shipped dependencies. Linux native
library changes require review of the catalogue and original notices. Windows
Tcl/Tk notices must match the installed toolkit version. Preserve full original
notices and review the builder's `pending_release_checks` explicitly.

On a clean supported target, extract the archive into a path containing spaces
and non-ASCII characters, then launch from a different current directory. Use
synthetic logs to generate both basic and extended reports in English and
Russian; check HTML and PDFs, navigation, and Help > Licenses. Verify failure and
cancellation preserve an existing report. Test the user-facing GUI as well as
the noninteractive smoke check. A headless check does not establish that the
native desktop opens and behaves correctly.

For a clean runtime without source Python tooling, the extracted launcher also
accepts `--self-test build/self-test-en --report-language en`; repeat with a fresh
output path and `--report-language ru`. This built-in synthetic smoke check
exercises the shipped runtime and report resources. It does not replace the
manual desktop checks above.

Record OS/version, architecture, build SHA, archive hashes, commands, passed and
skipped checks, and any unresolved issue. In particular, a Windows runner's OS
does not by itself verify Windows 10 compatibility.

## Review the draft

Download both archives from the draft and verify `SHA256SUMS` against those
downloaded bytes. Confirm the release tag, build metadata, checks, full license
bundle, and release notes agree. Read the notes as a new user: they must name
only available assets and tested platforms.

Keep the release in draft until the maintainer has explicitly approved its
publication and resolved the documented distribution scope. Repository
visibility must be changed separately only when approved. Do not infer approval
from successful CI, an existing tag, or a completed checklist.
