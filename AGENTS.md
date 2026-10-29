# Development

- Read README.md, docs/architecture.md, and the affected package README.
- Check the branch and working tree; preserve other people's changes.
- Use one class per identically named file; operations are class methods.
- Preserve the boundaries of core, stages, runtime, desktop, and tooling.
- Separate meaningful actions with blank lines; place import before from.
  Put spaces around standalone =, including keyword arguments.
- Describe new composite contracts with typed dataclasses.
  Preserve existing file formats and the current architecture.
- Write documentation and comments in English; reports support en/ru.
- Use synthetic examples. Keep logs, reports, personal data, and secrets
  out of the repository. Preserve required third-party notices.
- Store temporary data and check results in build/, and the environment in .venv/.
  Set TMPDIR/TEMP/TMP within build/tmp. Limit combined work process memory
  to 8 GiB; run heavy operations sequentially.
- Run checks appropriate to the change. Update docs/handoff.md and create
  a local commit after git diff --cached --check. Push only when explicitly requested.
