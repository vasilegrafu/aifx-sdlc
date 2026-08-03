# The agent roster

**Who exists, what isolates each one, and what passes between them.**

Written 2026-08-04. Supersedes the agent list in [PROPOSAL.md](PROPOSAL.md).
Everything here except `sdlc-explorer` is **designed, not built** — where this
document names a file, that file does not exist yet.

---

## The roster

Role nouns, per the naming rule in `sdlc-skill-authoring`.

| Agent | Turns | Into | Status |
|---|---|---|---|
| `sdlc-explorer` | a question about unfamiliar code | findings with anchors | **built** |
| `sdlc-analyst` | call notes, emails, vague asks | requirements, acceptance criteria, open questions | designed |
| `sdlc-architect` | requirements | design options with trade-offs, ADRs, data model | designed |
| `sdlc-implementer` | one ticket | a diff | **deferred** — see below |
| `sdlc-reviewer` | a diff | ranked findings | designed |
| `sdlc-test-engineer` | acceptance criteria | tests | designed |
| `sdlc-writer` | shipped behaviour | API docs, runbooks, user guide, release notes | designed |
| `sdlc-releaser` | a merged change | version, changelog, tag, migration notes | designed |
| `sdlc-operator` | logs, telemetry, a phone call | diagnosis, postmortem | designed |

---

## The part that decides whether this works

**Isolation is a property of the handoff, not of the agent.**

An agent isolated by *intention* is not isolated. Hand the reviewer a diff and
mention in passing that the implementer chose a queue for throughput, and the
fresh context is gone — you have paid the spawn cost and bought nothing.

So the system is not a set of prompts. It is a set of **payloads**, and each one
is a rule the caller must follow, because no agent prompt can defend itself
against what it is told.

| Handoff | Carries | Must not carry |
|---|---|---|
| Analyst → Architect | requirements, acceptance criteria, open questions | the client's tone, anything inferred to fill a gap |
| Architect → Implementer | the chosen option, its ADR, the ticket | the rejected options and why they lost |
| Implementer → Reviewer | diff, ticket, acceptance criteria, conventions | **any implementer reasoning whatsoever** |
| Acceptance criteria → Test engineer | criteria, public contracts, schemas | implementation bodies |
| Everything → Writer | shipped behaviour, acceptance criteria | internal rationale — for the client-facing half |

Every isolation guarantee in this roster is enforced at exactly one of those
rows. Write them down before writing any agent.

---

## Why an agent at all

An agent is justified by exactly four things, all about context rather than
subject matter:

1. the work reads far more than the answer is worth carrying back
2. the job requires *not* having a capability
3. the result is invalid if the same context produced the thing being judged
4. there is a conflict of interest with the caller's goal

One agent per lifecycle phase fails all four. Phases are not context boundaries
— real work is one loop, *understand → change → verify*, run at different
altitudes — and every spawn starts cold, re-deriving context that already
existed. Each agent below names which criterion it meets.

---

## The agents

### `sdlc-analyst`

**Criterion 2 and 4.** Its most valuable behaviour is refusing to invent missing
details — and **isolation is what makes that refusal credible**. The main
thread, holding the whole client conversation, "knows" what they probably meant
and will helpfully fill the gap. A cold agent holding only the raw notes
*cannot* invent from context it does not have. The gap becomes an open question
instead of a silent assumption.

- **In** — call notes, emails, transcripts, whatever the client actually said
- **Out** — user stories, acceptance criteria, and the open-questions list
- **Tools** — `Read`, `Write`, `Glob`, `Skill`. No repository access: the code
  is not evidence of what the client wants, and reading it invites inferring
  requirements from what already exists.

**The open-questions list is a first-class artifact, not a section.** It
persists and accumulates: the architect and implementer will each discover gaps
the analyst could not see, and every one of them needs a route back to the
client.

**Failure mode it must be built against:** a requirements document with no open
questions. That means the gaps were filled, not found.

### `sdlc-architect`

**Criterion 1 and 2.** Read-only on the repository, so it cannot drift into
fixing what it is supposed to be designing.

- **In** — requirements and acceptance criteria
- **Out** — two or three options with trade-offs, an ADR for the chosen one,
  system design, data model
- **Tools** — `Read`, `Grep`, `Glob`, `Skill`, and `Write` scoped to documents

**Forced options degrade into one real proposal and two strawmen.** It looks
like analysis and is not. The defence is a hard requirement:

> **Every option must state a named condition under which it wins.**

If you cannot say when B beats A, B is a strawman and the work was not done.
That is checkable; "give me options" is not.

### `sdlc-implementer` — deferred on purpose

**Criterion 1, weakly.** Implementation is the one phase where you want to steer
turn by turn, and where a cold start costs the most: it re-derives the codebase
context you were just holding.

**Keep implementation in the main thread until you have two tickets running at
once.** The agent version pays off for parallel work across worktrees, and not
much before that. This is a real capability that is deliberately not being
spent yet.

When it is built, **split by tool policy, not by language.** Backend, frontend
and data work rarely conflict in *conventions*; they conflict in tooling and
feedback loop — a frontend change needs a browser to verify, a data change needs
migrations and a database. That is what predicts whether one agent can do both
jobs.

Its conventions come from a **mined skill per project**, not a file baked into
the prompt. That is what the factory is for.

### `sdlc-reviewer`

