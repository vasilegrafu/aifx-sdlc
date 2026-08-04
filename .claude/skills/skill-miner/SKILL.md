---
name: skill-miner
description: Mine an existing codebase into reusable Agent Skills that generate new code in that codebase's style. Use when asked to extract, mine, harvest, distill, or reverse-engineer conventions, patterns, idioms, house style, or reusable code chunks out of a repo or a named set of directories; to turn a codebase, a service, or a reference implementation into a skill, a skill pack, a template, or a scaffold; to capture "how we build X here" so future code, services, or whole applications come out looking like the team that wrote the original; or to diagnose a generated skill that fires but produces off-style code, or does not fire at all.
---

# Skill miner

Turn a codebase into skills that generate code indistinguishable from it.

The durable asset is the extracted knowledge, not the invocation mechanism. This
produces skills only — no agents, no orchestration.

## What comes out

```
<skills-dir>/<skill-name>/
  SKILL.md              frontmatter + the rules that change output
  assets/               canonical exemplars, copied from the source repo, annotated
  references/           the long tail: rejected approaches, per-case detail, regression log
  scripts/              checks and scaffolds with one right answer
```

Plus two working files that are not the product but must exist while you work:
an **evidence ledger** (Stage 1, `assets/evidence-ledger.template.md`) and a
**skill charter** (Stage 2, `assets/charter.template.md`). The skill you write
starts from `assets/SKILL.template.md`.

## Ground rules

1. **Encode the invisible delta.** What survives is what a competent stranger
   would get wrong *and not notice*. If the build screams, the skill is
   redundant — the feedback loop already teaches it.
2. **Show shape, say reason, script right answers.** Structure → `assets/`.
   Boundaries and prohibitions → prose. Anything with one correct output →
   `scripts/`.
3. **One exemplar under-determines.** A lone sample cannot say which lines are
   contract and which are sample data. Ship two that differ, or one annotated.
4. **No mined chunk may carry a credential.** Copied exemplars come out of a
   real repo. Scrub before writing; `scripts/lint_skill.py` fails the build on
   key-shaped strings.
5. **Flag bets as bets.** Where the evidence is thin, say so in the skill body
   in one line, with what would settle it. A confident-sounding invention is
   worse than a stated uncertainty.

## Stage 0 — Scope

Get these from the user before reading anything. Ask only what is missing;
assume and state the rest.

- **Target**: repo root, and the directories in scope (whole repo or a list).
- **What you'd build with it**: the artifact type this skill must generate — "a
  new service", "a new API endpoint", "a new migration". This defines the skill,
  not the codebase's structure.
- **Weak spots**: what is *not* worth copying — legacy corners, mid-migration
  areas, the module everyone apologises for.
- **Beyond the code**: git history? PRs? ADRs? CI config? runbooks? Reasoning
  lives there, and its absence changes Stage 1.

If the user names no artifact type, default to the largest repeated vertical
slice `scripts/conventions.py` reports, and say that you did.

## Stage 1 — Mine

Deliverable: an evidence ledger of candidate conventions, each with its evidence
class. Full procedure in `references/mining.md`.

```bash
./.venv/Scripts/python.exe .claude/skills/skill-miner/scripts/survey.py <root> --md
./.venv/Scripts/python.exe .claude/skills/skill-miner/scripts/conventions.py <root> --md
./.venv/Scripts/python.exe .claude/skills/skill-miner/scripts/history.py <root> --md
```

Read in this order, because each one tells you what to skip in the next:

1. `survey.py` — shape, size, stacks, where the mass is, what enforces things
   (CI, linters, hooks, codegen).
2. **Enforcement config first** — lint rules, type config, CI gates, pre-commit,
   codegen templates. Anything a machine rejects is a settled convention and you
   need no further evidence for it.
3. `conventions.py` — candidate repeated shapes, ranked with a recency split so
   fossils separate from live practice.
4. `history.py` — reverts, fix-density, long commit bodies. This is where
   *reasoning* is; the code only holds *outcomes*.
5. The two or three files `history.py` ranks highest for fix-density. They are
   where the codebase learned something.
6. ADRs, runbooks, PR discussions on those same files.

### Is it a convention or an accident?

Frequency is not evidence. Copy-paste produces frequency. A convention is
deliberate if it survived a force that would have removed an accident. Score
each candidate against four classes and require **two**:

