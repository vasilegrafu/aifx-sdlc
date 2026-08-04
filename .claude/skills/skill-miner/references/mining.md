# Stage 1 — Mine

Read for *outcomes* in the code and *reasoning* everywhere else. Code records
what was decided; it never records what was rejected, and the rejected branch is
usually the more valuable one.

## Reading order, and what each source yields

Each step tells you what to skip in the next. Do not read files in alphabetical
order, ever.

### 1. Enforcement config — before any source file

`.eslintrc*`, `ruff.toml` / `setup.cfg` / `pyproject.toml`, `tsconfig.json`,
`.editorconfig`, `.pre-commit-config.yaml`, `Makefile`, CI workflow files,
`CODEOWNERS`, custom lint rules, codegen templates, git hooks.

Yield: the settled conventions, at zero evidential cost. A rule a machine
enforces needs no further proof and — importantly — usually needs **no space in
the skill either**, because the generator's output gets corrected by the same
machine. Encode enforced rules only when violating them is expensive to discover
(a CI run away rather than a save away).

Also yield: the *normalisation command* you will need in Stage 4. Note it now.

### 2. `survey.py` — where the mass is

Ranks directories by file count and by lines, lists manifests, spots test
layout, dates the tree from git.

Read the output for: which directory is the repeated unit (many sibling
subdirectories with similar file counts = a slice), which is the junk drawer
(one enormous `utils`), and which parts are cold (no commits in a year — do not
mine cold code, it encodes a past house style).

### 3. `conventions.py` — candidate shapes

Three independent signals, each reported with spread (how many directories) and
recency (share of files touched in the last year):

- **Slice shape** — filename suffix sets that co-occur in a directory
  (`*.service.ts` + `*.repo.ts` + `*.test.ts`). This is the skeleton of the
  vertical slice and usually becomes the exemplar set directly.
- **Prologue** — the recurring opening lines of files of a given type: import
  blocks, logger construction, license headers, module setup. Cheap, high-yield;
  a generated file with the wrong prologue reads as foreign immediately.
- **Idiom** — normalised lines recurring across many files *and* many
  directories. Spread across directories is what separates an idiom from one
  author's habit.

`LIVE` / `MIXED` / `FOSSIL` in the output is a recency verdict, not a
deliberateness verdict. It tells you what to investigate, not what to encode.

### 4. `history.py` — where the reasoning is

Reverts, fix-density per file, commits with long bodies, and files that keep
coming back.

- **Reverts** are the single richest vein. Each is a hypothesis the team tested
  in production. `git show <sha>` on the revert and its parent gives you both
  the tempting approach and the reason it failed.
- **Fix-density** ranks files by how often they appear in fix/bugfix/hotfix
  commits. High density means either the file is load-bearing (mine it) or
  chronically broken (do not). Read three commits to tell which.
- **Long commit bodies** are where a team without ADRs writes its ADRs.
- **Files that keep coming back** after their author left are the ones the house
  style congealed around.

### 5. Prose sources

ADRs, `docs/`, runbooks, PR discussions on the highest-fix-density files, review
comments, `CONTRIBUTING.md`.

What to look for, in order of value: *rejected alternatives* > *stated
constraints* ("must stay under X ms", "must not depend on Y") > *stated
preferences* > *aspirations*. Aspirations are worth nothing — a document
describing how the team wishes it built things is not evidence about how it
does, and the code will contradict it.

### 6. Only now, source files

Read the exemplar candidates end to end — the newest complete instance of the
slice, the one before it, and one older one. Three files with dates on them tell
you the direction of travel, which no single file can.

## The evidence ledger

One row per candidate. Copy `assets/evidence-ledger.template.md`. Do not skip
this into your head: the ledger is what makes Stage 2 a filter rather than a
recollection.

Required per row: the claim in one sentence, an example file:line, the evidence
classes met (Enforced / Repaired / Reasoned / Recent), the accident-test answer,
and any contradiction found.

Two classes required to survive. Enforced counts as two by itself. Recent alone
never survives — "everyone does it and it is still being written" is exactly
what a well-propagated copy-paste looks like.

## Finding the repairs

Repaired evidence is the hardest to find and the most convincing. Look for
commits that touch many files with a small diff each and a subject like
"align", "consistent", "standardise", "migrate", "cleanup". `history.py` lists
wide-and-shallow commits for this reason. Each one is a moment when someone
decided a pattern mattered enough to spend an afternoon on.

The inverse is also evidence: a wide-and-shallow commit that was *reverted* means
the team decided the pattern did **not** matter. Record that as negative
knowledge, it will save the generator from being tidier than the team wants.

## Mid-migration detection

Symptoms: two ways of doing the same job; a directory whose files split cleanly
by date; a shim, adapter, or `*_v2` name; a dependency present in the manifest
but imported in only a few files (arriving) or imported widely but absent from
recent files (leaving).

Date both sides with `conventions.py --contradictions`, which reports candidate
pairs that occupy the same role and their first/last-touch spread. Then apply
the rule in `SKILL.md`: encode the destination, tripwire the origin, or refuse
to decide and say so.

The refusal case matters. A skill that confidently encodes the losing side of a
live argument will be fought by every reviewer on the team, and you will not
find out until someone silently stops using it.

## Scoping to named directories

When the user names directories rather than a whole repo, pass them to every
script (`--include`). Two cautions:

- Enforcement config lives at the root, outside the named scope. Read it anyway.
- Git history is repo-wide; filter by path when ranking, not when reading. A
  revert in a neighbouring directory can still be the reason your directory
  looks the way it does.
