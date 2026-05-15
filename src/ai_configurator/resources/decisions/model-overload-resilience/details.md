# model-overload-resilience

Teaches every agent + project that loads this configurator how to
recover gracefully when a model provider is over capacity. Covers
Anthropic 529, OpenAI/Codex 503, and the generic 429 rate-limit case
shared across most providers.

## Why this exists

Provider capacity overload is the most common transient failure for
LLM-backed tools. Agents that don't handle it well either:

- Crash with an unhandled `APIStatusError`,
- Retry too aggressively and worsen the load,
- Or give up after one attempt and surface a confusing error to the user.

This pack codifies the right reflexes:

1. **Retry with exponential backoff + jitter.** Cap at ~30s.
2. **Respect `Retry-After` when the server provides it.**
3. **Cap concurrency** at 4-8 in-flight requests for parallel work.
4. **Fall back to a cheaper tier** (Opus 529 -> retry on Sonnet).
5. **Cache prompt prefixes** so retries are cheap.
6. **Move bulk work off-peak** using timezone-aware scheduling.
7. **Use the Batch API** for non-urgent bulk (separate capacity tier).

The 529-vs-429 distinction is important: 529 is *their* capacity
issue (every customer affected), 429 is *your* quota (only you). The
pack documents both.

## What ships

| File | Purpose |
|---|---|
| `CLAUDE.md.model-overload-resilience.fragment` | The standing rules an agent loads at session start. Multi-provider status-code table + retry playbook. |
| `commands/capacity-check.md` | `/capacity-check` slash command: maps the user's local timezone to current peak / off-peak windows for each provider and recommends "go" or "wait". |
| `data/off-peak-windows.json` | Structured per-provider off-peak data. Other tools (cron jobs, CI, dashboards) can consume this without parsing Markdown. |
| `scripts/api-retry.py` | Illustrative Python helper: stdlib-only retry wrapper with jitter, Retry-After honour, and provider-agnostic status-code matching. Users vendor or reference. |

## Apply

Auto-applied on `ai-configurator init`. Existing installs pick it up
on next CLI run via `reconcile()` because the dest filenames are
all new.

## Off-peak data

The JSON file is the source of truth for off-peak windows. The
slash command reads from it. Update the file (and bump the
`version` field) when peak patterns shift (e.g., after a major
model launch shifts load to a different tier).
