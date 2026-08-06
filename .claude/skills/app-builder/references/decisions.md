# The decisions a layer faces, including the ones the source never made

`shape` and `questions` can only report what is **in** the index. A source that
does something two ways produces a `VARIES` row and a question; a source that
does it one way produces `ALWAYS` and is reproduced in silence. A source that
**does not do it at all** produces nothing — no record, no count, no row — and
no query can raise it.

That third case is what this file is for. It is a checklist of decisions each
kind of layer normally faces, so that an absence in the source becomes a
question to the user instead of an invisible default.

## The rule this changes, and the rule it does not

`generating.md` says **do not improve the exemplar**, and that stays — it was
written for a real failure, where making a clumsy signature nicer broke every
caller. What changes is one word: do not improve it **silently**.

- Fidelity is still the default. Reproduce the source unless told otherwise.
- A departure still requires the user's answer. Never adopt a "better" pattern
  because it is better.
- But an absence in the source is now **askable**, where before it was invisible.

Every proposal from this file must therefore carry three things: what the source
does (or that it does nothing), what the alternative is, and that choosing it is
a **departure** — which `conform` will then report, correctly, as ADDED.

## How to use it

Check each row against the index for the layer being generated. Raise the ones
that are both **absent** and **load-bearing for what was asked**. A school
timetable needs delete behaviour settled; a throwaway import script does not.

Rank them the way `questions` ranks everything else: by what it costs to get
wrong. Adding a column later is a migration. Discovering that deleting a pupil
destroyed four years of academic records is not recoverable at all.

---

## Data model layer

| Decision | How to check the index | Why it is load-bearing |
|---|---|---|
| **Relationships** | `relationship(` count vs foreign-key count | Foreign keys give the *database* navigation; `relationship()` gives the *ORM* navigation. Six FKs and no relationships means `student.form_class` does not exist, and every caller joins by hand. A UI layer will want it immediately. |
| **Delete behaviour** | `ondelete=` values across the layer | `CASCADE` on a record people care about is destructive and silent. Soft delete, `RESTRICT`, or `SET NULL` are the alternatives, and the domain decides — not the source. |
| **Timestamps** | any attribute matching `created_at`/`updated_at` | "When did this row appear" is unanswerable afterwards. Cheap now, a migration plus lost history later. |
| **Optimistic concurrency** | a `version` column, or `__mapper_args__` | Two people editing one record: last write wins, silently, unless something is versioning. |
| **Constraints beyond keys** | `CheckConstraint`, `UniqueConstraint` | A rule enforced only in application code is a rule that is not enforced. |
| **Nullability** | explicit `nullable=` vs inferred from `Optional[...]` | SQLAlchemy infers, so the schema is decided by a type hint that reads as documentation. Worth being deliberate where it matters. |
| **Defaults: Python or server** | `default=` vs `server_default=` | A Python default does not apply to rows written by anything else — a migration, a bulk load, another service. |
| **`__repr__`** | `def __repr__` | Costs three lines and is the difference between a readable failure and `<Student object at 0x...>`. |

## Controller / repository layer

| Decision | How to check | Why |
|---|---|---|
| **Transaction boundary** | who opens the session — the controller, or the caller | Two controller calls in one request either share a transaction or do not, and the difference only shows under failure. |
| **Bulk operations** | `save_many`, `bulk_insert`, executemany | Row-at-a-time is fine until an import arrives. |
| **Pagination shape** | offset/limit vs keyset | Offset paging drifts while data changes underneath, and degrades at depth. |
| **Not-found convention** | returns `None`, raises, or returns a result object | Every caller has to know which, and mixed conventions inside one layer are a real source of bugs. |

## Web API layer

| Decision | How to check | Why |
|---|---|---|
| **Failure signalling** | HTTP status codes vs an ok-with-`has_errors` body | A 200 carrying an error is invisible to every generic client, proxy, retry policy and monitor. |
| **Read verb** | POST-for-reads vs GET | GET is cacheable, linkable, and works from a browser address bar. POST-for-reads is a real choice with real costs. |
| **Authentication** | any auth dependency or middleware | An API with none is a decision, not an oversight. |
| **Versioning** | a version in the path or a header | Cheap to add before clients exist, expensive after. |
| **Validation errors** | field-level detail vs a message string | A form cannot highlight a field from a sentence. |

## UI layer

| Decision | How to check | Why |
|---|---|---|
| **Server state handling** | a query library vs hand-rolled fetch | Caching, retries and invalidation get written either way; the question is whether by you. |
| **Form state and validation** | a form library vs `useState` per field | Validation rules otherwise live in two places, and drift from the API's. |
| **Error surface** | where a failed call becomes something a person sees | Otherwise every component invents its own. |
| **Generated client** | regenerate from the spec vs hand-written | A generated client cannot drift; it also cannot be edited, and its shape is the generator's. |

---

## What this file is not

It is not a standard, and following every row would produce a heavier
application than most requests deserve. It is a list of questions worth
*asking*, ranked against what was actually requested — nothing more. The answer
"no, atlas does not do that and neither should we" is a perfectly good one, and
should be recorded in the report at step 9 like any other choice.
