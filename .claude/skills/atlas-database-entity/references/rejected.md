# Rejected, absent, and unresolved

## Tried and reverted

**A shared instrument supertype.** Before `5b1401b3cb` the market-data table was
a generic `candlestick`. That commit renamed it to `stock_candlestick` and its
body states the rule:

> Make each instrument type self-contained: stock_instrument <-> stock_candlestick,
> with stock_candlestick.instrument_id a FK to reference_data.stock_instrument.id
> ON DELETE CASCADE. No shared instrument supertype; future types add their own
> `<type>_instrument` / `<type>_candlestick` pair.

This is the thing a competent stranger reaches for first — one `instrument`
table with a `type` column, one `candlestick` table keyed by it. It was tried
and undone deliberately. Adding `option_instrument` / `option_candlestick` as a
new pair is the intended move, not a sign of duplication to refactor away.

## Present in the imports, absent from the code

`relationship` is imported by every model's prologue and used by none of them.
The foreign key in `stock_candlestick` is declared with `ForeignKey(...)` and
left at that — no `relationship()`, no `back_populates`.

Do not add ORM relationships because the import looks like an invitation. If
navigation is needed, that is a change to the layer's design and belongs in a
conversation, not in a generated file.

## Absent from every model

- `__repr__` — the most likely unprompted addition
- docstrings on model classes
- `nullable=` (optionality is `Mapped[Optional[str]]`, via `typing.Optional`)
- `server_default`, `onupdate`, timestamps of any kind
- validation: no pydantic in this layer, despite pydantic being a dependency of
  the wider solution

## Absent from every controller

- `__init__`, `self`, instance state
- `session.add` / `commit` / `refresh` / `rollback`
- type hints and docstrings
- exception handling and logging

## Unresolved — do not decide alone

**Barrel style.** `reference_data/models/__init__.py` uses explicit named
imports; `market_data/models/__init__.py` uses `from .stock_candlestick import *`.
Both are current, both by the same author, and no commit argues for either. The
skill encodes the explicit form and flags it as a bet.

`check_registered.py` accepts either, so a generated file passes whichever way
the answer goes.

## Defects in the source — do not copy

- `class StockCandlesticksDbCtrl()` — plural class name where the module and the
  model are singular, and empty parentheses where the other controller has none.
- `get_max_time_by_instrument_id_` — trailing underscore, a typo.

Both are in `market_data/controllers/stock_candlestick_dbctrl.py`. They are
noted here rather than fixed, because fixing the source is a change to that repo
and not this skill's business.
