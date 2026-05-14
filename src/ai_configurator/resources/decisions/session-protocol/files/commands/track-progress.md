---
description: Set up a task list for a multi-step request. Use when the work spans > 3 distinct steps.
argument-hint: <one-line goal>
---

The user's request involves multiple distinct steps. Set up a task
list before starting so progress is visible and resumable.

1. **Decompose the goal** into 3–10 concrete tasks. Each task should
   be:
   - **Independently verifiable** — you can tell when it's done.
   - **Imperative-mood title** ≤ 60 chars.
   - **Ordered by dependency** — earlier tasks unblock later ones.

2. **Create each task** via `TaskCreate`:
   ```
   TaskCreate(subject="Verb-first task title", description="What done looks like")
   ```

3. **Mark `in_progress` BEFORE you start each task**, not when you
   finish. `TaskUpdate(taskId="N", status="in_progress")`.

4. **Mark `completed` THE MOMENT it's done**, not in a batch.
   Batching destroys the value of the task list.

5. **Surface failures**: if a task fails, mark it as still
   `in_progress`, add a `description` update explaining what failed,
   then either:
   - Spawn a sub-task to unblock it, OR
   - Ask the user a clarifying question if the failure is design-
     level, not bug-level.

6. **Reorder when reality drifts**: if you discover task 7 actually
   depends on task 12, fix the ordering immediately (`addBlockedBy`).
   Don't power through an obviously wrong sequence.

Default scale: a request that would take you 10+ tool calls is a
task-list request. Sub-3 tool calls is too small — just do it.
