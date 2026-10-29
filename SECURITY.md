# Security and privacy

## Report a vulnerability

Use GitHub's [private vulnerability reporting](https://github.com/baev-os/poe-log-report/security/advisories/new)
when it is available. Include the affected commit or release, operating system,
expected behavior, and a minimal synthetic reproduction.

Do not put passwords, access tokens, raw game logs, or personal conversations in
a public issue. If private reporting is unavailable, open an issue requesting a
private contact channel without including vulnerability details or sensitive
attachments. A response time is not guaranteed.

## Supported versions

The project is preparing its first release. There are no supported published
binary versions yet. Fixes are developed on `main`; release support will be
stated when a version is published.

## Sharing inputs and reports

The application runs locally and report generation does not require a network
server. Log text is treated as data and escaped in generated HTML.

Game logs and generated HTML/PDF may contain character names, conversations,
network addresses, local paths, and other personal information. Keep them local
unless you have reviewed and chosen to share their contents. Use invented names,
reserved example addresses, and synthetic messages for tests and screenshots.

The repository ignores local logs, generated reports, environments, keys, and
databases. Ignore rules do not remove files already committed to Git history.
If a credential is exposed, revoke or rotate it before discussing history
cleanup with the maintainer.

## Release checks

The [readiness record](docs/public-readiness.md) describes the completed scan,
its scope, and remaining checks. A scanner result is evidence for that snapshot;
it does not prove the absence of every secret or privacy issue. Release archives
must be checked separately and contain only the portable application directory.
