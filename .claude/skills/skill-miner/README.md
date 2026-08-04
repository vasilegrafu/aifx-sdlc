# skill-miner — how to use it

Operator instructions. The *reasoning* behind the pipeline is in `SKILL.md` and
`references/`; this file is the manual.

## Two ways in

**Ask for it.** The skill triggers on the phrasings you would naturally use:

> mine `D:/work/platform` into a skill for building services
> extract the conventions from `services/` so I can generate new ones
> turn this repo into a skill pack
> is the `acme-http-service` skill still current?

You will be asked for scope first (see *Stage 0* below). Then the skill runs the
scripts, reads the reports, and writes the new skill.

**Run the scripts yourself.** Every script is standalone, standard-library only,
and prints Markdown to stdout. Useful when you want the evidence without the
skill-writing, or when you are auditing a run.

```bash
V=./.venv/Scripts/python.exe          # NOT bare python
S=.claude/skills/skill-miner/scripts
$V $S/survey.py <repo>
```

The blocks below are POSIX shell (Git Bash). In PowerShell the same two lines
are:

```powershell
$V = ".\.venv\Scripts\python.exe"
$S = ".claude\skills\skill-miner\scripts"
& $V $S\survey.py <repo>
```

Everything after that is identical — same flags, same output. Redirect with `>`
in either shell.

## Prerequisites

| Need | Why | Without it |
|---|---|---|
| `./.venv/Scripts/python.exe` | bare `python` on this machine lacks the repo's deps | first import fails |
| a git repo as the target | dating, authorship, reverts, repairs | most of Stage 1 degrades — see *Degraded modes* in `references/mining.md` |
| the target's formatter command | Stage 4 diff normalisation | pass `--normalize-builtin` instead |
| someone to ask | the `Confirmed` evidence class | contradictions stay unresolved; record them as open |

Nothing is installed and nothing is written into the target repo. All scripts
read only.

## Stage 0 — set up the workspace

Mining copies code out of another repository. That output must never be
committed, which is why `.mining/` is gitignored here.

```bash
WS=.mining/platform-$(date +%F)
mkdir -p $WS/reports $WS/baseline $WS/skilled
cp .claude/skills/skill-miner/assets/evidence-ledger.template.md $WS/ledger.md
cp .claude/skills/skill-miner/assets/charter.template.md         $WS/charter.md
```

Decide and write down: the repo root, the directories in scope, **the artifact
type you want to generate** ("a new service", "a new endpoint"), which corners
are not worth copying, and whether a person is available to ask.

## Stage 1 — mine

```bash
R=/path/to/repo
$V $S/survey.py      $R                   > $WS/reports/survey.md
$V $S/conventions.py $R --contradictions  > $WS/reports/conventions.md
$V $S/graph.py       $R                   > $WS/reports/graph.md
$V $S/history.py     $R                   > $WS/reports/history.md
$V $S/interview.py   $R                   > $WS/reports/interview.md
```

Read them in that order — each says what to skip in the next.

| Script | Answers | Look for |
|---|---|---|
| `survey.py` | what is here, what enforces it, what is cold | the repeated directory (your slice), the junk drawer, `Enforcement` — read those files first |
| `conventions.py` | SLICE, PROLOGUE, IDIOM, **BLOCK** | the co-occurring filename set (your exemplars), and blocks with high author spread (your reusable chunks) |
| `graph.py` | **LAYERING**, **WIRING** | `ONE WAY` directions to encode; the top registry file — a new artifact must be added to it, and that failure is silent |
| `history.py` | reverts, alignments, fix density, reasoned commits | reverts first: each is a hypothesis the team paid to test |
| `interview.py` | the questions no script can answer | ask them, then record answers as `Confirmed` with a name and a date |

Useful flags:

- `--include src --include lib` — scope to directories (repeatable). Root
  enforcement config is still reported.
- `--depth 3` on `survey.py`/`graph.py` — deeper rollup for monorepos, where
  depth 2 collapses everything into one bucket.
- `--months 60` on `history.py`/`interview.py` — widen the window on a slow repo.
- `--min-files 2` on `conventions.py` — a small codebase where nothing repeats
  three times yet.
- `--json` — machine-readable, on everything except `interview.py`.

Fill in `$WS/ledger.md` as you read. **Two evidence classes required** to
survive; `Enforced` counts as two; `Recent` never survives alone.

## Stage 2 — distill

Run the naive baseline *before* judging what is non-obvious:

1. Pick an artifact in the repo and reconstruct its prompt from the ticket or PR
   **title and body** — never the diff.
2. Start a session in the empty `$WS/baseline/`, paste the prompt, save the
   output there. No skill, no repo access. (A restricted-tool subagent works
   too; it is a measuring instrument, not an agent architecture.)
