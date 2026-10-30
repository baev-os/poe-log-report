# Changelog

## 0.1.6 (in preparation)

- Default to `Europe/London` in the desktop interface, command-line analysis,
  and single-file and collection analysis services. IANA timezone rules apply
  GMT in winter and BST in summer.
- Preserve explicitly selected timezones and the timezone recorded in saved
  analyses when exporting reports.
- Align the analysis manifest's `tool_version` with the application release
  version.

## 0.1.5 (2026-10-30)

Published in the private repository; repository visibility is unchanged.

- Map all nine copied Windows DLLs to exact upstream binary hashes, component
  versions, sources, and original notices, including OpenSSL 3.0.19, Tcl/Tk's
  zlib 1.3.1, and Microsoft runtime 14.42.34438.0.
- Reject unknown or changed DLLs during notice staging, packaging, and relocated
  verification. Carry the scoped verification through release manifests and
  receipts; legacy archives retain their pending review.
- Record the maintainer's decision to include game materials in good faith and
  remove or replace them on a request from GGG. Fair use is the project's
  position; GGG permission and a legal determination are not claimed.

## 0.1.4 (private draft)

- Prepare complete Windows x64 and Linux x86_64 archives with manifests,
  checksums, and English/Russian relocated acceptance receipts. Both source
  pipelines pass; Linux also passes in a clean runtime without Python.
- Use a shared temporary directory for Chrome checks so Unix socket paths fit
  the hosted runner's checkout path.
- Include normal desktop font configuration in the clean Linux acceptance image.
- Keep the no-Git source-copy regression portable on Windows without deleting
  read-only Git objects, and fail if the clean Linux runtime contains Python.
- Resolve anonymized native-library paths from Nuitka reports before verifying
  their hashes and notices; close browser fixture logs before Windows cleanup.
- Preserve focused chart tooltips across viewport changes and record outstanding
  Windows native-dependency provenance review in draft release metadata.

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

Platform validation and remaining acceptance checks are recorded in the
[readiness record](docs/public-readiness.md).
