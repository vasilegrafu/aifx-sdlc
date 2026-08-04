# Stage 3 — Encode

Turning the charter into a directory that reliably generates good code.

## Exemplars vs. prose vs. scripts

The belief that a canonical reference implementation beats any amount of English
is **right for structure and wrong for choice**, and the boundary is sharp
enough to be operational.

### What only an exemplar can carry

Shape. File layout, ordering of sections, ceremony, naming rhythm, how much is
in the constructor, where the logging goes, what the test file looks like beside
it. Every attempt to describe these in prose either omits something or produces a
paragraph the generator satisfies in a way you did not intend. One real file is
unambiguous about all of it simultaneously, and simultaneity is the point — the
relationships between the parts are most of the style.

Copy exemplars **verbatim** from the source repo, then scrub secrets and trim
business logic unrelated to the shape. Do not rewrite them into something
cleaner. A cleaned-up exemplar generates cleaned-up code that no longer matches
the repo, which is the entire failure this pipeline exists to prevent.

### What an exemplar cannot carry

1. **What varies.** A single sample cannot say which parts are contract and
   which are this instance's data. The reader must guess, and will guess that
   distinctive-looking things are meaningful.
2. **Why.** Structure is visible; the rejected alternative is not.
3. **Absence.** You cannot show a prohibition. An exemplar that omits caching
   does not say "do not cache here".
4. **Choice.** One sample shows one case. Generation needs the rule for picking.

### How much to copy: file, or chunk

Two units, and they are not interchangeable.

- **Whole file** is the default for anything with a shape — a handler, a
  service, a test. Shape is about the relationships between parts, and those
  only survive if the parts arrive together.
- **Chunk** — a run of lines repeated verbatim across files, which is what
  `conventions.py` BLOCK finds: the bootstrap, the error wrapper, the
  transaction dance. Ship these as a marked region inside an exemplar, or as a
  template in `scripts/` if it is truly fixed. State that it must appear
  verbatim, because a generator will otherwise paraphrase it into something
  equivalent-looking and subtly different.

The distinction is mechanical: **if it varies by entity name between real
instances, it is shape (whole file); if it is identical across instances, it is
a chunk.** A chunk pasted into prose gets reworded; a chunk in a file gets
copied.

### The placeholder problem

An exemplar copied verbatim carries the domain nouns of whatever it was — the
generator writes `OrderService` into a feature about invoices, which is the most
recognisable symptom of a skill built this way.

Do not solve it by rewriting the exemplar into something generic; that destroys
the very texture you copied it for. Solve it in the notes file with an explicit
mapping table (`assets/exemplar.notes.template.md`):

| In the exemplar | Stands for |
|---|---|
| `Order`, `orders` | the entity |
| `OrderService` | `<Entity>Service` |
| `createOrder` | `<verb><Entity>` |

Three rows are usually enough. The mapping is also what makes the exemplar
readable a year later, when nobody remembers which parts were the example.

### The fix for (1): never ship one exemplar alone

Either:

- **Two exemplars that differ** along the axis that actually varies. The diff
  between them *is* the specification of what is free and what is fixed, and the
  reader extracts it without being told. This is the best option whenever two
  real instances exist. Prefer a pair that differ in one dimension only.
- **One exemplar plus `<name>.notes.md`** listing which lines are load-bearing
  contract, which are sample data, and which are optional. Cheaper, and worse:
  it relies on the reader cross-referencing.

Never a bare exemplar. A bare exemplar produces output that copies the sample's
domain nouns into an unrelated feature — the single most recognisable symptom of
a skill built this way.

### What must be prose

Reasons, boundaries, prohibitions, principles, and the decision rules. Short
sentences, second person, imperative. Prose earns its place when it says *never*,
*because*, or *when*. Prose describing shape is dead weight sitting next to an
exemplar that already showed it.

### What must be a script

