# Skill charter — <skill-name>

Working file for Stage 2. Decides what survives and in what form, before any
skill file is written.

## The one thing

This skill generates: <artifact type — the thing someone sits down to build>.

Triggered by phrasings like: <five you would actually type>.

Not this skill's job: <the neighbouring artifact that will be its own skill>.

## Baseline result

- Target used: `<path>`
- Prompt reconstructed from: <ticket / PR>, written before the artifact: yes/no
- Baseline got **right** (therefore not delta): <list — be honest, this list
  should be long>
- Baseline got **wrong loudly** (build/test would catch): <list — one line each
  in the skill, or nothing>
- Baseline got **wrong silently**: <list — **this is the payload**>

## Survivors

| # | Item | Quadrant | Quirk/Principle | Form | Where |
|---|---|---|---|---|---|
| 1 | <one sentence> | non-obvious/silent | quirk | exemplar | `assets/<f>` |
| 2 |  |  |  |  |  |

Forms: exemplar · prose · decision-row · script · reference · dropped.

## Dropped, and why

| Item | Reason |
|---|---|
| <ledger row> | obvious — baseline produced it |
| <ledger row> | loud — the compiler says it |
| <ledger row> | fossil — failed the accident test |

## Exemplar plan

| File | Source path in repo | Pair or notes? | Scrubbed? |
|---|---|---|---|
| `assets/<canonical>` | `<repo path>` | pairs with `<other>` / `.notes.md` | yes/no |

Pairs differ along: <the one axis of variation they demonstrate>.

## Decision rules

| Key (observable in the request) | Outcome | Exemplar |
|---|---|---|
|  |  |  |

Default row: <which>. Escape hatch wording: <…>.

## Scripts

| Script | One right answer it computes | Replaces which prose instruction |
|---|---|---|

## Budget

Target body length: <lines>. If over: cut from the obvious/loud quadrant first,
never from negative knowledge.

## Checkpoint

- Three items whose removal would most degrade output: <1> <2> <3>
- Items that came from the baseline diff rather than my own judgment: <n>
- Bets to state in the body: <list, each with what would settle it>
