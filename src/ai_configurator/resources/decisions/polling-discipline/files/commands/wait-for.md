---
description: Pick the right primitive for "wait for X" instead of chaining sleeps. Outputs the exact tool call shape for the user's situation; doesn't execute.
---

The Claude Code runtime blocks `sleep N; <check>` patterns used as
polling. This command walks through picking the correct primitive
before you hit the block.

### Step 1: Classify what you're waiting for

Answer one of these:

- **(A)** A command I just started (a build, test run, migration)
- **(B)** An external state change (a file appears, an API responds,
  a CI run finishes, a port opens)
- **(C)** A fixed delay between two known operations (rate-limit
  back-off, debounce window)
- **(D)** A long idle period during `/loop` (autonomous tick)

### Step 2: Propose the primitive

**(A) Command I started**

```
Bash(command="<your-command>", run_in_background=true)
```

You'll be notified when it exits. Read the result with the Bash
tool's standard output retrieval when notified. **Don't** start it
foreground and then sleep-poll its log file.

**(B) External state change**

```bash
until <one-line-check-that-returns-0-when-ready>; do sleep 2; done
```

Examples:

| Watching for | Check |
|---|---|
| File appears | `[ -f /path/to/file ]` |
| Port open on localhost | `nc -z localhost 8080 2>/dev/null` |
| HTTP 200 from URL | `curl -fsSL -o /dev/null --max-time 2 https://...` |
| GitHub Actions run finishes | `! gh run list --limit 1 --json status \| grep -q in_progress` |

Run the loop via the Monitor tool — each stdout line surfaces as a
notification; the loop exit fires a completion notification.

**(C) Fixed delay**

A single `sleep <N>` is fine. The block triggers on *chained*
sleeps used as polls, not on a one-shot delay.

**(D) Long idle in /loop**

```
ScheduleWakeup(delaySeconds=1200, prompt="<re-fire prompt>")
```

Or for staying within the cache TTL: `delaySeconds=240`. Never
`delaySeconds=300` (worst-of-both cache behavior).

### Step 3: Pause for confirmation

Don't execute. Print the proposed call. The user runs it when ready.
If they say "go", invoke it. After completion, surface one line:
"<thing> ready at <time>" or "exit code 0 after <duration>".

### Anti-patterns to refuse

- `sleep 30 && next-cmd` (will be blocked)
- `sleep 10; sleep 10; sleep 10` (same; runtime detects chained sleeps)
- `python3 -c "import time; time.sleep(30)"; next-cmd` (same)
- `while true; do <check>; sleep 1; done` (no exit condition — burns
  cache indefinitely)

If the user really wants a fixed delay (case C), confirm out loud
that it's not a poll before issuing the sleep.
