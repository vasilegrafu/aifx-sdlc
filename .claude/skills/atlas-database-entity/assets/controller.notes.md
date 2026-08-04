# `controller.py` — what is contract, what is sample

## Source

Copied verbatim from
`solution.atlas:database/reference_data/controllers/stock_instrument_dbctrl.py`
on 2026-08-04. No credentials; nothing removed.

The second controller in the repo
(`market_data/controllers/stock_candlestick_dbctrl.py`) is a *narrower* version
of this one — same contract, fewer methods, plus range queries. This file is the
full surface; take from it only the methods the entity actually needs.

## Load-bearing — reproduce these

| Lines | What must hold | Why |
|---|---|---|
| 1 | `from devfx.database.sqlalchemy import StandardDbCtrl` | every query goes through `StandardDbCtrl`; raw `select()` / `session.scalars()` appears nowhere in this layer |
| 2 | `from database.session_injector import session_injector` | |
| 3 | `from ..models import <Entity>` | relative, through the models barrel — **not** `from database.<domain>_data.models.<entity> import <Entity>` |
| 5 | `class <Entity>DbCtrl:` | |
| every method | `@staticmethod` then `@session_injector`, in that order, with `session` as the first parameter | there is no `__init__` and no instance state anywhere in this layer; the decorator supplies the session |
| every method | no type hints, no docstrings | models are typed, controllers are not — a deliberate split in this codebase |
| query bodies | `StandardDbCtrl(session).select(<Entity>)` then chained `.filter(...)`, continued with `\` and aligned under the first call | |
| `# ----` lines | separator between method families: save / get-many / get-one / delete | |

## The method vocabulary

Names are the contract. A reviewer reads these before the bodies.

| Method | Shape |
|---|---|
| `save(session, <entity>_spec)` | `StandardDbCtrl(session).save(<entity>_spec)` |
| `save_data(session, criteria, **assigns)` | `...save_data(<Entity>, criteria, **assigns)` |
| `get_all(session)` | `.select(<Entity>).all()` |
| `get_list(session, filtering_spec, sorting_spec)` | the spec block below |
| `get_page(session, filtering_spec, sorting_spec, pagination_spec)` | the spec block, then `.paginate_by_spec(...)` |
| `get_by_id(session, id)` | `.filter(<Entity>.id == id).one_or_none()` |
| `get_by_<field>(session, <field>)` | `.one_or_none()` |
| `get_by_<field>s(session, <field>s)` | plural means `.in_(...)` and `.all()` |
| `delete_all(session)` | `.select(<Entity>).delete()` |
| `delete_by_id` / `delete_by_<field>` / `delete_by_<field>s` | mirror the getters exactly |

`get_by_<field>` / `delete_by_<field>` pairs exist for the entity's natural
business key. Do not invent getters for fields nobody looks up by.

## The spec block — reproduce verbatim

This appears identically in `get_list` and `get_page`. It is ceremony, not
shape: copy it, do not paraphrase it.

```python
        query = StandardDbCtrl(session).select(<Entity>)
        if filtering_spec:
            query = query.filter_by_spec(filtering_spec)
        if sorting_spec:
            query = query.order_by_spec(sorting_spec)
```

## Placeholders

| In the exemplar | Stands for |
|---|---|
| `StockInstrument` | `<Entity>` |
| `stock_instrument_spec` | `<entity>_spec` |
| `ticker_symbol` | the entity's natural business key |

## Deliberately absent

- **No `__init__`, no `self`.** Everything is a static method.
- **No `session.commit()`, no `session.add()`, no `session.refresh()`.**
  `StandardDbCtrl` and the injector own the transaction.
- **No exception handling and no logging.**
- **No return type annotations**, including on the getters.

## Known defects in the source — do not copy

- `market_data/controllers/stock_candlestick_dbctrl.py` declares
  `class StockCandlesticksDbCtrl()` — plural, and with empty parentheses, while
  its module and model are singular. Use the singular, parenthesis-free form
  shown here.
- The same file has `get_max_time_by_instrument_id_` with a trailing underscore.
  A typo, not a convention.