3. Anything the baseline already got right is **not** delta. Cross it off.

Fill in `$WS/charter.md`: what survives, in what form, and its provenance id.

## Stage 3 — encode

Write the skill directory. Start from `assets/SKILL.template.md`; annotate
exemplars with `assets/exemplar.notes.template.md`; record every rule in
`references/provenance.jsonl` (`assets/provenance.template.jsonl`) **as you go**.

```bash
# what the repo's own nouns are, and which the description already names
$V $S/trigger_terms.py $R --skill <skill-dir>

# the gate: frontmatter, dead paths, credentials, provenance, exemplar hygiene
$V $S/lint_skill.py <skill-dir> --phrasings phrasings.txt
```

`phrasings.txt` is ten requests you would actually type, one per line, including
two lazy ones. Lexical overlap is a proxy; the real proof is Stage 4.

**`lint_skill.py` exits 1** on anything unusable or unsafe — bad frontmatter, a
body path that does not exist, a credential-shaped string, malformed provenance.
Warnings (exit 0) are quality: thin description, lone exemplar, prohibition with
no reason, decision table with no default row.

## Stage 4 — validate

Generate the same target twice — baseline (Stage 2) and skilled — then:

```bash
$V $S/regen_diff.py \
  --original $R/services/orders/create.ts \
  --baseline $WS/baseline/create.ts \
  --skilled  $WS/skilled/create.ts \
  --normalize-cmd "npx prettier --write {file}"   # or --normalize-builtin
```

The verdict line is the point:

| Verdict | Means | Do |
|---|---|---|
| `NO DELTA` | the baseline already matched — target too easy | pick a harder target |
| `NOT FIRING` | skilled ≈ baseline; the skill never loaded | fix the **description**, not the content |
| `FIRING, WRONG` | it changed the output, but not toward the original | the rule is mis-stated or its key is unobservable |
| `FIRING, CLOSER` | it moved toward the original | additive edits for what remains |
| `FIRING, WORSE` | it moved away | remove the rule that caused it |
| `NO BASELINE` | you omitted `--baseline` | you cannot tell wrong from silent; generate it |

Add `--full-diff` for the raw diffs, `--json` for scripting. Stop when two
regenerations of *different* targets produce no new meaningful divergences, and
log each run in the skill's `references/regressions.md`.

## Afterwards — keeping it true

```bash
# which artifact types still have no skill; the top row is the next one to build
$V $S/coverage.py $R --skills .claude/skills

# has the repo moved since mining? exits 1 on GONE or DRIFTED
$V $S/drift.py <skill-dir> --source $R --stale-days 365
```

`drift.py` statuses: **GONE** (source deleted — the rule may have gone with it),
**DRIFTED** (re-copy the exemplar, then re-run Stage 4), **EVIDENCE?** (the cited
commit is missing or was reverted), **STALE** (a human confirmation has aged
out — ask again). Quarterly is a reasonable cadence, or whenever generated code
starts looking subtly foreign.

## Before trusting a run

```bash
$V $S/selftest.py          # add --keep to inspect the fixture repo afterwards
```

Builds a throwaway git repo with one planted instance of everything the pipeline
claims to find, then checks each comes back. A failure means a detector stopped
detecting, and a mining run will quietly find less than it reports. Run it after
changing any script, and after a Python upgrade.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError` on first import | bare `python` | use `./.venv/Scripts/python.exe` |
| `history.py` exits 1, "not a git repository" | no history to mine | expected; see *Degraded modes* |
| "no commits in window" | window too narrow | `--months 60` |
| `conventions.py` reports nothing | small or young repo | `--min-files 2` |
| Layering table is empty | rollup too shallow for a monorepo | `--depth 3` or `--depth 4` |
| Everything is `LIVE` and nothing separates | recency window too wide | `--recent-days 180` |
| Author spread is all `1` | solo repo | expected — the script says so; lean on enforcement and the accident test |
| `graph.py` shows external packages you know are internal | import root is unusual | check they are not ambiguous directory names; unresolved beats fabricated |
| Regeneration always says `NO DELTA` | targets too easy, or nothing to encode | try a target whose ticket is vague and whose result is opinionated |

## Files in this skill

- `SKILL.md` — the procedure and the reasoning. Loaded when the skill triggers.
- `references/` — `mining.md`, `distilling.md`, `encoding.md`, `validating.md`
  (the deep argument for each stage) and `worked-example.md` (a full run,
  end to end — read it once before your first).
- `assets/` — templates: the skill skeleton, evidence ledger, charter, exemplar
  notes, provenance.
- `scripts/` — everything above. `_common.py` is shared helpers, not a command.
