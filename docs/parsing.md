# Line parsing

A typical record is `YYYY/MM/DD HH:MM:SS tick source [LEVEL Client PID] message`.
Log opening markers, blank lines, and message continuations are supported.
Time is interpreted in the explicitly selected time zone.

The parser preserves bytes, coordinates, status, rule code, and captured fields.
Unknown messages, UTF-8 errors, and time errors are tracked separately.
A saved analysis contains JSONL, summaries, and manifests with checksums.
[Rule reference](rules.md).
