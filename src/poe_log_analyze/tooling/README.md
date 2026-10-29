# Build tools

Tools for Nuitka, resource preparation, licenses, and RePoE comparison. Preserve distribution content checks and third-party notices.

`build_desktop.py --release-tag v0.1.0` requires the matching application version,
a clean worktree, and a local tag at the current commit. The source identity is
checked again after compilation. Development builds omit this option.

Linux builds use the pinned native notice catalogue by default.
`--collect-native-licenses` creates a separate catalogue in the build output from
the original notices of the installed Debian/Ubuntu packages and wheel files
identified in the compiler report. Unknown owners and wheel RECORD mismatches
fail the build. `--native-catalogue path/Native.json` reuses a verified catalogue
and its adjacent `Native.txt`; library bytes must still match exactly.
