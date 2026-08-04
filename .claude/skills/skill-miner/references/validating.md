# Stage 4 — Validate

Regenerate something that already exists, diff it against the real thing, and
convert each surviving difference into a specific edit. Every meaningful
divergence is either a gap in the skill or a place the original was wrong, and
you must decide which — those have opposite fixes.

## Choosing the target

Four properties, in priority order:

1. **Recent.** It must post-date the conventions you encoded. Regenerating a
   three-year-old file measures your skill against a house style that no longer
   exists and reports failure for being right.
2. **Prompt-reconstructible.** There must be a ticket, PR description or issue
   written *before* the artifact, which you can use as the generation prompt.
   Without it you will write the prompt from the file and leak the answer — the
   most common way this test gets faked.
3. **A complete slice.** The whole unit the skill claims to generate, including
   its test file and registration. A partial target validates a partial skill.
4. **Mid-sized and ordinary.** Not the flagship 2000-line module, not the
   trivial one. The flagship is atypical and the trivial one has no shape to get
   wrong.

Bonus property: written by someone who is not the skill's author. A target
written by the person doing the mining validates their memory, not the skill.

## The three generations

Always two arms, giving three comparisons:

- **baseline** — no skill, no repo access. Reuse the one from Stage 2.
- **skilled** — the skill loaded, still no repo access. *No repo access* is not
  optional: a generator that can read the repo will copy the neighbouring file
  and the test measures nothing.

| Comparison | What it measures |
|---|---|
| original ↔ baseline | the delta that actually exists — the size of the job |
| original ↔ skilled | the residual gap — what is still missing |
| **baseline ↔ skilled** | **whether the skill did anything at all** |

The third is the one people skip, and it is the one that separates a wrong skill
from a silent one.

## Normalising before reading

Run the repo's own formatter and autofixer over all three files first
(`--normalize-cmd`). Anything a formatter erases was never a divergence, and
unnormalised diffs are 80% noise — which is how validation sessions turn into
whitespace archaeology and get abandoned.

If the repo has no formatter, `--normalize-builtin` strips comments, blank lines
and indentation. It is cruder and it is still worth it: comment wording and
whitespace are the two things a real divergence is never about.

```bash
./.venv/Scripts/python.exe .claude/skills/skill-miner/scripts/regen_diff.py \
  --original src/orders/order.service.ts \
  --baseline  out/baseline/order.service.ts \
  --skilled   out/skilled/order.service.ts \
  --normalize-cmd "npx prettier --write {file}" --md
```

The script reports similarity across the three pairs, a declaration-level shape
diff (what exists in one file and not the other), and the raw unified diffs. It
does not classify divergences — that is judgment, and pretending otherwise
produces confident nonsense.

## Meaningful divergence vs. acceptable variation

The test: **would a reviewer on that team leave a comment?**

Meaningful — it changes:

- the **public surface**: exported names, signatures, the shape of what callers
  get back;
- **placement and naming**: which file, which directory, what the file is called;
- **failure behaviour**: what is thrown or returned, what is caught, what is
  retried, what is logged on the way out;
- a **cross-cutting ceremony**: auth, transactions, telemetry, feature flags,
  validation — where it goes and whether it is there at all;
- **test shape**: what is tested, at what level, with what doubles.

Acceptable — do not chase:

- internal statement ordering with no dependency between the statements;
- local variable names, comment wording, string wording;
- anything a formatter or autofix would change;
- an equivalent-cost algorithmic choice inside one function;
- extra or missing inline comments.

Grey zone, decide once and record the decision in `references/regressions.md` so
it does not get re-litigated: helper extraction, the exact granularity of
functions, and how much gets inlined.

## Reading the three comparisons