**Criterion 2, 3 and 4 — the strongest case in the roster.** It gets a fresh
context holding only the diff, the ticket and the acceptance criteria. It must
not see the implementer's reasoning, because **an agent that has already
justified a choice will defend it.**

- **In** — diff, ticket, acceptance criteria, conventions. Nothing else.
- **Out** — ranked findings
- **Tools** — `Read`, `Grep`, `Glob`, `Bash` for `git diff`/`git log`, `Skill`.
  **No `Edit` and no `Write`** — a reviewer that can fix will fix, and the
  finding is lost.

**Every finding carries a severity and a concrete failure scenario** — the
inputs or state that produce the wrong output. Without that ranking a
fresh-context reviewer produces forty nitpicks in arbitrary order and you stop
reading it, which costs more than having no reviewer.

Security is a **skill on this agent**, not a separate one: a different lens on
the same diff, not a different context.

### `sdlc-test-engineer`

**Criterion 3 and 4.** It writes tests from the acceptance criteria. If it reads
the implementation first, you get tests that faithfully encode the bug.

The rule needs one refinement, or the agent cannot work at all — tests written
purely from prose do not compile:

> **Read the contract, never the body.** Public signatures, type definitions,
> schemas and route tables are fair game. The implementation of the thing under
> test is not.

Without that distinction it produces unrunnable pseudo-tests, or quietly reads
the implementation anyway and you are back to encoding the bug.

- **In** — acceptance criteria, public contracts
- **Out** — tests, and a note on any criterion that could not be tested
- **Tools** — `Read`, `Grep`, `Glob`, `Write`, `Edit`, `Bash`, `Skill`

**Run it before the implementer where you can.** Then the isolation costs
nothing to enforce, because there is no implementation to read.

### `sdlc-writer`

**Criterion 1 and 3.** One agent, two jobs with different sources of truth and
opposite failure modes:

| | Verified against | Fails by |
|---|---|---|
| **Technical** — API docs, README, runbooks | the code | drifting silently |
| **Client-facing** — user guide, training, release notes | the acceptance criteria | assuming knowledge |

The second has its own isolation argument, and it is the same one the reviewer
rests on: **a writer who knows how it works internally writes documentation
that assumes you do too.** The curse of knowledge is a context problem.

**One agent, two skills** — because the source of truth differs. Split the agent
only if the client-facing output starts sounding like internal documentation.

This is the phase solo developers under-serve most, and disproportionately what
clients judge the work on.

### `sdlc-releaser`

**Criterion 2.** Version, changelog, migration notes, tagging, publishing.
Hard-to-reverse and outward-facing, so it gets a narrow blast radius rather than
living inside the implementer where any run might trip it.

- **Tools** — `Read`, `Edit`, `Bash`, `Skill`, gated. It asks before anything
  leaves the machine.

### `sdlc-operator`

**Criterion 1.** Lives in runtime data rather than source: logs, telemetry,
triage, postmortem. For consulting work this is the phase where reputation is
won or lost — the client calls when it breaks, not when it ships.

- **Tools** — `Read`, `Grep`, `Glob`, `Bash`, `Skill`, read-mostly

---

## The skills each agent needs

The factory builds these. Grouped by owner; several are shared.

| Agent | Skills |
|---|---|
| `sdlc-analyst` | `sdlc-requirements`, `sdlc-acceptance-criteria`, `sdlc-estimation` |
| `sdlc-architect` | `sdlc-adr`, `sdlc-system-design`, `sdlc-api-design`, `sdlc-data-model`, `sdlc-tech-selection`, `sdlc-threat-model` |
| `sdlc-implementer` | `sdlc-conventions` *(mined per project)*, `sdlc-scaffold`, `sdlc-codegen`, `sdlc-debug`, `sdlc-refactor` |
| `sdlc-reviewer` | `sdlc-code-review`, `sdlc-security-review` |
| `sdlc-test-engineer` | `sdlc-test-strategy`, `sdlc-test-generation` |
| `sdlc-writer` | `sdlc-api-docs`, `sdlc-runbook`, `sdlc-user-guide`, `sdlc-release-notes` |
| `sdlc-releaser` | `sdlc-release`, `sdlc-changelog`, `sdlc-migration` |
| `sdlc-operator` | `sdlc-observability`, `sdlc-incident`, `sdlc-postmortem` |
| shared | `sdlc-commit-and-pr`, `sdlc-ci-pipeline` |

## Where the factory cannot reach

`sdlc-skill-mining` extracts practices from an existing repository. That covers
the implementer, the reviewer, the test engineer and the technical half of the
writer — all of it is in your projects' history, CI configuration and review
comments.

**It has no source for the analyst, or for the client-facing writer.**
Requirements elicitation and client training material are not in any repository;
they are in your head and your email. Those skills must be *authored* from your
own practice, with you in the loop — slower, and worth knowing before planning a
mining sprint that cannot reach two of these.

---

## Build order

**Do not build the roster.** Build one vertical slice.

1. Take a real ticket from a real project.
2. Run the chain once **by hand** — analyst, architect, implementation,
   reviewer, test engineer, writer — with the five payloads written down and
   enforced.
3. Note which handoff leaked and which role was underspecified. That is the
   design feedback, and it is far cheaper now than after a dozen skills exist.
4. Build the agents the slice proved you need, in the order it proved you need
   them.
5. Mine the skills, one at a time, each ending in a working check.

The reviewer and the test engineer are the two whose value does not depend on
the rest of the chain existing. If the slice stalls, build those.