| Class | Evidence | Strength |
|---|---|---|
| **Enforced** | a machine rejects the alternative — lint rule, type, CI gate, codegen | decisive alone |
| **Repaired** | a commit exists whose only purpose was bringing a file into line | strong |
| **Reasoned** | a written argument — ADR, PR thread, long commit body, a comment saying "not X because Y" | strong |
| **Recent** | the newest files in the repo do it too | necessary, never sufficient |

Then run the inversion — **the accident test**: *if this were done the other
obvious way, would anything break, or would anyone notice?* If nothing breaks
and nobody would notice, it is a style fossil. Fossils are cheap to keep and
expensive to encode; drop them.

Deviations are data. A pattern with violations nobody fixed is not a convention.
A pattern with violations that *were* fixed is one, and the fixing commit is
your Repaired evidence.

### Contradictions and mid-migration

Two patterns doing the same job means one of three things. Date both sides —
`conventions.py` gives you first-appearance and last-touch per candidate.

- **Old dying, new growing** → encode the destination. Also encode the departing
  pattern as a *tripwire*, because a generator reading the repo will otherwise
  imitate the fossil it sees most of.
- **Both live, split by area** → not a contradiction, it's a missing key. Find
  the observable that predicts which is used and encode it as a decision rule.
- **Both live, no ADR, no pattern to which is used** → the team has not decided.
  Don't decide for them — a skill that encodes the losing side of a live
  argument gets fought by every reviewer, and you find out only when people
  quietly stop using it. Record it in the ledger as open, raise it with the
  user, encode neither.

## Stage 2 — Distill

Deliverable: a charter naming every item that will survive, why, and its form.
Template `assets/charter.template.md`; full procedure in
`references/distilling.md`.

### Run the naive baseline first

Before deciding what is non-obvious, find out. Pick an artifact that exists in
the repo, reconstruct the prompt that produced it (its ticket or PR *title and
body* — never its diff), and generate it with **no skill loaded** in a session
that cannot see the repo.

**Anything the baseline already got right is not delta.** This is the only
reliable test for "genuinely non-obvious rather than merely familiar to me" —
your own sense of surprise is contaminated by knowing the answer. The baseline
is also Stage 4's control, so it is not extra work.

### The filter

Two axes: would a stranger produce it anyway, and would the mistake be visible?

