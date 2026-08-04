# `model_standalone.py` — what is contract, what is sample

## Source

Copied verbatim from `solution.atlas:database/reference_data/models/stock_instrument.py`
on 2026-08-04. Nothing removed; the file carries no credentials.

Its pair is `model_with_fk.py` (`market_data/models/stock_candlestick.py`). The
two differ along **one axis: whether the entity references another entity.**
That diff is the specification of what varies — read both before writing one.

## Load-bearing — reproduce these

| Lines | What must hold | Why |
|---|---|---|
| 1–15 | the whole import block, verbatim, **including names this model does not use** | it is a fixed prologue in all three models; trimming it to what you use makes the file read as foreign |

Exactly two lines of the prologue vary, and nothing else does:

| Line | Varies how |
|---|---|
| `from uuid import UUID, uuid4` | present only when the primary key is a UUID. `state_variable.py` has a `String` key and omits it |
| `from sqlalchemy import ForeignKey, ForeignKeyConstraint` | the plain `ForeignKeyConstraint` form is default; `ForeignKey` joins it only in a model that declares one (`model_with_fk.py`) |

`from sqlalchemy import Uuid` stays in **every** model, including ones with a
string key. It is part of the fixed block, not part of the key decision —
dropping it alongside `uuid4` is the one mistake this exemplar invites, and the
regeneration in `references/regressions.md` made exactly it.
| 16 | `from database.base_database_model import BaseDatabaseModel` | the base is `BaseDatabaseModel`, never `Base` |
| 18 | `# ----------------------------------------------------------------` before the class | separator that appears above every class and every method group |
| 20 | `class <Entity>(BaseDatabaseModel):` | |
| 21 | `__tablename__` equals the module stem | the rename in `5b1401b3` made table-per-instrument-type the rule |
| 22–25 | `__table_args__` tuple, **`{'schema': '<domain>_data'}` last** | without it the table lands in `dbo`; `create_schemas()` then builds an empty schema beside it and nothing errors |
| 23 | `Index('idx__<table>__<column>', '<column>', unique=True)` | indexes are declared in `__table_args__`, never as `index=True` on the column |
| 27 | `id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)` | surrogate key default; `state_variable.py` shows the natural-key exception |

## Sample data — change these freely

| Lines | What it is |
|---|---|
| 29–33 | the entity's own columns |
| the string lengths | per field; `String(8)` for codes, `String(256)` for names, `String(2048)` for prose |

## Placeholders

| In the exemplar | Stands for |
|---|---|
| `StockInstrument` | `<Entity>` in PascalCase |
| `stock_instrument` | `<entity>` in snake_case — module stem **and** `__tablename__` |
| `reference_data` | the domain package the entity belongs to |
| `ticker_symbol` | the entity's natural business key, if it has one |

## Deliberately absent

An exemplar cannot show an absence, so these are stated:

- **No `__repr__`.** None of the three models defines one. Adding one is the
  single most likely unprompted addition, and it does not belong.
- **No type hints beyond `Mapped[...]`,** and no docstrings on the class.
- **No `nullable=`.** Optionality is expressed as `Mapped[Optional[str]]` using
  `typing.Optional`, not `str | None` and not `nullable=True`.
- **No `back_populates` / `relationship()` in any current model** even though
  `relationship` is imported by the prologue. The FK is declared and left at
  that.
