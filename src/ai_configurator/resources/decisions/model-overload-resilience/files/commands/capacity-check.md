---
description: Map the user's local timezone to current peak / off-peak windows for each AI model provider, then recommend whether to proceed or wait. Reads from the data/off-peak-windows.json bundled with the configurator.
---

`/capacity-check` answers "is now a good time to fire a batch of
model calls?" for whichever providers the user is using.

### Step 1: Detect the user's timezone

```bash
# macOS / Linux: read the system zoneinfo
date +%Z                                  # short name (e.g. EAT, PST, JST)
# OR the IANA zone:
readlink /etc/localtime | sed 's|.*zoneinfo/||'   # e.g. Africa/Nairobi
# fallback: $TZ env var
echo "$TZ"
```

If none resolves, ask the user: "What's your IANA timezone (e.g.
`America/New_York`, `Europe/London`, `Africa/Nairobi`)?"

### Step 2: Read the bundled off-peak data

```bash
cat ~/.claude/data/off-peak-windows.json
```

The file ships with the `model-overload-resilience` pack. If it's
missing, run `ai-configurator init` to (re-)apply the pack.

### Step 3: Compute the verdict

For each provider the user cares about (default: Anthropic +
OpenAI), compare current local time to the off-peak window listed
under `providers.<provider>.off_peak_windows.<user_tz>`:

- **In off-peak window**: GREEN. Proceed.
- **In peak window**: AMBER. Recommend retry-with-backoff is wired,
  fallback model is configured, and concurrency is capped (<=8).
- **In peak window AND a known hot day** (post-model-launch, end of
  US quarter): RED. Suggest deferring the work.

If the user's timezone isn't in the JSON, suggest the nearest
listed zone and add a note that the off-peak data is heuristic.

### Step 4: Report

Print a short verdict table:

```
provider    status   window now              recommendation
anthropic   GREEN    22:00-06:00 your local  proceed
openai      AMBER    peak (Mon-Fri 09-18)    retry-with-backoff + fallback
codex       AMBER    inherits openai         same as openai
```

Plus a one-line tip:

> Anthropic and OpenAI both off-peak: bulk work runs cleanly. Use
> the Batch API if you have >100 prompts to send.

### Step 5: Don't act unilaterally

`/capacity-check` is informational. Don't reschedule cron jobs,
flip env vars, or change registry entries without confirming with
the user. If they say "go", proceed. If "wait", quote the off-peak
window opening time in their local zone.

### Hot-day flags

Refuse GREEN regardless of clock when any of these are true:

- **Post-model-launch**: a new Opus/Sonnet/gpt-* released within
  the last 48 hours.
- **End of US quarter** (last week of Mar/Jun/Sep/Dec).
- **status.anthropic.com** or **status.openai.com** shows an
  active incident.

For incident status, fetch the providers' status JSON if available
or recommend the user check the status page directly. Don't guess.
