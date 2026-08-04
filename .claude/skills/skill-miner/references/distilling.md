# Stage 2 — Distill

The ledger from Stage 1 is everything true about the codebase. Almost none of it
belongs in a skill. This stage is a filter, and it should reject most of its
input; a distillation that keeps most of what it started with has not been run.

## The rule, sharpened

The working version — *encode the delta, not the domain* — is right and one step
short. A competent stranger fails to produce plenty of things they would
immediately fix on the first build error. Those are deltas, and encoding them
buys nothing.

> **Encode what a competent stranger gets wrong on the first try and does not
> notice on the second.**

Non-obviousness is necessary. Invisibility is what makes it worth context.

## Step 1 — the naive baseline

Do this before judging anything, because your sense of what is surprising has
been destroyed by reading the answer.

1. Pick an artifact in the repo (the Stage 4 target works; use the same one).
2. Reconstruct the prompt that produced it from what existed *before* it — the
   ticket, the PR title and body, the issue. Never the diff. The diff is the
   answer key.
3. Generate it with no skill loaded, no repo access.
4. Diff against the real file.

### How to actually run step 3

The two constraints are *no skill* and *no repo*, and the second is the one
people get wrong: a generator that can read the repo will copy the neighbouring
file, produce a perfect result, and tell you there is no delta to encode.

- **Fresh session, empty directory** (default). Start a session in
  `.mining/<ws>/baseline/`, which contains nothing. Paste the reconstructed
  prompt. Save the output there. Nothing in that directory can leak the answer.
- **Restricted subagent** (faster, same session). Launch one with no read access
  to the source repo and no skills loaded, and have it write into `baseline/`.
  Using a subagent as a measuring instrument is not building an agent
  architecture — it is a test harness, and it disappears with the run.
- **What does not work**: asking the same session to "pretend you have not read
  the repo". It has, and the output will show it.

Keep the prompt file next to the output. Stage 4 reuses both, and next
quarter's re-run needs them to mean anything.

What the baseline got right is not delta, no matter how clever it felt when you
found it in the code. What it got wrong is a candidate. What it got wrong
*silently* — code that runs and reads fine — is the payload.

This costs one generation and pays for itself twice: it is also the control arm
of Stage 4's firing test.

## Step 2 — the quadrant

Place every surviving ledger row.

|  | **Loud failure** | **Silent** |
|---|---|---|
| **Obvious** | drop entirely | one line of prose |
| **Non-obvious** | one line of prose | exemplar + reason + tripwire |

Judging *loud*: would the failure surface within one build/test/typecheck cycle
of the generator's own loop? If yes, the machine teaches it faster and cheaper
than the skill can. This is the counter-intuitive one — plenty of hard-won
knowledge about a codebase is genuinely non-obvious and genuinely worthless to
encode, because the compiler says it out loud.

Judging *obvious*: only the baseline may judge this. Not you.

## Step 3 — quirk or principle

For each survivor, ask: **what does this look like in another language or
framework?**

- **Does not translate** — a naming scheme, a directory layout, a specific
  helper that must be used. Quirk. State it as a flat fact, point at the
  exemplar, spend no words justifying it. Attempting to generalise a quirk
  produces prose that sounds like architecture and generates nothing.
- **Translates** — an ordering constraint, an error-handling posture, a
  dependency direction. Principle. State the principle *and* the local
  instantiation. The principle alone will be agreed with and then ignored; the
  instantiation alone will be copied into a context where it does not apply.

Quirks belong in `assets/`. Principles belong in the body. When in doubt it is a
quirk — the failure mode of this pipeline is over-generalisation, producing
skills full of true, portable, useless sentences.

## Step 4 — negative knowledge

Anything the ledger recorded as "tried and reverted", "considered and rejected",
or "used to be done that way".

This is the densest value in the pipeline for one reason: a capable generator
will *reinvent the rejected approach*, because it was rejected for a
non-obvious, local reason and it looked good on paper. Prohibitions here are not
red tape; they are the accumulated results of experiments you already paid for.

Form:

> **Don't** <the tempting thing> — <what happened> (<sha / PR / ADR>).
> Instead: <what to do>.

Three parts, all mandatory:

- **The temptation stated first.** A prohibition the reader does not recognise
  as the thing they were about to do never fires.
- **The consequence.** Without it the rule is a superstition, and it will be
  overridden the moment it is inconvenient, or obeyed long after the reason
  expired.
- **The pointer.** Lets a future reader re-check whether the reason still holds.
  Negative knowledge decays; a rule with a date on it can be retired.

Keep the strongest few in `SKILL.md`. The rest go to `references/rejected.md`,
which is cheap to keep because it is only loaded when consulted.

## Step 5 — assign a form

Every survivor gets exactly one primary form. Write it in the charter.

| Form | For | Test |
|---|---|---|
| `assets/` exemplar | anything with a shape | can you point at lines instead of describing them? |
| body prose | reasons, boundaries, prohibitions, principles | is it a *why* or a *never*? |
| decision-rule row | a choice between shapes you already ship as exemplars | is the key observable in the request? |
| `scripts/` | one right answer, computable | could you write a test for the output? |
| `references/` | true, occasionally needed, long | would including it inline crowd out the payload? |
| dropped | everything else | — |

Items that want two forms usually want one exemplar plus one prose line. Items
that want three are two items.

## Budget

Set the budget before writing, not after. A body under roughly 200 lines gets
read whole; past 500 the tail competes with the payload for attention. If the
charter does not fit, the cut comes from the top-left of the quadrant, never
from negative knowledge — the tempting-thing-that-fails rows are the last to go.

## Charter checkpoint

Before Stage 3, the charter should let you answer:

- What is the one artifact this skill generates?
- Which three items, if removed, would most degrade the output? (If you cannot
  name three, you have not found the payload — return to Stage 1.)
- Which items are quirks, and are they all in `assets/`?
- Which items came from the baseline diff rather than from your own judgment?
  A charter with none is a charter assembled from familiarity.
