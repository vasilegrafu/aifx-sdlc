---
name: sdlc-skill-mining
description: Extract a reusable skill from an existing project — find what a team does repeatedly, separate the convention from the accident and the procedure from the stack, and produce a candidate skill brief. Use when asked to "mine", "extract", "harvest" or "capture" practices from a repository, to turn a team's way of working into a skill, or to answer "what should we make a skill out of here". Produces a brief; sdlc-skill-authoring turns the brief into a working skill.
---

# Skill mining

You are turning **what a team does** into **a procedure anyone can follow**.
The output is a *brief*, not a skill — `sdlc-skill-authoring` writes the skill.
Keeping those separate is what stops a half-understood practice from being
written up in an authoritative voice.

Mining spans an agent boundary: the evidence-gathering is read-heavy and belongs
to `sdlc-explorer`; the judgment is not delegable and stays with the caller.

## The judgment this skill exists for

**A convention and an accident look identical in a grep.**

Twenty files doing the same thing might be a practice the team converged on over
two years, or one person's afternoon. The code cannot tell you which. `git log`
can, and that question — asked early — is the difference between a skill worth
having and twenty copies of someone's habit.

## Procedure

### 1. Choose something that repeats

A skill pays for itself only if the procedure recurs. Look where repetition is
already visible:

- pull-request templates and checklists — someone wrote down what kept going wrong
- CI pipeline steps — an enforced practice, already executable
- review comments that appear again and again — an unwritten rule with a cost
- runbooks, onboarding docs, `CONTRIBUTING.md`
- the explanation given to every new joiner
- post-incident actions that changed how work is done

**Reject one-offs.** A clever solution used once is a good story, not a skill.

### 2. Gather evidence — dispatch the explorer

Send `sdlc-explorer` at it. Ask for facts, not impressions:

- **where** the practice appears — file:line anchors
- **how consistently** — how many places follow it, how many diverge
- **since when** — `git log -S` on the distinctive string
- **by how many authors** — one person, or the team
- **whether it survived a refactor** — a practice that was re-applied after a
  rewrite was chosen deliberately; one that was merely never touched was not

Survey first if the repo is unfamiliar; trace when you need the thread.

### 3. Apply the convention test

| Evidence | Reading |
|---|---|
| many authors, long span, survived a refactor | **convention** — mine it |
| one author, short span, never revisited | **habit** — do not mine it |
| followed in most places, diverging in a few | **convention plus drift** — mine it, and record what the divergence costs |
| enforced by CI or a linter | **convention, already executable** — mine the *check*, not the prose |

The last row is the most valuable and the most often missed. If a practice is
enforced by a pipeline step, that step is a working implementation someone
already debugged. Lift it.

### 4. Separate the invariant from the stack

For every rule you are about to write down, ask:

> **Would this still be right on a different stack?**

- **Yes** → it is the procedure. It goes in `SKILL.md`.
- **No** → it is stack detail. It goes in `stacks/<name>.md`.
- **Only because of this repo's framework/vendor/legacy** → it is not a skill at
  all. Drop it, or record it as a note in the brief.

This split is the whole reason a skill survives contact with a second project.
Get it wrong and you have written `sdlc-<thing>-for-that-one-repo` under a name
that promises more.

### 5. Find the executable part

Prose drifts; a script reads the tree every time. For each rule, ask whether it
can be *checked* rather than *described* — file layout, naming, required files,
a config invariant, a version pin. Anything CI already enforces is executable by
definition.

Note these in the brief as candidate checks. Authoring writes them.

### 6. Decide the granularity

One brief may be several skills. The test is **the trigger**, not the topic:

> Does one question bring all of this to mind, or several different questions?

Different triggers mean different skills, however related the subject. Two
procedures with different *stopping conditions* must never share a skill —
each one's stopping rule licenses the other's failure mode. (Surveying and
tracing a codebase are one topic and two skills for exactly this reason.)

### 7. Record provenance

Mined knowledge has a source, and the source keeps moving. Every brief carries:

- which repository, and the commit it was read at
- the date
- what evidence supported each rule — anchors, not memory
- **the confidence**: observed everywhere / observed often / observed once and
  reasoned from

Without this, nobody can ever re-check the skill against the project that
justified it, and a rule that has since been abandoned upstream lives forever.

## Output — the candidate brief

```
Skill        proposed name, and the trigger question it answers
Source       repo @ commit, date

Procedure    the steps, stack-agnostic
             each step: the rule, and the evidence for it (file:line, git range)

Stack notes  what belongs in stacks/<name>.md, grouped by stack

Checkable    rules a script could enforce rather than describe

Confidence   per rule: everywhere / often / once
Rejected     what you looked at and chose not to mine, and why
Splits       if this should be more than one skill, the proposed split
```

**"Rejected" is not padding.** It stops the next person re-mining the same dead
end, and it is the record that a judgment was made rather than skipped.

## Anti-patterns

- **One repo, universal claim.** A skill mined from a single project encodes
  that project's compromises — its framework, its team size, its one bad
  outage. Step 4 is the defence; do not skip it because the rule feels obvious.
- **Mining the documentation.** Docs state intent and drift silently. Mine what
  is *practised*, then note where the docs disagree — that gap is itself a
  finding.
- **Mining the exception.** The interesting edge case is memorable precisely
  because it is rare. Frequency decides, not memorability.
- **Preserving a workaround.** Some practices exist to route around a bug, a
  version, or a person. Check whether the reason still holds before enshrining
  it — `git log` usually names the reason.
- **Mining taste as standard.** One senior engineer's preference repeated
  across their own files is a habit with good PR. Step 3 exists to catch this.
- **Writing the skill while mining.** The brief is the deliverable. Authoring
  in the same pass means the parts you were least sure of arrive in the same
  confident voice as the parts you verified.
