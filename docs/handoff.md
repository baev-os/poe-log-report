# Handoff

Report publication now keeps its successful status when temporary-file cleanup or
lock release fails after publication. Journal removal still precedes workspace
removal; unfinished publication errors retain their existing recovery behavior.

Analysis artifacts are hashed in 1 MiB blocks with cancellation checks, preserving
SHA-256 values and saved formats. Basic-report conversations append messages
individually, avoiding argument limits for large groups.

Regression coverage includes partial cleanup and restart, journal removal failure,
lock release errors, cancellation during hashing (including EOF), and a detached
browser scenario with 150,000 synthetic messages covering sorting and search.
The large browser scenario runs once within the existing basic-report matrix.

Validation: 48 targeted tests passed; mypy passed for 42 source files. The full
unit run passed (615 tests, 3 skipped because no graphical display is available).
Headless Chrome passed all 102 scenarios and 1,606 checks, including the large
conversation regression. Heavy checks ran sequentially under a shared 7 GiB
memory limit. Check logs are build/check-targeted.log, build/check-mypy.log,
build/check-unit.log, and build/check-browser/ (summary: build/check-browser.log).
Commands: [tests/README.md](../tests/README.md).

No native build was run. WindowsMemoryBudget.ps1 remains a standalone helper;
build-script integration is separate from these correctness fixes.
