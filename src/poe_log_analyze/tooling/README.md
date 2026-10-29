# Build tools

Tools for Nuitka, resource preparation, licenses, and RePoE comparison. Preserve distribution content checks and third-party notices.

`build_desktop.py --release-tag v0.1.5` requires the matching application version,
a clean worktree, and a local tag at the current commit. The source identity is
checked again after compilation. Development builds omit this option.

Linux builds use the pinned native notice catalogue by default.
`--collect-native-licenses` creates a separate catalogue in the build output from
the original notices of the installed Debian/Ubuntu packages and wheel files
identified in the compiler report. Unknown owners and wheel RECORD mismatches
fail the build. `--native-catalogue path/Native.json` reuses a verified catalogue
and its adjacent `Native.txt`; library bytes must still match exactly.

Windows builds use `licenses/WindowsNative.json` and its original-notice archive.
Every copied DLL in a completed compiler report must match the reviewed Python
source path and SHA-256, and the shipped DLL inventory must match exactly.
Packaging and relocated verification repeat the shipped-file and notice checks.
The scoped `included_dll` result passes through build metadata, release manifests,
and verification receipts; unknown versions require a catalogue review.
