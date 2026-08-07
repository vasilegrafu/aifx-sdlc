# Challenging what the source is unanimous about

`references/decisions.md` covers what the source **never decided** — an absence
leaves no record, so no query can raise it. This file covers the opposite
silence: what the source decided **once, everywhere, and never revisited**.

Those are invisible for a reason that is worth stating plainly, because it is
counter-intuitive. `questions` ranks *forks*. A fork needs disagreement. A choice
the exemplar is unanimous about produces no fork, no row and no question — it
produces an `ALWAYS` row, which `shape` reports as the contract. So **the more
deeply embedded a choice is, the less likely anything is to raise it.**

## The gate

Every row here is a *candidate*, not a finding. Before putting one to the user,
you owe one of two things:

1. **Corpus evidence** — a `practice` run showing what the wider world does and
   when it last did it.
2. **A named failure** — the concrete thing that goes wrong. Not "dated", not
   "less clean". What breaks, for whom, when.

Without one of those, say nothing. A generation that spends its attention
arguing about the exemplar's taste is worse than one that copies it faithfully,
and "I would have written it differently" is not evidence.

## Reading `practice` honestly

`practice` is evidence, and evidence needs interpreting. Three traps, all real:

**`DISAGREES` does not mean wrong.** Measured, not hypothetical:

```
practice --on requests --versus httpx --lang python
  atlas             3  12%  2026-06     21  88%  2026-07
  corpus favours   requests   (requests 15, httpx 10)
  atlas DISAGREES -- it uses httpx
```

Atlas is *ahead* of the corpus here, not behind. Django and Flask are mature
codebases whose test suites still reach for `requests`; that is history, not
current preference. A corpus majority is a fact about the corpus, and a corpus
of mature projects is biased toward what was standard when they were written.
Read the dates in the row, not only the counts.

**The corpus is small and specific, and a thin one lies.** A dozen codebases,
chosen for other reasons. Enough to tell you a choice is contested; not a survey.

This is not a caveat, it is a thing that happened. React server state, asked
twice, with nothing changed but the corpus:

```
with 2 React repositories indexed          with 4
  bulletproof-react  72% useQuery            react-admin        88% useState
  zustand           100% useState            bulletproof-react  72% useQuery
                                             fastapi-fullstack  92% useState
  corpus favours useQuery                    zustand           100% useState
  atlas DISAGREES
                                             corpus favours useState
                                             atlas agrees
```

The first verdict was already on its way to the user as evidence. It was not
wrong arithmetic -- it was one opinionated repository being called "the corpus".
So: **before quoting a verdict, look at how many codebases produced it and
whether they are the right kind.** Two is not a corpus. A framework's own test
suite is not an application. Say the sample out loud when you report the number,
and if the answer embarrasses the claim, that is the finding.

**A token is not a design.** `useQuery` appearing in 72% of modules tells you a
library is in use. It does not tell you it was a good decision for a schools
admin screen with four forms.

## Ranking

Same axis as everything else: **what it costs to get wrong.** But note that the
cost of *changing* a unanimous convention is much higher than changing a forked
one, because unanimity means every call site agrees. A row that is cheap to
propose can be enormously expensive to accept.

State the blast radius with the proposal. "The corpus disagrees" and "this
rewrites every client" belong in the same sentence.

---

## Data model layer

| The source does | The alternative | The failure to name |
|---|---|---|
| Sync SQLAlchemy | async engine + session | Only bites under concurrency the target may never see. Do not raise it for an admin app; do raise it if the request mentions scale. |
| `uuid4` primary keys | ULID / sequential UUID, or identity | Random UUIDs scatter B-tree inserts and bloat indexes. Real at millions of rows; invisible below that. Name the row count. |
| Declarative `Base` per model file | shared mixins for common columns | Only worth raising once the same three columns appear on every model — before that it is speculation. |
| No migrations | Alembic | The failure is concrete and arrives on day two of production: a schema change with data in the table. Absence of migrations is usually an oversight, not a decision. |

## Controller / repository layer

| The source does | The alternative | The failure to name |
|---|---|---|
| Static classes with a `session` first parameter | instance repositories, or unit-of-work | Check callers first. This exact signature is the worked example in `generating.md` for why ergonomics are not a reason. |
| Session opened per call | session per request / unit of work | Named failure, and it is not theoretical: objects returned from a closed session are detached, so relationships raise `DetachedInstanceError` at every caller, and two calls in one request cannot share a transaction. |
| Naming `*DbCtrl` | `*Repository` | Convention only. No failure. Raise it grouped with other cosmetic items or not at all — and note that `*DbCtrl` matches the linked library's own `StandardDbCtrl`. |

## Web API layer

| The source does | The alternative | The failure to name |
|---|---|---|
| 200 with `has_errors` in the body | HTTP status codes | Every proxy, retry policy, monitor and generic client reads a failed call as success. Concrete, and it worsens as infrastructure is added. |
| POST for reads | GET | Loses caching, linkability, and the browser address bar. **Blast radius: every client.** Propose before clients exist; expect "no" afterwards. |
| One file per endpoint | routers grouped by resource | Taste, until the count is large. No failure at eleven endpoints. |
| No auth | any auth | Not an alternative — an absence. Belongs in `decisions.md`. |

## UI layer

| The source does | The alternative | The failure to name |
|---|---|---|
| `useState` for server data | a query library | Caching, retries, invalidation and request dedup get written either way. **But see the worked example below before raising this** -- the corpus verdict reversed once the corpus had more than one React application in it. |
| `useState` per form field | a form library with schema validation | Validation rules end up in two places and drift from the API's. |
| Hand-written API client | generated from the OpenAPI spec | A hand-written client drifts silently. A generated one cannot — but it also cannot be edited, and it is only as stable as the spec. |

---

## What this file is not

It is not a modernisation checklist, and working through it top to bottom would
be a misuse. Most `ALWAYS` rows are load-bearing and correct, and reproducing
them is the job. These are the handful where the default deserves a second look
— and the answer "no, that is how we do it here" is a good answer that should be
recorded in the report like any other.