|  | **Loud failure** (won't build, test fails) | **Silent** (runs, reviews clean, still wrong) |
|---|---|---|
| **Obvious** | drop | one line, no exemplar |
| **Non-obvious** | one line — the feedback loop teaches it | **the payload** |

Everything in the bottom-right earns an exemplar and a reason. Everything else
earns a line or nothing. A skill that is mostly top-left is a skill that mostly
burns context.

### Quirk or principle

Ask what the item looks like in a different language. If the statement cannot
survive translation, it is a quirk — state it as a literal fact and point at the
exemplar; do not dress it as a principle. If it survives, state the principle
*and* its local instantiation, because the principle alone does not generate
code. Rule of thumb: **quirks belong in exemplars, principles belong in prose.**

### Negative knowledge

"We tried X and reverted it because Y" is the highest value per token in the
whole pipeline — it is precisely what a capable stranger would try. Encode as a
tripwire, never as a bare prohibition:

> **Don't** <the tempting thing> — <what happened> (<evidence pointer>).
> Instead: <the thing to do>.

A prohibition without a reason gets overridden by a model that thinks it knows
better, or gets applied after the reason stops holding. Keep the strongest few
in the body; the rest go in the new skill's own `<skill>/references/rejected.md`.

## Stage 3 — Encode

Deliverable: the skill directory, passing `lint_skill.py`. Full argument in
`references/encoding.md`.

Start from `assets/SKILL.template.md`. Then:

- **Exemplars** are copied from the source repo verbatim, then scrubbed of
  secrets and trimmed of unrelated business logic — never paraphrased. Add a
  `<name>.notes.md` beside each marking which lines are load-bearing contract
  and which are sample data. Two exemplars that differ beat one plus prose,
  because the diff between them *is* the axis of variation.
- **Decision rules** go in a flat table keyed by something observable in the
  user's request, with a default row and an escape hatch. Not nested. If a rule
  needs more than about five branches, the branching is a real design axis:
  state it as a principle with two worked examples instead. A rule whose key the
  model cannot read off the request is not a rule, it is a lookup that will fail.
- **Scripts** for anything with one right answer: scaffolding a directory,
  deriving a name from another name, checking a generated file against the house
  rules. Deterministic beats instructional every time you can get it.
- **Description** is the trigger and the most common failure point. Write
  `<what it does> + Use when <phrasings>`, and include the codebase's own nouns —
  directory names, file suffixes, framework names — because those are what
  people paste. Collect ten phrasings you would actually type, put them in a
  file, and check coverage:

```bash
./.venv/Scripts/python.exe .claude/skills/skill-miner/scripts/lint_skill.py <skill-dir> --phrasings phrasings.txt
```

### Scope

One skill per thing you would actually build — the full vertical slice. Splitting
by concern (layering / errors / naming) is the classic mistake: generation needs
all of them at once, and split skills fire partially.

Split when the body outgrows what gets used in one shot, when two halves have
disjoint triggers, or when the exemplar set covers more than one target artifact.
**Split by target artifact, never by concern.** Before splitting, reach for
`references/` — a reference file is loaded on demand without needing to be
triggered, which is strictly safer than a second skill that may not fire.

## Stage 4 — Validate

Deliverable: a regression record in the new skill's own
`<skill>/references/regressions.md`. Full protocol
in `references/validating.md`.

Regenerate something that already exists and diff. Pick a target that is recent
(post-dates the conventions you encoded), mid-sized, a complete slice, and has a
written prompt you can reconstruct from *before* it existed.

Generate twice — baseline (no skill, from Stage 2) and skilled — then:

```bash
./.venv/Scripts/python.exe .claude/skills/skill-miner/scripts/regen_diff.py \
  --original path/to/real.ts --baseline out/base.ts --skilled out/skilled.ts \
  --normalize-cmd "npx prettier --write {file}"
```

Three comparisons, and the third is the one people forget:

| Reading | Diagnosis | Fix |
|---|---|---|
| skilled ≈ baseline | **not firing** | description, not content — rewrite triggers, shorten body, un-bury the rule |
| skilled ≠ baseline, still ≠ original | **firing, wrong** | the rule is mis-stated, the exemplar is missing, or the decision key is unobservable |
| skilled closer to original, gaps remain | **firing, incomplete** | additive — new exemplar or new rule row |
| skilled ≠ original and skilled is better | **the original was wrong** | record it, change nothing |

Meaningful divergence, concretely — *would a reviewer on that team comment?*
Yes if it changes the public surface, file placement or naming, failure
behaviour, a cross-cutting ceremony (logging, auth, transactions, telemetry), or
test shape. **If a formatter or autofix would erase it, it is not a divergence** —
which is why you pass `--normalize-cmd` and run the repo's own formatter on both
sides before reading anything.

Each surviving divergence maps to one edit:

| Divergence | Edit |
|---|---|
| structure missing | extend or add an exemplar |
| wrong choice among valid alternatives | add a decision-rule row |
| invented a thing that does not exist | tripwire in the body |
| right thing, wrong place or name | state the fact in prose + a scaffold script |
| differs every run | move it to `scripts/` |

**Stop** when two regenerations of *different* targets produce no new meaningful
divergences. Log each target, its prompt, and the outcome in
`<skill>/references/regressions.md` so next quarter's re-run is a replay, not a
redesign.

A full run end to end — ledger, charter, skill decomposition, a filled
`SKILL.md`, and the Stage 4 numbers — is in `references/worked-example.md`. Read
it once before the first run.

## Which skills come out, and in what order

Decompose by artifact, then order by how often you would invoke it. The first
skill is the vertical slice you build most: everything else is either a variation
on it (a decision-rule row, not a skill) or a rarer artifact that can wait.

1. The dominant slice — "how we build a `<service|endpoint|job|page>` here".
2. The artifact that most often accompanies it (migration, client, contract).
3. The cross-cutting thing that has its own trigger phrasing and its own target
   file — tests, CI, deploy.

Stop there and validate before adding more. An unvalidated skill pack is a
guess with a directory structure.

## Bets in this pipeline

- **Description phrasing dominates firing, more than body quality.** Settled by
  the `skilled ≈ baseline` check across several phrasings.
- **Annotated exemplars beat prose for structure.** Confident about exemplars,
  less so that the load-bearing annotation earns its tokens. Settled by
  regenerating with and without the notes file.
- **Recency-weighted repetition approximates deliberateness.** It is a proxy.
  Spot-check candidates against enforcement artifacts before trusting the rank.
- **Value concentrates in the non-obvious/silent quadrant.** Test it by counting
  which encoded items actually changed the regenerated output; the ones that
  changed nothing were context tax.
