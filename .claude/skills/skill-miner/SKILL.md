---
name: skill-miner
description: Mine an existing codebase into reusable Agent Skills that generate new code in that codebase's style. Use when asked to extract, mine, harvest, distill, or reverse-engineer conventions, patterns, idioms, house style, or reusable code chunks out of a repo or a named set of directories; to turn a codebase, a service, or a reference implementation into a skill, a skill pack, a template, or a scaffold; to capture "how we build X here" so future code, services, or whole applications come out looking like the team that wrote the original; to check whether a mined skill has gone stale against the repo it came from, or which artifact types still have no skill; or to diagnose a generated skill that fires but produces off-style code, or does not fire at all.
---

# Skill miner

Turn a codebase into skills that generate code indistinguishable from it.

The durable asset is the captured knowledge, not the invocation mechanism. This
produces skills only — no agents, no orchestration.

## What comes out

```
<skills-dir>/<skill-name>/
  SKILL.md                     frontmatter + the rules that change output
  assets/                      exemplars copied from the source repo, annotated
  references/
    provenance.jsonl           every rule, its evidence, and where it came from
    rejected.md                what was tried and abandoned
    regressions.md             the Stage 4 log - next quarter's test suite
  scripts/                     checks and scaffolds with one right answer
```

That `provenance.jsonl` is what separates a skill from folklore. A rule with no row
there cannot be re-checked, re-argued, or retired — and `drift.py` cannot tell
you when the codebase moves out from under it.

## Ground rules

1. **Encode the invisible delta.** What survives is what a competent stranger
   would get wrong *and not notice*. If the build screams, the skill is
   redundant — the feedback loop already teaches it.
2. **Show shape, say reason, script right answers.** Structure → `assets/`.
   Boundaries and prohibitions → prose. Anything with one correct output →
   `scripts/`.
3. **One exemplar under-determines.** A lone sample cannot say which lines are
   contract and which are sample data. Ship two that differ, or one annotated.
4. **Record where every rule came from.** One `provenance.jsonl` row per rule,
   with its evidence and source sha. Knowledge you cannot re-verify decays into
   superstition at exactly the speed the codebase changes.
5. **No mined chunk may carry a credential, and none may carry code you cannot
   reuse.** Exemplars come out of a real repo. Scrub keys — `lint_skill.py`
   fails on key-shaped strings — and never mine vendored or third-party
   directories into an exemplar.
6. **Flag bets as bets.** Where evidence is thin, say so in the skill body in
   one line, with what would settle it. A confident invention is worse than a
   stated uncertainty.

## Stage 0 — Scope and workspace

Get these from the user before reading anything. Ask only what is missing;
assume and state the rest.

- **Target**: repo root, and the directories in scope.
- **What you'd build with it**: the artifact type this skill must generate — "a
  new service", "a new endpoint", "a new migration". This defines the skill, not
  the codebase's structure.
- **Weak spots**: what is *not* worth copying — legacy corners, mid-migration
  areas, the module everyone apologises for.
- **Beyond the code**: git history? PRs? ADRs? CI config? runbooks? **A person
  you can ask?** Their absence changes Stage 1 (see *Degraded modes* in
  `references/mining.md`).

Then make the workspace. It holds copied source and must never be committed —
`.mining/` is gitignored here for that reason:

```
.mining/<repo>-<YYYY-MM-DD>/
  reports/       survey.md conventions.md graph.md history.md interview.md
  ledger.md      from assets/evidence-ledger.template.md
  charter.md     from assets/charter.template.md
  baseline/      the no-skill generation (Stage 2)
  skilled/       the with-skill generation (Stage 4)
```

If the user names no artifact type, default to the largest live slice
`conventions.py` reports, and say that you did.

## Stage 1 — Mine

Deliverable: a ledger of candidate conventions, each with its evidence classes.
Full procedure in `references/mining.md`.

```bash
V=./.venv/Scripts/python.exe; S=.claude/skills/skill-miner/scripts
$V $S/survey.py       <root> > .mining/<ws>/reports/survey.md
$V $S/conventions.py  <root> --contradictions > .mining/<ws>/reports/conventions.md
$V $S/graph.py        <root> > .mining/<ws>/reports/graph.md
$V $S/history.py      <root> > .mining/<ws>/reports/history.md
$V $S/interview.py    <root> > .mining/<ws>/reports/interview.md
```

Read in this order, because each tells you what to skip in the next:

1. `survey.py` — shape, mass, stacks, cold zones, and what enforces things.
2. **Enforcement config first.** Anything a machine rejects is settled: no
   further evidence needed, and usually no space in the skill either.
3. `conventions.py` — SLICE (filename roles), PROLOGUE (how files open), IDIOM
   (recurring lines), BLOCK (**recurring chunks — the reusable ones**), each
   with author spread and a recency verdict.
