# `<exemplar filename>` — what is contract and what is sample

Sits beside the exemplar as `<name>.notes.md`. Without it a single sample cannot
say which lines are the convention and which are this instance's data, and the
reader guesses that distinctive-looking things are meaningful.

Not needed when two exemplars ship together and differ along one axis — the
diff between them says this better than prose can.

## Source

Copied verbatim from `<repo>:<path>` at `<sha>` on `<YYYY-MM-DD>`.
Scrubbed: `<what was removed — credentials, unrelated business logic>`.

## Load-bearing — reproduce these

| Lines | What must hold | Why |
|---|---|---|
| 1–8 | the import block, in this order | `<the rule>` |
| 14 | returns `<type>`, never throws | `<evidence pointer>` |
| 22–26 | this block appears verbatim | `<it is ceremony, not shape>` |

## Sample data — change these freely

| Lines | What it is |
|---|---|
| 10–12 | the entity's fields; a new artifact has its own |
| 31 | the log message wording |

## Placeholders

What the domain nouns stand for. Without this the generator writes the
exemplar's entity into an unrelated feature.

| In the exemplar | Stands for |
|---|---|
| `Order` / `orders` | the entity, singular / plural |
| `OrderService` | `<Entity>Service` |
| `createOrder` | `<verb><Entity>` |

## Deliberately absent

What this exemplar does *not* do, and should not be read as permission to omit
or to add. (An exemplar cannot show an absence; this is where it gets said.)

- no caching — `<why>`
- no retry — `<why>`
