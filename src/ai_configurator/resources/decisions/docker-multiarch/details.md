# docker-multiarch

Bakes a single rule into every Claude Code session: **when the
current project uses Docker, every image we build runs on both
`linux/amd64` and `linux/arm64`** — Apple Silicon Macs, AWS Graviton,
Ampere, Raspberry Pi 4+, and the entire Intel/AMD desktop world all
run the same image without `--platform` flags.

This pack ships:

| File | Purpose |
|---|---|
| `CLAUDE.md.docker-multiarch.fragment` | Global rules to add to your `CLAUDE.md` so the policy fires whenever a Docker-related file (`Dockerfile`, `docker-compose.yml`, `Containerfile`) is present. **The fragment self-gates** — it explicitly says "if no Dockerfile in this project, skip these rules". |
| `commands/docker-multiarch-check.md` | `/docker-multiarch-check` slash command that audits the current Dockerfile + CI for multi-arch readiness. |

## Why self-gating

Most projects aren't Docker projects. Claude reads its full `CLAUDE.md`
every session, so an unconditional "build multi-arch" rule would fire
in every Rust / Python / Java context where it doesn't apply.
The fragment starts with:

> **Skip this section if the current project has no `Dockerfile`,
> `Containerfile`, `docker-compose.yml`, or `Compose.yml`.**

That's the gate. Claude reads the rule, checks for the trigger files,
and applies the policy only when relevant.

## Apply

```bash
ai-configurator decisions apply docker-multiarch
```

Then append the fragment to your live `CLAUDE.md`:

```bash
cat ~/.config/claude-config/content/claude/CLAUDE.md.docker-multiarch.fragment \
  >> ~/.config/claude-config/content/claude/CLAUDE.md
ai-configurator sync -m "adopt docker-multiarch"
```

This pack is **auto-applied** by `ai-configurator init` — new
content dirs get the slash command + fragment automatically.

## Why this matters in 2026

- **Apple Silicon is 70 %+ of new developer machines**. Any image that
  only builds for `amd64` makes those devs sit through `qemu`
  emulation every `docker compose up` — slow + unreliable.
- **AWS Graviton (ARM) is 20–40 % cheaper** per vCPU for the same
  workload. Companies move production fleets to it; an `amd64`-only
  image blocks that migration.
- **Raspberry Pi + small ARM SBCs** are the entry point for many
  edge / IoT / hobby deployments.
- **Future-proofing**: the ARM share grows every quarter; the cost of
  starting multi-arch is tiny, the cost of retrofitting later is real.

## Linux installs too

The same applies to non-Docker Linux installs of any tool we ship —
pure-Python tools are arch-agnostic but anything with C extensions
must publish `manylinux2014_x86_64` AND `manylinux2014_aarch64`
wheels. The fragment covers both.
