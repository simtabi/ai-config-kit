---
description: Ask one focused clarifying question when the request is ambiguous and the wrong path is expensive.
---

The user's request is ambiguous. The wrong interpretation would cost
more than 5 minutes to undo. Ask **one** clarifying question with a
numbered options list.

Rules for the question:

1. **Show that you understand what they probably want.** Lead with a
   one-sentence restatement of your strongest guess.

2. **Numbered options**: list 2-4 concrete options, each with the
   trade-off:
   ```
   Which approach?
     1. Option A: pro: X. con: Y. (my default)
     2. Option B: pro: Z. con: W.
     3. Something else: describe.
   ```

3. **State your default** so a "go ahead" without an explicit pick
   still progresses.

4. **One question, not three.** If you have three unknowns, pick the
   one that gates the most downstream work and ask that.

5. **Don't ask about things you can verify**: if the answer is in
   the codebase, go find it. Reserve clarifying questions for
   genuine human-only decisions (preferences, priorities, ambiguous
   intent).

6. **Don't Socratically explore** the problem: that's mid-work
   reasoning, not a clarifying question. Save it for after the
   user picks an option.

When NOT to clarify:

- Wrong interpretation costs < 5 minutes to undo.
- The answer is in `SPEC.md` / `STATUS.md` / `CHANGELOG.md` /
  recent commits and you haven't read those yet.
- You've already asked a clarifying question this session.
- The user explicitly told you to "just do it" / "use your judgement".

Template:

> Just to confirm before I touch anything:
>
> You want **<one-sentence restatement>**. Two paths:
>
> 1. **<Option A>**: pros: …; cons: …. (default if you don't pick)
> 2. **<Option B>**: pros: …; cons: ….
>
> Pick a number or describe a third path?
