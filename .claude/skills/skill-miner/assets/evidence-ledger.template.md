# Evidence ledger — <repo> <scope>

Working file for Stage 1. Not shipped with the skill. One row per candidate
convention; two evidence classes required to survive into Stage 2 (Enforced
counts as two by itself; Recent never survives alone).

## Candidates

| # | Claim (one sentence) | Example | Enf | Rep | Rea | Rec | Accident test: if done the other way… | Survives |
|---|---|---|---|---|---|---|---|---|
| 1 | <what is done> | `path:line` | ✓/– | ✓/– | ✓/– | ✓/– | <breaks / nobody notices> | yes/no |
| 2 |  |  |  |  |  |  |  |  |

- **Enf**orced — a machine rejects the alternative. Cite the rule.
- **Rep**aired — a commit exists whose only purpose was bringing files into
  line. Cite the sha.
- **Rea**soned — a written argument exists. Cite ADR / PR / commit body.
- **Rec**ent — the newest files in the repo do it too.

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

## Cold zones

Directories with no recent commits — do not mine, they encode a past house style.

- `<path>` — last touched <date>

## Open questions for the user

- <question that changes what gets encoded>
