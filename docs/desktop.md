# Desktop application

## Run from source

Run `scripts/poe_desktop.py`; Python 3.14 and Tkinter/Tcl/Tk are required.
Add logs and select a time zone, language, and report types. PDFs are created
automatically for the selected types. The report period is optional.
The default log time zone is `Europe/London`, with GMT/BST selected according
to each timestamp's date. Change it if your logs use another time zone.

Processing runs in a worker thread; the GUI displays progress and an execution log.
Cancellation and errors preserve the previous result.

Logs are processed locally. The resulting HTML/PDF can repeat sensitive input,
including conversations, character names, addresses, and paths. Review it before
sharing. Bug reports and screenshots should use synthetic inputs.

## Portable application

The private v0.1.5 packages passed native builds and relocated English/Russian
self-tests on Windows Server 2022 x64 and Ubuntu 24.04 x86_64. Linux also passed
in a clean desktop runtime without Python. Windows 10/11 manual desktop
acceptance remains outstanding; no binary release has been published.
See the [validation record](public-readiness.md) and [release process](releasing.md).

Extract the entire Windows ZIP or Linux tar archive into a writable directory.
Keep the launcher beside `app/`; the executable depends on the libraries and
resources inside that directory. On Windows, start `poe-log-analyze.cmd`.
On Linux, run `./poe-log-analyze`. The portable distribution includes Python;
the user does not need to install a separate interpreter.

Successful analyses replace `report/` beside the launcher. Errors and
cancellation preserve the existing report. The application requires write
access there. Keep your own input logs outside the application directory when
replacing it with a newer release, and preserve any report you want to keep.

Check an archive against the published `SHA256SUMS` before extraction. A checksum
verifies downloaded bytes; release provenance and platform results are recorded
separately in the release notes.

## Build

To build, install `requirements-build.txt` and run `build.sh` on Linux
or `build.ps1` on Windows with MSVC x64. Move the entire
`poe_desktop.dist` directory, including `app/` and the license notices.
Check the finished distribution on its target OS; source tests do not replace this check.

The Linux release baseline is Ubuntu 24.04 x86_64 with
a pinned container image, package snapshot, and Python 3.14.4. The Windows build
uses Python 3.14.4 and MSVC x64. The workflows contain the configured build inputs;
compiler evidence records the actual toolchain versions selected on each runner.
Building on another Linux distribution can require a reviewed native-library
license catalogue and can change the minimum runtime requirements.

Only archive the finished application directory. Build commands, compiler
reports, and other files beside it are maintainer diagnostics and may contain
absolute build-machine paths. Keep those in ignored `build/`.

Project and third-party notices are available from Help > Licenses and under
`app/poe_log_analyze/resources/licenses/`. Preserve them when repackaging.
See [public-readiness.md](public-readiness.md) for outstanding distribution review.
