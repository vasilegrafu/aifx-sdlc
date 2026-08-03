# Proposal — agents and skills for the software development lifecycle

**Status: proposed, nothing built.** Written 2026-08-03. This document is a
plan, not a description of the tree — where it names a file, that file does not
exist yet. It is meant to be edited.

---

## The decision that drives everything else: agents are not phases

The obvious mapping — one agent per lifecycle phase (`sdlc-requirements`,
`sdlc-design`, `sdlc-code`, `sdlc-test`, `sdlc-deploy`) — is the wrong shape,
and it is rejected here explicitly because it is what gets built first by
default.

Waterfall phases are not context boundaries. Real work is one loop — *understand
→ change → verify* — run at different altitudes. And every agent spawn starts
**cold**: it re-derives context that already existed. Phase-agents mean paying
that tax five times to ship one change.

**Spawn an agent only when there is a reason the main thread cannot do the job:**

| Reason | Example |
|---|---|
| **Context isolation** — high-volume reading where only the conclusion is wanted | codebase archaeology |
| **Tool policy** — the job requires *not* having a capability | a reviewer holding `Edit` fixes things instead of reporting them |
| **Independence** — the work is invalid if the same context produced the thing being judged | code review, security audit |
| **Conflict of interest** | whoever writes the code should not be free to weaken its assertions |

The consequence: **agents are few and role-shaped; skills are many and
procedure-shaped.** Skills are where leverage compounds. An agent is roughly
forty lines of prompt; a skill is a durable, versioned, testable procedure.

---

## Agents

> **Superseded by [AGENTS.md](AGENTS.md).** The roster there is the current
> design; this section is kept for the reasoning that produced it and for what
> changed.

The four criteria for spawning an agent at all — and the rejection of one agent
per lifecycle phase — carried over unchanged. What the roster got wrong was its
coverage, in three ways:

- **No `sdlc-analyst`.** Requirements were filed under "deliberately not
  agents", on the grounds that they are a skill anyone can invoke. That misses
  the point: an analyst's value is *refusing to invent missing details*, and
  isolation is what makes the refusal credible. A caller holding the whole
  client conversation will fill gaps helpfully; a cold agent holding only the
  raw notes cannot.
- **No `sdlc-writer`.** Documentation was dismissed as "a worse writer with
  less context". Wrong for the client-facing half — a writer who knows how it
  works internally writes documentation that assumes you do too. Less context
  is the point.
- **Nothing about the handoffs.** The roster listed seven isolated agents and
  said nothing about what passes between them, which is where every isolation
  guarantee is actually enforced or lost. AGENTS.md defines the payloads.

Also changed: `sdlc-tester` became `sdlc-test-engineer` with an explicit
contract-not-body rule, and `sdlc-implementer` is deferred in favour of the
main thread until there are two tickets running at once.

---

## Skills

Each skill is one directory. Tiers are build order, not importance.

### Tier 0 — the factory

Built first, because it makes everything after it consistent.

- **`sdlc-codebase-survey`** — first contact with an unfamiliar repository:
  what it is, what builds it, how it is laid out, what conventions it follows
  *(built)*
- **`sdlc-code-trace`** — following one behaviour from entry point to effect
  through a codebase already mapped *(built)*
- **`sdlc-skill-mining`** — the procedure for extracting a skill from an
  existing project *(built)*
- **`sdlc-skill-authoring`** — how a skill in this repo is structured, plus
  `check.py`, the validator that enforces it *(built)*

The first two are the `sdlc-explorer` agent's own skills: its work splits into
a breadth-first question and a depth-first one, which have different stopping
conditions and therefore cannot share a procedure. They come before mining
because mining reads whatever they find.

Mining and authoring belong to **the caller, not to an agent**. Both are work
where the user's judgment is the product — which convention is worth keeping,
whether a description will fire — and that is exactly what an isolated
cold-start agent cannot supply. They are also the only skills here that operate
on *this* repository rather than on the software being built.

Authoring was written **last on purpose**, by codifying what the skills built
before it already had in common. A standard derived from working examples beats
one invented against a blank page, and its validator had four real skills and
an agent to be tested against on the day it was written.

### Tier 1 — the daily loop

Highest use per unit of effort.

- **`sdlc-code-review`** — the review checklist and severity model
- **`sdlc-test-strategy`** — what to test, at which level, and what not to test
- **`sdlc-adr`** — architecture decision records
- **`sdlc-commit-and-pr`** — commit shape, PR description, changelog entry
- **`sdlc-debug`** — systematic debugging: reproduce, isolate, minimal fix
- **`sdlc-scaffold`** — new project and new module scaffolding

### Tier 2 — design and contracts

