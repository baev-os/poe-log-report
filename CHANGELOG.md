# Changelog

## 0.1.2 (draft preparation)

- Use a shared temporary directory for Chrome checks so Unix socket paths fit
  the hosted runner's checkout path.
- Include normal desktop font configuration in the clean Linux acceptance image.
- Keep the no-Git source-copy regression portable on Windows without deleting
  read-only Git objects, and fail if the clean Linux runtime contains Python.

## Initial preparation

### Initial release preparation

- Local Path of Exile 1 log analysis with basic and extended HTML/PDF reports.
- English and Russian reports, desktop interface, and command-line entry points.
- Windows x64 and Linux x86_64 portable build preparation, distribution metadata,
  third-party license bundles, and draft release validation.
- Public release documentation, synthetic example input, and secret/privacy
  review records.

### Correctness fixes

- Keep a successful report publication successful when subsequent temporary-file
  cleanup or lock release fails.
- Hash analysis artifacts in cancellable blocks without changing stored hashes.
- Build large report conversations without argument-count limits.

No version has been published yet. Platform compatibility and available downloads
will be recorded with the first reviewed release.
