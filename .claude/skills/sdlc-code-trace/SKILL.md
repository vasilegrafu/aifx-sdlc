---
name: sdlc-code-trace
description: Follow one behaviour through a codebase from entry point to effect, and report the path. Use for "where does X happen", "how does Y work", "what runs when a user does Z", "why is this value wrong", "what calls this" — questions with one thread to pull. For first contact with a repository you have never seen, use sdlc-codebase-survey instead.
---

# Code trace

Depth-first. You are producing a **path**: an ordered list of hops from where
control enters to where the effect happens, each anchored at `file:line`.

A trace is finished when the path is connected end to end, or when you can name
exactly which hop you could not resolve and why. Those are the only two
acceptable endings.

## Procedure

### 1. Make the question answerable

"How does authentication work" is not traceable; it is a survey question
wearing a trace costume. Convert it into a specific thread with two ends:

> *When a request arrives with an expired token, what produces the 401?*

If the question names no starting input and no observable effect, ask for one
or pick the most likely and **say which you picked**.

### 2. Pick a distinctive anchor

The single highest-leverage decision in a trace. Search for the most unusual
string in the system, not the most relevant-sounding one:

**Good anchors** — an error message, a log line, a route path, a magic
constant, a header name, a table or column name, an environment variable, a
feature-flag key, an exception type. These are rare, so they land on few files.

**Bad anchors** — `handler`, `process`, `service`, `manager`, `validate`,
`execute`. These are everywhere, and a hundred matches teaches you nothing.

Prefer a string the *user* would see or the *system* would emit. It is usually
unique in the repository and usually near what you want.

### 3. Walk edges, not files

At each hop record: what called this, what this does, what it calls next.
Follow the thread. Do not read the rest of the file because you are already in
it — that is how a trace becomes a survey.

Stop expanding a branch when it cannot affect the outcome you are chasing.

### 4. Expect the thread to break, and know where

Grep follows explicit calls. It does not follow:

- **dependency injection / IoC containers** — the registration site names the
  implementation; find the binding, not the call
- **events, queues, pub-sub** — search the *message or topic name*, not the
  publisher
- **reflection, dynamic dispatch, metaprogramming, code generation** — search
  the generator or the convention, and say so
- **configuration-driven dispatch** — the mapping is data; read the data
- **framework lifecycle hooks** — nothing in the repository calls them; the
  framework does. Name the framework contract instead of hunting for a caller.
- **interfaces with several implementations** — find which one is *wired*, not
  which ones exist

When you hit one, say which kind it is. "The thread breaks here at an event
boundary; the topic is `order.settled` and three subscribers register for it"
is a complete, useful finding. Guessing which subscriber runs is not.

### 5. Use history and tests as evidence

- **Tests are the cheapest executable specification.** A test exercising the
  path names the entry point and asserts the expected effect — often a better
  answer than the source, and it is verified.
- `git log -S "<anchor>"` finds when the behaviour appeared.
- `git log -p <file>` and `git blame` explain *why* far better than a comment,
  because the commit message had a reason to exist.

Reach for these when the code says *what* and the question was *why*.

### 6. Report the path

```
Question   the specific thread, as you interpreted it

Path
  1. <what happens>              file:line
  2. <what happens>              file:line
  3. ...                         file:line
  → <the effect>                 file:line

Breaks
  - hop 3 → 4 crosses <DI | event | reflection | config>; resolved by <how>,
    or NOT resolved and here is what it would take

Notes
  - anything the caller will trip over: a second path to the same effect,
    a branch that looks live but is dead, a name that means two things
```

## Anti-patterns

- **Starting at the top.** Do not trace forwards from `main` hoping to arrive.
  Anchor near the effect and walk *backwards* to the entry — the search space
  shrinks instead of growing.
- **A generic anchor.** A hundred grep hits is a wasted step; pick a rarer
  string and try again.
- **Silently bridging a gap.** An unresolved hop reported honestly is a finding.
  An unresolved hop papered over with a plausible guess is a wrong answer that
  reads like a right one, and the caller has no way to tell.
- **Reading whole files at each hop.** Read the function, not its neighbours.
- **Answering a survey question with a trace.** If there is no single thread,
  stop and survey instead.