4. `graph.py` — LAYERING (who may import whom) and WIRING (**the registry a new
   file must be added to** — the commonest silent failure there is). Neither is
   visible in any single file.
5. `history.py` — reverts, alignments, fix-density, long commit bodies. The code
   holds outcomes; only the history holds reasons.
6. `interview.py` — the questions no script can answer. Ask them.
7. Then read files: the top fix-density files, and three instances of the slice
   with dates on them.

### Is it a convention or an accident?

Frequency is not evidence — copy-paste produces frequency. A convention is
deliberate if it survived a force that would have removed an accident. Score
each candidate and require **two classes**:

| Class | Evidence | Strength |
|---|---|---|
| **Enforced** | a machine rejects the alternative — lint rule, type, CI gate, codegen | decisive alone |
| **Repaired** | a commit whose only purpose was bringing files into line (`history.py` ALIGNMENTS) | strong |
| **Reasoned** | a written argument — ADR, PR thread, long commit body, "not X because Y" | strong |
| **Confirmed** | a named person confirmed it, on a date (`interview.py`) | strong, and it expires |
| **Recent** | the newest files do it too | necessary, never sufficient |

**Author spread** is the cheapest check of all and `conventions.py` computes it:
a pattern from five authors is house style; the same pattern from one is that
person's habit. Encoding a habit propagates one person's preferences as if the
team had agreed. Below three authors in the repo, the signal says nothing.

Then invert — **the accident test**: *if this were done the other obvious way,
would anything break, or would anyone notice?* If nothing breaks and nobody
notices, it is a style fossil. Drop it.

Deviations are data. Violations nobody fixed mean it is not a convention;
violations that *were* fixed are your Repaired evidence.

### Contradictions and mid-migration

`conventions.py --contradictions` reports one role with two implementations, and
dates both sides.

- **Old dying, new growing** → encode the destination, and tripwire the origin:
  a generator reading the repo will otherwise imitate the fossil it sees most of.
- **Both live, split by area** → not a contradiction, a missing key. Find the
  observable that predicts which is used and make it a decision rule.
- **Both live, no reasoning** → the team has not decided. Don't decide for them —
  a skill that encodes the losing side of a live argument gets fought by every
  reviewer, and you find out only when people quietly stop using it. Record it
  as open, raise it with the user, encode neither.

## Stage 2 — Distill

Deliverable: a charter naming every survivor, why, and its form. Template
`assets/charter.template.md`; procedure in `references/distilling.md`.

### Run the naive baseline first

Before deciding what is non-obvious, find out. Pick an artifact that exists in
the repo, reconstruct the prompt that produced it (its ticket or PR *title and
body* — never its diff), and generate it with **no skill loaded and no repo
access**. Operationally: start a session in the empty `.mining/<ws>/baseline/`
directory, paste the prompt, save the output there. (A restricted-tool subagent
works too — that is a measuring instrument, not an agent architecture.)

**Anything the baseline already got right is not delta.** This is the only
reliable test for "genuinely non-obvious rather than merely familiar to me" —
your own sense of surprise is contaminated by knowing the answer. The baseline
is also Stage 4's control, so it is not extra work.

### The filter

