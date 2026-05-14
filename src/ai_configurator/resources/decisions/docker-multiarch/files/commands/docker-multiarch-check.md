---
description: Audit the current project's Dockerfile + CI for multi-arch readiness. Suggest fixes for any amd64-only patterns.
---

Audit this project for multi-arch (linux/amd64 + linux/arm64) build
readiness. Don't change any files yet — report findings and propose
the diff. I'll ask you to apply.

Run these checks **in order** and report inline:

### 1. Trigger files present?

```bash
ls Dockerfile* docker-compose* Compose* Containerfile* 2>/dev/null
```

If none of those exist, this isn't a Docker project — stop here and
say so. Otherwise continue.

### 2. Dockerfile inspection

For each `Dockerfile` / `Containerfile`:

```bash
grep -nE "^FROM\b" <dockerfile>
grep -nE "^ARG \s*(TARGETPLATFORM|TARGETARCH|BUILDPLATFORM)" <dockerfile>
grep -nE "^RUN.*amd64|arm64|x86_64|aarch64" <dockerfile>
```

Flag if:

- A `FROM` line hardcodes `--platform=linux/amd64` (or any single
  platform).
- The image downloads a binary without using `$TARGETARCH` to pick
  the URL (look for `curl -o`, `wget -O`, `ADD https://...`
  followed by an arch-specific filename).
- The base image isn't a known multi-arch one (`ubuntu`, `debian`,
  `alpine`, `python`, `node`, `golang`, `rust`, etc.). If unsure,
  `docker manifest inspect <image>:<tag>` shows the available
  platforms.

### 3. docker-compose / Compose

```bash
grep -nE "platform:|image:" docker-compose*.yml Compose*.yml 2>/dev/null
```

Flag if any `platform:` key is hardcoded to a single arch.

### 4. CI inspection

```bash
ls .github/workflows/*.yml .gitlab-ci.yml .circleci/config.yml 2>/dev/null
```

For each found CI file:

- Is `docker/setup-buildx-action` used?
- Is `docker/setup-qemu-action` used (for cross-arch builds on
  amd64 runners)?
- Is the `platforms:` input set to include `linux/arm64`?

### 5. Release artefacts (non-Docker installs)

If the project ships Python wheels or binaries:

```bash
ls dist/*.whl 2>/dev/null
grep -rE "cibuildwheel|maturin|goreleaser" . --include='*.toml' \
     --include='*.yml' --include='*.yaml' 2>/dev/null | head
```

Flag if wheels are built only for `x86_64` (look at the filename
suffix: `manylinux2014_x86_64.whl` only vs both arches).

### 6. Report

Output a short markdown table:

```
| Finding | Severity | Suggested fix |
|---|---|---|
| Dockerfile:12 hardcodes --platform=linux/amd64 | high | Remove the flag; let buildx pick |
| .github/workflows/release.yml: no qemu-action | medium | Add docker/setup-qemu-action@v3 |
| dist/*.whl has only x86_64 | medium | Add cibuildwheel-aarch64 matrix |
```

Then list the **smallest diff** that would address each item.

### Do not

- Don't apply fixes without my confirmation.
- Don't run `docker build` yourself; just analyse the files.
- Don't flag things like `RUN apt-get install` that are arch-neutral
  but contain the substring `amd64`; the grep above is a starting
  point, you decide what's actually amd64-only.

If everything is already multi-arch ready, say so in one sentence and
move on.
