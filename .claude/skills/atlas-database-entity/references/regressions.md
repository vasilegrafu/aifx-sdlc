# Regression log

The targets and prompts here are the test suite. Re-run them after the codebase
moves, after a model change, or whenever `drift.py` reports anything.

## 2026-08-04 — `database/reference_data/models/state_variable.py`

Held-out target: this file was deliberately **not** copied into `assets/`, so
the skill had never seen it. It is referenced only as a decision-table row.

- prompt: "Add a `state_variable` entity to `reference_data`: an id that is a
  name-like string key, a value, and a type." Reconstructed from the file's
  role, not from its diff.
- baseline: written before any source file in `database/` was read, in the style
  of an unfamiliar but competent SQLAlchemy 2.0 developer
  (`Base`, `int` autoincrement PK, inline `index=True`, `__repr__`, minimal
  imports, no schema).
- normalisation: `--normalize-builtin` (this repo has no formatter config)

| Comparison | First run | After fix |
|---|---|---|
| original ↔ baseline (the delta that exists) | 27.3% | 27.3% |
| original ↔ skilled (residual gap) | 98.3% | **100.0%** |
| baseline ↔ skilled (did it fire) | 47.7% | 46.8% |

Verdict both runs: **FIRING, CLOSER**.

### Meaningful divergences: 1

**The skilled output dropped `from sqlalchemy import Uuid`.** The exemplar notes
said "`Uuid` and `uuid4` drop out when the key is a natural string", which is
wrong: only the stdlib `from uuid import UUID, uuid4` line drops. The SQLAlchemy
`Uuid` import is part of the fixed prologue and appears in every model,
including `state_variable.py` itself.

- Divergence class: *structure missing / mis-stated* → edit the exemplar notes,
  and add the exception to the prose rule.
- Fixed in `assets/model_standalone.notes.md` (a table of exactly which two
  prologue lines vary) and in `SKILL.md#rules`.
- Re-ran: 100.0%.

This is the divergence the exemplar *invites* — one sample cannot show which
absence is meaningful, which is the whole argument for the notes file. It is
worth keeping as the canonical example of why a lone exemplar under-determines.

### Acceptable variation: 1

`stock_instrument.py` has no blank line before
`from database.base_database_model import BaseDatabaseModel`; the other two do.
A formatter would erase it, so it is not a divergence.

## Not yet regenerated

- **A controller.** Only the model half has been regenerated. The controller
  surface is larger and more likely to hold gaps, so it is the next target.
- **A second, different target** — the stop rule needs two consecutive clean
  regenerations of *different* artifacts, and only one has run.

## Known weakness of this run

The baseline and skilled arms were produced in the same session that wrote the
skill. The baseline was written before any source file was read, which protects
it, but a genuinely independent arm needs a separate session. Treat 27.3% as a
good-faith measure of the delta, not a controlled result.