|  | **Loud failure** (won't build, test fails) | **Silent** (runs, reviews clean, still wrong) |
|---|---|---|
| **Obvious** | drop | one line, no exemplar |
| **Non-obvious** | one line — the feedback loop teaches it | **the payload** |

Everything in the bottom-right earns an exemplar and a reason. A skill that is
mostly top-left is a skill that mostly burns context.

### Quirk or principle

What would this look like in another language? If the statement cannot survive
translation it is a quirk — state it as a fact, point at the exemplar, don't
dress it as a principle. If it survives, state the principle *and* its local
instantiation. **Quirks belong in exemplars, principles belong in prose.**

### Negative knowledge

"We tried X and reverted it because Y" is the highest value per token in the
pipeline — it is exactly what a capable stranger would try. Encode as a tripwire:

> **Don't** <the tempting thing> — <what happened> (<sha / PR / ADR>).
> Instead: <what to do>.

A prohibition without a reason gets overridden by a model that thinks it knows
better, or applied long after the reason expired. Keep the strongest few in the
body; the rest go in the new skill's `<skill>/references/rejected.md`.

## Stage 3 — Encode

Deliverable: the skill directory, passing `lint_skill.py`. Argument in
`references/encoding.md`. Start from `assets/SKILL.template.md`.

- **Exemplars** are copied verbatim from the source repo, then scrubbed and
  trimmed — never paraphrased. Add `<name>.notes.md`
  (`assets/exemplar.notes.template.md`) marking load-bearing lines and the
  placeholder mapping. Two exemplars that differ beat one plus prose: the diff
  between them *is* the axis of variation.
- **Chunks** from `conventions.py` BLOCK are the sub-file unit. A chunk copied
  verbatim across files is ceremony — put it in an exemplar or a script, and say
  it must appear. A chunk that varies by entity name is shape, not chunk.
- **Wiring** from `graph.py` goes in the body as an imperative naming the exact
  file to edit. This failure is silent; nothing else in the skill will catch it.
- **Decision rules** go in a flat table keyed by something observable *in the
  user's request*, with a default row and an escape hatch. Not nested. Past
  about five rows the branching is a design axis: state a principle with two
  worked examples instead.
- **Provenance**: one row per rule in the new skill's `<skill>/references/provenance.jsonl`
  (`assets/provenance.template.jsonl`). Write it as you go, not afterwards.
- **Description** is the trigger and the most common failure point:

```bash
$V $S/trigger_terms.py <root> --skill <skill-dir>   # the repo's own nouns
$V $S/lint_skill.py <skill-dir> --phrasings phrasings.txt
```

### Scope

One skill per thing you would actually build — the full vertical slice.
Splitting by concern (layering / errors / naming) is the classic mistake:
generation needs all of them at once, and split skills fire partially.

Split when the body outgrows one-shot attention, when two halves have disjoint
triggers, or when the exemplar set covers more than one target artifact.
**Split by target artifact, never by concern.** Before splitting, reach for
`references/` — a reference file loads on demand without needing to be
triggered, which is strictly safer than a second skill that may not fire.

## Stage 4 — Validate

Deliverable: a regression record in `<skill>/references/regressions.md`. Full
protocol in `references/validating.md`.

Pick a target that is recent, mid-sized, a complete slice, and has a written
prompt reconstructible from *before* it existed. Generate twice — baseline (from
Stage 2) and skilled — then:

```bash
$V $S/regen_diff.py --original <real> --baseline <base> --skilled <skilled> \
   --normalize-cmd "<the repo's formatter> {file}"    # or --normalize-builtin
```

| Reading | Diagnosis | Fix |
|---|---|---|
| baseline ≈ original | **no delta** | the target was too easy; pick a harder one |
| skilled ≈ baseline | **not firing** | the description, not the content — and don't add content |
| skilled ≠ baseline, still ≠ original | **firing, wrong** | rule mis-stated, exemplar missing, or the decision key is unobservable |
| skilled closer, gaps remain | **firing, incomplete** | additive: new exemplar or rule row |
| skilled better than original | **the original was wrong** | record it, change nothing |

Meaningful divergence — *would a reviewer on that team comment?* Yes if it
changes public surface, placement or naming, failure behaviour, a cross-cutting
ceremony, or test shape. **If a formatter would erase it, it is not a
divergence.**

**Stop** when two regenerations of *different* targets produce no new meaningful
divergences.

### Then check the set, not just the skill

```bash
$V $S/coverage.py <root> --skills <skills-dir>    # which artifact types have no skill
$V $S/drift.py <skill-dir> --source <root>        # has the repo moved since mining?
```

`coverage.py` answers "have I mined enough" — Stage 4 only answers "is this one
right". `drift.py` is the re-run: schedule it, or run it whenever generated code
starts looking subtly wrong. GONE and DRIFTED mean re-copy and re-validate;
STALE means a human confirmation has aged out and needs asking again.

A full run end to end — ledger, charter, decomposition, a filled `SKILL.md`, the
Stage 4 numbers — is in `references/worked-example.md`. Read it once first.

## Which skills come out, and in what order

Decompose by artifact, then order by how often you would invoke it. The first
skill is the vertical slice you build most; everything else is either a
variation on it (a decision-rule row, not a skill) or a rarer artifact that can
wait. After the first is validated, let `coverage.py` pick the next.

## Before trusting a run

```bash
$V $S/selftest.py    # plants one of everything in a fixture repo, checks it comes back
```

A failure there means a detector stopped detecting, and a mining run will
quietly find less than it reports.

## Bets in this pipeline

- **Description phrasing dominates firing, more than body quality.** Settled by
  the `skilled ≈ baseline` check across several phrasings.
- **Annotated exemplars beat prose for structure.** Confident about exemplars,
  less so that the annotation earns its tokens. Settled by regenerating with and
  without the notes file.
- **Author spread approximates deliberateness.** Strong in multi-author repos,
  meaningless below three; `conventions.py` says which case it is in.
- **Import-graph layering generalises.** Good for path-based imports; weaker for
  annotation-driven DI (Spring, NestJS), where the real edges are not imports.
- **Value concentrates in the non-obvious/silent quadrant.** Test it by counting
  which encoded items actually changed the regenerated output; the ones that
  changed nothing were context tax.