| Reading | Diagnosis | Fix |
|---|---|---|
| baseline ≈ original (before anything else) | **no delta** | the target proves nothing — a stranger already produced it. Pick a harder target; if every target reads this way, the skill may have nothing to encode |
| skilled ≈ baseline (high similarity, same divergences) | **not firing** | rewrite the description; check whether the rule sits below the attention budget; check name/frontmatter validity |
| skilled ≠ baseline, but no closer to original | **firing, wrong** | the rule is mis-stated, its decision key is not observable, or the exemplar shows the wrong thing |
| skilled closer, specific gaps remain | **firing, incomplete** | additive edits only |
| skilled ≠ original, and skilled is better | **the original was wrong** | record it in the ledger, change nothing, tell the user |

Do not fix a not-firing skill by adding content. It is the commonest wasted day
in this pipeline: the body gets longer, firing stays broken, and the added
content makes the next diagnosis harder. Description first, always, then re-run.

## Divergence → edit

| Divergence | Edit | Why that form |
|---|---|---|
| structure missing or in the wrong order | extend an exemplar, or add a second one | shape belongs in `assets/` |
| picked a valid alternative, but not this repo's | add a decision-rule row with an observable key | the skill had no way to choose |
| invented a helper, module or convention that does not exist | tripwire in the body, with the real thing named | prohibitions cannot be shown |
| right thing, wrong place or name | one prose fact + a scaffold script | placement is deterministic |
| output differs run to run | move it into `scripts/` | nondeterminism means it was under-specified |
| skilled output is worse than baseline | remove the rule that caused it | some encoded knowledge is actively harmful |

That last row is real and worth watching for. An over-specified rule can
suppress a good instinct the model already had.

## Stopping

Stop when **two consecutive regenerations of different targets produce no new
meaningful divergences.** One clean run means you fixed that file; two on
different targets means the skill generalises.

Also stop, temporarily, when the same divergence resists three edit attempts.
That item is either unencodable in prose (make it a script), or actually a
contradiction in the source repo that Stage 1 missed. Go back and date both
sides rather than escalating the wording.

## Two questions Stage 4 does not answer

Regeneration tells you whether *this skill* is right. It says nothing about
whether the set is complete, or whether either is still true next quarter.

### Is the set complete? — `coverage.py`

```bash
python coverage.py <repo> --skills <skills-dir>
```

Lists the repo's live artifact types against the skills that name them, ranked
by how much live code each uncovered type represents. The top uncovered row is
the next skill to build — unless nobody would ever ask for it, which is a
legitimate answer and worth writing down so the row stops coming back.

Matching is lexical, deliberately: a type counts as covered when a skill *names*
it, which is the same condition as the skill triggering at all. A skill that
covers migrations without ever using the word does not, in practice, cover them.

### Is it still true? — `drift.py`

```bash
python drift.py <skill-dir> --source <repo>
```

Skills rot silently and read exactly as convincing on the day they stop being
right. Against the recorded provenance it reports:

- **GONE** — the source file is deleted. The rule may have been retired with it;
  check before re-copying anything.
- **DRIFTED** — the source changed materially since the exemplar was copied.
  Re-copy, then re-run Stage 4: the divergence you get is the codebase moving,
  not the skill being wrong.
- **EVIDENCE?** — the cited commit is missing or was itself reverted. The
  argument behind the rule may no longer hold.
- **STALE** — a `Confirmed` item has aged past `--stale-days`. Ask again; the
  person may have left and the constraint may have lapsed.

Exit code 1 on GONE or DRIFTED, so it can gate a scheduled run. The natural
cadence is quarterly, or whenever generated code starts looking subtly foreign.

## The regression record

Append to `references/regressions.md` for every run:

```markdown
## <date> — <target path>
- prompt source: <ticket / PR>, reconstructed from <what>
- normalisation: <command>
- similarity: orig↔base <x>, orig↔skilled <y>, base↔skilled <z>
- meaningful divergences: <n> — <one line each>
- edits made: <list, with the row of the divergence→edit table used>
- grey-zone rulings: <any>
- verdict: firing / not firing / wrong / clean
```

This is what makes the pipeline repeatable next quarter: the targets and their
prompts are the test suite, and re-running them after a model change or a
codebase drift tells you whether the skill still works, in one afternoon rather
than one rediscovery.
