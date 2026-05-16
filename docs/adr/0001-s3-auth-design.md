# ADR-0001 — S3 auth design

**Status**: Accepted (2026-05-16)
**Phase**: SPEC §4 Phase E — cross-machine sync beyond git
**Unblocks**: `ClaudeConfig.sync_to_s3` implementation

## Context

Phase E ships a way to sync the content dir to an S3-compatible
target (AWS S3, Cloudflare R2, Backblaze B2, MinIO, etc.) so
operators on machines without git access can still get the latest
config. The scaffold shipped in v0.6.0 (commit `9976632`); the
upload itself was blocked on three open questions:

1. **Which credentials chain?** AWS has a documented chain (env
   vars → shared credentials file → IAM role → SSO → instance
   metadata). Which subset do we honour, in what order?
2. **Do we ship a default profile or require explicit auth?**
3. **Federated identity (OIDC) for CI?** If `sync_to_s3` runs in
   CI, we want OIDC trusted publishing not long-lived keys.

## Decision

### 1. Credentials: boto3's default chain, unmodified

boto3's default credential resolution is well-documented and
respects the AWS conventions every operator already knows:

```
1. Constructor args   (we never pass these — keeps secrets out of code)
2. AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY env vars
3. AWS_PROFILE env var (selects from ~/.aws/credentials)
4. Shared credentials file ~/.aws/credentials  (default profile)
5. Container credentials       (ECS task role)
6. Instance metadata           (EC2 / EKS / similar)
```

We do NOT override the chain. We pass `Session(profile_name=…)`
when the user explicitly names a profile via `--profile` on the
CLI; otherwise we use the default session and let boto3 resolve.

### 2. Required: no implicit profile

We refuse to upload without one of:

- `AWS_PROFILE` env var set
- `--profile NAME` flag passed
- `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` in env

If none of these are present, `sync_to_s3` raises `ConfigError`
with a remediation that points at the boto3 credential docs.

Rationale: silently picking up `~/.aws/credentials.default` on a
shared machine has surprised more than one operator into
uploading to the wrong account. Explicit > implicit.

### 3. CI: OIDC via boto3 + AssumeRoleWithWebIdentity

For GitHub Actions, the standard pattern is
`aws-actions/configure-aws-credentials` which sets
`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` /
`AWS_SESSION_TOKEN` from STS. boto3 picks those up via #2 of the
default chain. We don't need ai-config-kit-specific OIDC code.

The workflow side gets a documented snippet in `docs/sync.md`:

```yaml
permissions:
  id-token: write
  contents: read
steps:
  - uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-assume: arn:aws:iam::123456789012:role/ai-config-sync
      aws-region: us-east-1
  - run: ai-config-kit sync --target s3://my-bucket/config --apply
```

### 4. S3-compatible endpoints

Support non-AWS S3 (R2, B2, MinIO) via the `--endpoint-url`
flag, which maps to `Session.resource("s3", endpoint_url=…)`.
Default is AWS; specifying `--endpoint-url` picks any compatible
target.

### 5. Upload semantics

Upload is `client.upload_file(path, bucket, key)` for each file
under `src_dir`. Symlinks resolve before upload (we want the
target's content, not the symlink path). Files matching the
secret patterns (`*.credentials.json`, `.env*`, etc.) are
filtered out by the existing `_is_secret` check.

A manifest file `.ai-config-sync.json` is written to the bucket
root with the per-file sha256 + content_dir layout so a
downstream `sync_from_s3` (Phase E.2) can diff before
overwriting.

## Consequences

### What this enables

- `ClaudeConfig.sync_to_s3(target, profile=None, endpoint_url=None,
  dry_run=False)` can be implemented.
- New CLI: `ai-config-kit sync --target s3://bucket/path [--profile NAME]
  [--endpoint-url URL] [--apply]`.
- Operators with multi-machine config get a non-git option.
- CI workflows can keep config in S3 + pull on cold runners.

### What this costs

- Optional `[s3]` extras dep (boto3) — already scaffolded.
- A new audit event `s3_sync` recording target, file count,
  bytes transferred.
- Secret-pattern filtering is the only defense against uploading
  `.env` files; we never override the user's secret patterns
  list.

### What this doesn't fix

- `sync_from_s3` (the reverse direction) is Phase E.2 — separate
  ADR. Today's flow is one-way (laptop → S3).
- Conflict resolution: if two machines upload to the same key
  prefix, last-write-wins. A v0.7 enhancement could use the
  manifest's sha256 to detect divergence.

## Alternatives considered

### Vendored credential reading (rejected)

Read `~/.aws/credentials` ourselves + handle each backend
explicitly.

**Why rejected:** reimplementing boto3's chain is fragile and
makes future credential types (SSO refresh, IMDSv2, etc.) our
problem. boto3 already handles this correctly.

### git annex / rclone / rsync wrappers (rejected)

Wrap rclone or git-annex for the sync.

**Why rejected:** adds a system-level binary dep that's painful
on macOS-default + Windows + Linux-fedora-default. boto3 is
pure-Python and bundles cleanly with `pip install
'ai-config-kit[s3]'`.

### Mandatory `--profile` (no env-var support) (rejected)

Force every operator to use a named profile.

**Why rejected:** breaks the CI flow where credentials come from
`configure-aws-credentials` action via env vars.

## Implementation

```python
def sync_to_s3(
    self,
    target: str,
    profile: str | None = None,
    endpoint_url: str | None = None,
    dry_run: bool = True,
) -> S3SyncReport:
    if not target.startswith("s3://"):
        raise ConfigError(f"sync target must be s3://bucket/key, got {target!r}")

    # Refuse implicit auth — explicit profile or explicit env vars only.
    if profile is None and "AWS_PROFILE" not in os.environ and (
        "AWS_ACCESS_KEY_ID" not in os.environ
        or "AWS_SECRET_ACCESS_KEY" not in os.environ
    ):
        raise ConfigError(
            "no AWS auth detected; set AWS_PROFILE, pass --profile NAME, "
            "or set AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY"
        )

    import boto3
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    client = session.client("s3", endpoint_url=endpoint_url)

    bucket, _, key_prefix = target[5:].partition("/")
    uploaded: list[str] = []
    skipped_secrets: list[str] = []
    for path in self._files_to_track(include_overlays=True):
        if self._is_secret(path):
            skipped_secrets.append(str(path.relative_to(self.src_dir)))
            continue
        rel = path.relative_to(self.src_dir).as_posix()
        key = f"{key_prefix.rstrip('/')}/{rel}" if key_prefix else rel
        if not dry_run:
            client.upload_file(str(path), bucket, key)
        uploaded.append(rel)
    # Manifest + audit event after the loop.
    ...
```

## Next steps

1. Land the `sync_to_s3` implementation per the snippet above.
2. Add `S3SyncReport` dataclass.
3. CLI: `ai-config-kit sync --target s3://... [--profile NAME]
   [--endpoint-url URL] [--apply]`.
4. Tests using `moto` (the AWS mocking library) — won't add a
   network dep.
5. `docs/sync.md` covering the CI snippet + R2/B2/MinIO examples.
