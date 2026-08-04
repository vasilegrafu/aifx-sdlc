# Evidence ledger — <repo> <scope>

Working file for Stage 1. Lives in `.mining/<repo>-<date>/ledger.md`, not in the
skill. Surviving rows become `references/provenance.jsonl` rows in Stage 3 —
same evidence, machine-readable, and that file *is* shipped.

Evidence mode for this repo: <full / no git / squashed / no docs / solo — see
Degraded modes in references/mining.md>. One row per candidate
convention; two evidence classes required to survive into Stage 2 (Enforced
counts as two by itself; Recent never survives alone).

## Candidates

| # | Claim (one sentence) | Example | Authors | Enf | Rep | Rea | Con | Rec | Accident test: if done the other way… | Survives |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | <what is done> | `path:line` | n of N | ✓/– | ✓/– | ✓/– | ✓/– | ✓/– | <breaks / nobody notices> | yes/no |
| 2 |  |  |  |  |  |  |  |  |  |  |

- **Enf**orced — a machine rejects the alternative. Cite the rule.
- **Rep**aired — a commit exists whose only purpose was bringing files into
  line. Cite the sha.
- **Rea**soned — a written argument exists. Cite ADR / PR / commit body.
- **Con**firmed — a named person confirmed it, on a date. Record both; this is
  the only class that expires (`drift.py --stale-days`).
- **Rec**ent — the newest files in the repo do it too.

**Authors** is `conventions.py`'s author spread: how many distinct people wrote
files exhibiting this, out of how many in the repo. One of many is a habit, not
a convention. Below three authors in the repo, leave it blank — the number says
nothing there.

## Evidence pointers

| # | Class | Pointer | What it says |
|---|---|---|---|
| 1 | Reasoned | `<sha>` / PR #<n> | <the argument in one line> |

## Negative knowledge

Tried and reverted, considered and rejected, used to be done that way.

| Temptation | What happened | Pointer |
|---|---|---|
| <the approach a stranger would take> | <the consequence> | `<sha>` / PR / ADR |

## Contradictions

| Role | Side A | first/last touch | Side B | first/last touch | Reasoning found? | Ruling |
|---|---|---|---|---|---|---|
| <what both do> | <pattern> | <dates> | <pattern> | <dates> | <ADR? PR?> | encode A / encode B / **open — do not encode** |

Rulings: encode the destination and tripwire the origin; or, if both are live
with no reasoning and no area-split, encode neither and raise it with the user.

## Wiring (from `graph.py`)

What a new artifact must be added to, and what happens if it is not. These fail
silently, so they belong in the skill body even when the evidence is thin.

| New artifact | Must also be added to | Failure if forgotten |
|---|---|---|
| `<type>` | `<registry path>` | <unreachable / not registered / no route> |

## Layering (from `graph.py`)

| Direction | Verdict | Encode as |
|---|---|---|
| `<a> → <b>` | ONE WAY / DOMINANT / TANGLED | rule / rule + named exceptions / nothing |

## Chunks (from `conventions.py` BLOCK)

Verbatim runs worth carrying into an exemplar or a script.

| Chunk (first line) | Files | Authors | Deliberate? | Goes to |
|---|---|---|---|---|
| `<line>` | n | n | asked / assumed | `assets/<f>` / `scripts/<f>` / dropped |

## Cold zones

Directories with no recent commits — do not mine, they encode a past house style.

- `<path>` — last touched <date>

## Open questions for the user

- <question that changes what gets encoded>
