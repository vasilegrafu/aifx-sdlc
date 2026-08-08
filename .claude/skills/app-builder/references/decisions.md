# The decisions a layer faces, including the ones the source never made

`shape` and `questions` can only report what is **in** the index. A source that
does something two ways produces a `VARIES` row and a question; a source that
does it one way produces `ALWAYS` and is reproduced in silence. A source that
**does not do it at all** produces nothing — no record, no count, no row — and
no query can raise it.

That third case is what this file is for. It is a checklist of decisions each
kind of layer normally faces, so that an absence in the source becomes a
question to the user instead of an invisible default.

The second case — done one way, always, and reproduced in silence — is the
mirror image, and it has its own file: `alternatives.md`. Keep them apart. An
absence is raised because nothing in the index can raise it; a unanimous
convention is challenged only on evidence, and the default there is to reproduce
it faithfully.

The last section covers **cross-cutting dimensions** — logging, auth, CI,
deployment — which belong to the application rather than to any layer, and which
the index can answer only partly. That section says which is which, and it is
worth reading before claiming to have checked one of them.

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

## Cross-cutting dimensions

The tables above are per layer. These are not — they belong to the application,
they are decided once, and they are almost always decided by **omission**,
because nothing in a request for "a web API" mentions logging.

They also differ from everything else here in how much the index can help, and
being precise about that is the point of the middle column. Do not claim to have
checked something the index cannot see.

| Dimension | Can the index answer it? | Why it is worth raising |
|---|---|---|
| **Error handling** | **Yes** — `find --symbol 'Error$'`, and `practice --on <ExceptionName>` | atlas carries a whole hierarchy under `devfx/exceptions/` — `ApplicationError`, `ArgumentError`, `OperationError`. A generated layer that raises bare `Exception` has silently left the source's contract, and `conform` will not say so because exceptions are not class features. |
| **Logging** | **Yes** — `practice --on logging --versus structlog` | Measured on this index: the reference corpus uses `logging` in 52 modules; **atlas and the target use neither, anywhere**. That is an absence with no index record of its own, and the first production incident is when anyone notices. |
| **Authentication** | **Yes** — `shape --kind func` and read `DECORATORS` | Measured: `solution.school/webapi` shows `app.post 71%`, `route_wrapper 71%`, and no auth decorator at all. An API with no authentication is a decision; it should be one someone made. |
| **Configuration** | **Partly** — config *modules* are indexed; `.json`/`.env` values are not | Where configuration is read decides whether the app runs from anywhere. See `generating.md` on working from one directory. |
| **Test strategy** | **Partly** — `proof` finds test config, test directories and the interpreter | It cannot tell you whether the tests are any good, only that they exist and how they are run. |
| **Dependency management** | **Yes** — manifests are indexed; `deps` lists them, and `deps --on NAME` says who declares a package | An option that adds a dependency names it, and `deps --on` answers whether the exemplars or the target already declare it. References do not count as paid for, and are read only with `--references`. |
| **Build / packaging** | **No** | — |
| **Deployment, CI/CD** | **No** — 0 files; `.github/workflows`, Dockerfiles and YAML are not indexed at all | Generated code that no pipeline builds is not deployed, and nothing in this skill will notice. |
| **Observability** | **No** — metrics and tracing are configuration, not structure | Distinct from logging: logs say what happened once, metrics say how often. Raise only if scale or operability came up in the brief. |
| **Documentation** | **No** | A README is usually the honest deliverable, not a plan. |

**Raise these against the brief, not as a list.** The step 1 answers decide
almost all of them: a prototype maintained by its author needs none of CI,
observability or a documented public surface, and saying so once is better than
six questions. A system with a five-year life and a team needs most of them, and
then they are cheap to add now and expensive later.

The three at the bottom of the table share a property worth stating plainly:
**this skill cannot see them, so it cannot check them, and it must not imply it
has.** Saying "I have not looked at how this is deployed, because nothing about
deployment is in the index" costs one sentence and is the difference between a
gap the user knows about and one they do not.

---

## What this file is not

It is not a standard, and following every row would produce a heavier
application than most requests deserve. It is a list of questions worth
*asking*, ranked against what was actually requested — nothing more. The answer
"no, atlas does not do that and neither should we" is a perfectly good one, and
should be recorded in the report at step 10 like any other choice.