- **`sdlc-requirements`** — stories, acceptance criteria, scope boundaries
- **`sdlc-system-design`** — component and interaction design
- **`sdlc-api-design`** — contract-first interface design
- **`sdlc-data-model`** — schema design and evolution
- **`sdlc-threat-model`** — structured security analysis

### Tier 3 — delivery and operations

- **`sdlc-ci-pipeline`** · **`sdlc-containerize`** · **`sdlc-iac`**
- **`sdlc-release`** — semver, changelog, tagging, migration notes
- **`sdlc-observability`** — logs, metrics, traces, what to instrument
- **`sdlc-incident`** — triage and postmortem

### Tier 4 — leverage

Where the Python generation and calculation scripts live.

- **`sdlc-codegen`** — specification or schema to source, via the Jinja engine
- **`sdlc-report`** — the component and report engine lifted from
  `aifx-finance`, retargeted at architecture documents, review reports and
  postmortems
- **`sdlc-metrics`** — DORA and cycle-time calculations from git and CI data

Tier 4 is the direct payoff from `aifx-finance`. Its report engine — a builder
CLI, a controller whose `_build_context()` derives and asserts, a Jinja
template, and validation of the artifact it just produced — **is already a code
generator**. Swapping `.html.j2` for `.py.j2` changes nothing structural.

---

## Many technologies, without multiplying skills

Working across many stacks invites `sdlc-test-strategy-python`,
`-dotnet`, `-typescript` — an N×M explosion in which the interesting content,
the procedure, is copy-pasted and then drifts apart.

Instead: **one skill is one procedure**, with stack specifics behind
progressive disclosure.

```
sdlc-test-strategy/
  SKILL.md            the procedure -- stack-agnostic, always loaded
  REFERENCE.md        depth, loaded on demand
  stacks/
    python.md  dotnet.md  typescript.md  go.md
  check.py            the executable part
```

`SKILL.md` says *read `stacks/<detected>.md`*. Adding a stack is one file, not
a fork, and the invariant lives in exactly one place — which is the single most
important property of the whole arrangement.

---

## Practices, decided now rather than discovered later

### Agents

1. **`description` is a routing key, not documentation.** Write it for the
   dispatcher, with concrete trigger phrases. A vague description means the
   agent never fires.
2. **Restrict `tools` deliberately.** A capability that is not removed will be
   used.
3. **Every agent declares an output contract** — what it returns, in what
   shape. A cold-start agent that dumps raw findings forces the caller to
   re-read everything it read.
4. **Agents do not spawn agents.**

### Skills

5. **Progressive disclosure.** `SKILL.md` stays short and procedural; depth
   goes to `REFERENCE.md`; bulk goes to subdirectories.
6. **Prefer a script over prose wherever the check is deterministic.** This is
   the hardest-won lesson in `aifx-finance`: prose drifts from the tree
   silently, a script reads the tree every time. Corollary — **never write a
   count into a document**. It is true the day it is typed and cannot say when
   it stopped being.
7. **Every generator validates what it just generated**, splitting severity two
   ways: **error** means structurally broken and independent of the input;
   **warning** means it rendered but the content is thin. Without that split a
   legitimately sparse input fails its own check, and the output gets ignored.
8. **One procedure lives in exactly one place.** In `aifx-finance`, duplicating
   a procedure into a REFERENCE cost a dropped step that nobody noticed.
9. **Skills are versioned by the repository.** Nothing versions itself.

### Naming

Agents take **role nouns** (`sdlc-reviewer`); skills take **activity or
artifact names** (`sdlc-code-review`). Sharing the `sdlc-` prefix is fine only
while the grammar differs — otherwise an agent and a skill end up with the same
name and no way to tell which was invoked.

---

## Build order

1. **`sdlc-explorer`, `sdlc-skill-authoring`, `sdlc-skill-mining`** — the
   factory. The explorer mines an existing project, authoring turns findings
   into skills, mining is the procedure connecting them. Everything after this
   is faster.
2. **Port the engine** from `aifx-finance`: `_paths.py`, `status.py`, the
   builders, `css/` and `js/`. Gate: `status.py --check` exits 0 on the new
   tree.
3. **Tier 1 skills**, mined from a real project, one at a time — each finished
   only when its `check.py` runs.
4. **`sdlc-reviewer` and `sdlc-architect`**, now that there are skills for them
   to invoke.
5. **Tiers 2 to 4**, as each earns its place.

## Open questions

Two things block step 1:

- **Which project gets mined?** Ideally one with real CI configuration, pull
  request history and conventions worth extracting.
- **Which stacks matter most?** That decides what goes into `stacks/` first;
  everything else can wait.
