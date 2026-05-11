# Security policy

## Reporting a vulnerability

**Do not file public issues for security reports.** Use either:

- Email: `opensource@simtabi.com` (preferred)
- GitHub private advisory:
  <https://github.com/simtabi/claude-configs/security/advisories/new>

We aim to acknowledge within 72 hours. Please include:

- Description of the issue and its impact
- Steps to reproduce
- Affected version(s)
- Proof-of-concept code, if applicable
- Whether you'd like public credit for the report

## Supported versions

| Version | Status |
|---------|--------|
| 0.1.x | Current — supported |

Security fixes target the latest minor release. Older minors receive
fixes only for High and Critical severities.

## Scope

In scope:

- The `claude-config` Python package on PyPI
- The source code in this repository
- The CLI entry point and the `ClaudeConfig` class

Out of scope:

- The user's personal content directory and its git remote (those
  are theirs)
- Claude Code itself (report to Anthropic)
- Third-party tools shelled out to from CI examples (git, etc.)

## Built-in protections

The tool itself enforces secret hygiene at multiple layers:

1. **Refuses to track** files matching `secret_patterns`
   (default: `.credentials.json`, `*.key`, `*.token`, `*.pem`,
   `*.p12`, `*.secret`, `.env`, `.env.*`).
2. **Refuses to symlink** the same patterns during `install`.
3. **Pre-populates `.gitignore`** in newly-initialized content
   directories with those patterns.
4. **No network access** in the tool itself — every git operation
   only touches the user-configured content dir.

If you find a way to bypass these protections, that's a security
issue. Report it via the channels above.

## Disclosure

We coordinate disclosure with reporters. Default policy: publish an
advisory once a fix is released, credit the reporter (with their
permission), assign a CVE when warranted.
