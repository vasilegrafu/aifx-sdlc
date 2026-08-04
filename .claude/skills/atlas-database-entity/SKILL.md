---
name: atlas-database-entity
description: Add an entity to the atlas database layer in solution.atlas the way this codebase does it — the SQLAlchemy model, its DbCtrl controller, and the imports that make the table actually get created. Use when adding, changing or reviewing anything under database/, adding a table, model, entity, or DbCtrl; when working in reference_data, market_data, fundamental_data, analyst_data, economic_data, derivative_data, alternative_data or user_data; when writing a mapped_column, __table_args__, a schema-qualified table, an Index on a model, or a StandardDbCtrl query; when adding an instrument, candlestick or any <type>_instrument / <type>_candlestick pair; when a new table did not appear after running database_generator; or when asked to make a model or controller match the rest of the atlas database layer.
---

# Entities in the atlas database layer

Generates one entity: a model under `database/<domain>_data/models/` and a
controller under `database/<domain>_data/controllers/`.

## Start here

Read both models before writing one. They differ along **one axis — whether the
entity references another entity** — and that difference is the specification of
what varies.

- `assets/model_standalone.py` — the default (`reference_data/stock_instrument`)
- `assets/model_with_fk.py` — same shape with a foreign key and several indexes
  (`market_data/stock_candlestick`)
- `assets/controller.py` — the full controller surface; take only the methods
  the entity needs
- `assets/model_standalone.notes.md`, `assets/controller.notes.md` — which lines
  are contract and which are sample data

Copy the structure, not the domain nouns.

## The thing that fails silently

A model becomes a table only because something imports it:

```
database_generator.generate()
  -> import database.<domain>_data           # database_generator.py
  -> from .models import *                   # <domain>_data/__init__.py
  -> from .<entity> import <Entity>          # <domain>_data/models/__init__.py
  -> the class body registers on BaseDatabaseModel.metadata
  -> metadata.create_all(engine)
```

Break any link and **nothing fails**. The module imports, the controller
imports, everything that touches the class works — and the table is simply never
created. It surfaces much later as a runtime error against a database that looks
healthy.

So, after writing the two files, edit two more:

1. `database/<domain>_data/models/__init__.py` — add
   `from .<entity> import <Entity>`
2. `database/<domain>_data/controllers/__init__.py` — add
   `from .<entity>_dbctrl import <Entity>DbCtrl`

A **new domain** additionally needs `import database.<domain>_data` in
`database/database_generator.py` and its name in that file's `SCHEMAS` list.
Adding an entity to an existing domain does not.

## Choose

| If the entity… | Then | Exemplar |
|---|---|---|
| has a natural string key (a name, a code) | `id: Mapped[str] = mapped_column(String(256), primary_key=True)` | `reference_data/models/state_variable.py` |
| references another entity | `ForeignKey('<domain>_data.<table>.id', ondelete='CASCADE')`, plus an `Index` per lookup path | `assets/model_with_fk.py` |
| neither | UUID surrogate key, `mapped_column(Uuid, primary_key=True, default=uuid4)` | `assets/model_standalone.py` (the default) |

If none match, follow `assets/model_standalone.py` and say in your output that
you did.

## Rules

- The base class is `BaseDatabaseModel`, never `Base`.
- `__table_args__` ends with `{'schema': '<domain>_data'}`. Without it the table
  lands in `dbo` while `create_schemas()` builds an empty schema beside it, and
  nothing errors.
- `__tablename__` equals the module stem. One table per instrument type, not one
  generic table with a type column (`5b1401b3`).
- Indexes go in `__table_args__` as `Index('idx__<table>__<col>', '<col>')` —
  double underscores, table name first, columns in order. Never `index=True` on
  the column.
- Controllers are all `@staticmethod` + `@session_injector`, `session` first.
  There is no `__init__` and no instance state in this layer.
- Every query goes through `StandardDbCtrl(session).select(...)`. Raw `select()`
  or `session.scalars()` appears nowhere here.
- Controllers import their model as `from ..models import <Entity>` — through
  the barrel, relative.
- Models carry `Mapped[...]` types; controllers carry no type hints at all. That
  split is deliberate.
- Reproduce the model import prologue verbatim, including names the file does
  not use. Only two lines vary: `from uuid import UUID, uuid4` appears only with
  a UUID key, and `ForeignKey` joins `ForeignKeyConstraint` only in a model that
  declares one. `from sqlalchemy import Uuid` stays even when the key is a
  string.

## Don't

> **Don't** give a new instrument type a shared supertype table, or reuse a
> generic `candlestick` table with a type column — `5b1401b3` renamed
> `candlestick` to `stock_candlestick` to end exactly that. Instead: each type
> gets its own `<type>_instrument` / `<type>_candlestick` pair, joined by a FK
> with `ondelete='CASCADE'`.

> **Don't** add `__repr__`, docstrings, `nullable=`, or `relationship()` to a
> model. None of the three existing models has any of them; `relationship` is
> imported by the prologue and deliberately unused.

> **Don't** open, commit or refresh a session in a controller — `@session_injector`
> and `StandardDbCtrl` own the transaction, and a controller that commits will
> double-commit inside an injected session.

> **Don't** copy `StockCandlesticksDbCtrl` as a naming model — it is plural
> where its module and model are singular. A defect, not a convention.

## Before you're done

```bash
./.venv/Scripts/python.exe .claude/skills/atlas-database-entity/scripts/check_registered.py \
    D:/Dev.Work/project.finance/solution.atlas --domain <domain>_data --entity <entity>
```

Checks the whole registration chain, the schema key, the table/module name
match, and the controller export. Exits 1 on any finding. This is the only
mechanical guard against the silent failure above — the interpreter will not
help you.

## Bets

- **The verbatim import prologue is deliberate, not copy-paste drift.** It is
  identical across all three models, which is what a template looks like — but
  there is no linter and no commit that enforces it. Ask the author; a single
  answer settles it.
- **`models/__init__.py` should use explicit named imports** (`from .x import X`,
  as `reference_data` does) rather than `import *` (as `market_data` does). Both
  are live and single-authored, so this is unresolved: the explicit form is
  encoded here because it is what the larger package does and because
  `check_registered.py` can verify a named import precisely. Say which you want
  and this becomes a rule instead of a bet.
- **The controller method vocabulary is complete.** It is drawn from one full
  controller and one partial one; a third entity with different access patterns
  may add verbs this list does not have.