Anything with one right answer: scaffolding a directory tree, deriving a name
from another name, generating boilerplate that is fully determined, and above
all **checking**. A check written as prose ("make sure the handler is
registered") is advice; the same check as a script is a fact. Convert every
prose check you can, then have the skill body tell the generator to run it
before declaring done.

Scripts also survive model changes better than instructions do. Prefer them even
when the instruction currently works.

## Decision rules that do not degenerate

A decision tree nobody follows has three causes, and each has a fix.

**Cause 1: the key is not observable.** "Use the async variant when the workload
is IO-bound" requires knowledge the generator does not have at generation time.
A rule only fires if its key can be read off the user's request or off a file
that already exists. Rewrite keys until they are observable: "when the request
mentions an external API, a queue, or a webhook".

**Cause 2: nesting.** Nested conditions require the reader to hold state. Use a
flat table, one row per case, keyed by an observable, each row pointing at an
exemplar:

| If the thing you are building… | Then | Exemplar |
|---|---|---|
| talks to the database | `…` | `assets/repo-service.ts` |
| calls an external API | `…` | `assets/gateway-service.ts` |
| neither | `…` (the default) | `assets/plain-service.ts` |

Always a default row. Always an escape hatch: *if none match, follow the default
and say in your output that you did* — an unmatched case that fails loudly is
recoverable; one that silently picks the first row is not.

**Cause 3: too many rows.** Past roughly five, the branching is not a lookup, it
is a design axis. Stop enumerating and state the underlying principle with two
worked examples at the extremes. Enumerating a design axis produces a table that
is always missing the row you need.

## Scope: pressure-testing the vertical slice

The instinct is correct, and for the stated reason: generation needs layering,
error handling and naming *simultaneously*, and concern-split skills fire
partially — you get a service with house-style error handling and foreign
layering, which is worse than either alone because it looks deliberate.

Where it breaks:

- **The body outgrows one-shot attention.** Past ~500 lines the tail is
  decoration. Symptom: a rule near the bottom that validation shows is not
  firing while an identically-worded rule near the top is.
- **The exemplar set covers more than one target artifact.** A service and a
  database migration are different things being built at different moments.
  Carrying migration exemplars in the service skill taxes every service.
- **Two halves have disjoint triggers.** If no plausible request invokes both,
  they are two skills wearing one name, and the union of their descriptions
  triggers each of them wrongly half the time.
- **Variation axes multiply.** Two axes with five values each cannot be covered
  by an exemplar set; that is a sign the "one thing" is actually a family.

**Split by target artifact, never by concern.** "Service", "migration", "client
SDK" — each is a thing someone sits down to build. "Error handling" is not.

**Before splitting, use `references/`.** A reference file is loaded on demand and
does not need to be triggered, so moving the deep-but-rare half of a skill into
`references/` gets the size benefit without the partial-firing risk. Reach for a
second skill only when the trigger phrasings are genuinely disjoint.

## Descriptions: the actual trigger

Under-triggering is the dominant failure mode of skills, and the description is
almost always the cause. The body can be perfect and never load.

Shape: **what it does, then `Use when` followed by phrasings.**

Include, deliberately:

- the **verbs** a person would use — build, add, create, scaffold, wire up,
  implement, port, extend;
- the **artifact nouns** — endpoint, service, handler, migration, job, page;
- the **codebase's own nouns** — actual directory names, file suffixes,
  framework and library names, internal jargon. People paste these, and they are
  the highest-precision triggers available;
- the **problem phrasings**, not just the build phrasings — "why does my
  handler not …", "make this match the rest of the repo";
- a negative clause **only** when a sibling skill would otherwise collide.

Test it rather than admiring it. Write ten phrasings you would actually type —
including two lazy ones and one that names no keyword at all — into a file, and
run:

```bash
./.venv/Scripts/python.exe .claude/skills/skill-miner/scripts/lint_skill.py <skill-dir> --phrasings phrasings.txt
```

Lexical overlap is a proxy, not proof of triggering. Real proof is the Stage 4
firing test: if the skilled generation matches the baseline, it did not load,
whatever the linter said.

## Wiring: the one thing an exemplar cannot show

`graph.py` WIRING names the registries a new artifact must be added to — the
barrel, the route table, the DI container. This never appears in an exemplar,
because the exemplar *is* the new file and the edit happens somewhere else.

State it as an imperative naming the exact path:

> After creating the handler, add it to `src/handlers/index.ts`. Nothing else
> will tell you: an unregistered handler compiles, passes its own test, and is
> unreachable.

Better still, make it a script: a check that fails when the new file is not
referenced from the registry is deterministic, and this failure mode is the one
most worth automating because nothing else catches it.

## Provenance: write it as you go

Every rule that lands in the skill gets a row in `references/provenance.jsonl` —
its claim, its form, where it lives in the skill, its evidence classes with
pointers, the source path and sha, and the date mined.

This is not bookkeeping for its own sake. It buys three things nothing else
provides:

1. **Re-checkability.** In six months someone will challenge a rule. Without a
   pointer, the argument is settled by whoever is most confident.
2. **Drift detection.** `drift.py` reads exactly this file. No provenance, no
   drift check, and the skill ages silently.
3. **Expiry.** A `Confirmed` item carries a name and a date, so it can be
   re-asked when the reason may have lapsed — or when that person has left.

Write the row when you write the rule. Reconstructing provenance afterwards
means re-deriving the evidence, which nobody does, which is why skills end up as
folklore.

## Assembly checklist

Run `lint_skill.py` and fix everything it reports, then check by hand:

- Frontmatter `name` matches the directory name; description is one paragraph,
  third person, with `Use when`.
- Every exemplar is real code from the source repo, scrubbed, and either paired
  or annotated.
- Every path mentioned in the body exists.
- Every decision rule has an observable key, a default, and an escape hatch.
- Every prohibition carries a consequence and a pointer.
- Any check that could be a script is a script, and the body says to run it.
- Bets are labelled as bets, in one line each.
