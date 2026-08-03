---
name: sdlc-codebase-survey
description: Map an unfamiliar codebase — what it is, what builds and runs it, how it is laid out, which conventions it actually follows. Use on first contact with a repository, when onboarding onto a project, before planning a change in unfamiliar code, or when asked "what is this repo" / "how is this organised" / "how do I run this". For following one specific behaviour through code you already understand, use sdlc-code-trace instead.
---

# Codebase survey

Breadth-first. You are producing a **map**, not an understanding. The map is
finished when someone else can decide where to look; it is not finished when
you know how the software works, because that is unbounded and nobody asked.

## The one rule

**Executable documentation outranks written documentation.**

A README states what someone intended on the day they wrote it, and nothing
fails when it stops being true. A CI pipeline, a build script, a `Makefile`,
a container definition and a test suite are *executed* — they cannot drift
without something going red.

So: read what runs before you read what claims. And when the two disagree,
**the disagreement is a finding**. It usually marks either the newest thing in
the repo or the most abandoned one, and it is worth more to the caller than
either document alone.

## Procedure

### 1. Establish ground truth — before any source file

Find the manifest and the pipeline. These four questions have cheap answers and
they frame everything else:

- **What is it built with?** — the dependency manifest, and whether a lock file
  is committed
- **How is it built?** — build script, task runner, container definition
- **How is it tested?** — test framework, where tests live, how they are invoked
- **How does it ship?** — CI workflow, deployment configuration

Common manifests, as a starting grep rather than a definitive list: `package.json`,
`pyproject.toml`, `requirements.txt`, `*.csproj`, `*.sln`, `go.mod`, `Cargo.toml`,
`pom.xml`, `build.gradle*`, `Gemfile`, `composer.json`, `mix.exs`, `Package.swift`.
Pipelines live in `.github/workflows/`, `.gitlab-ci.yml`, `azure-pipelines.yml`,
`Jenkinsfile`, `.circleci/`.

A monorepo has several. Find that out now, not in step 4.

### 2. Separate the code from the noise

Before counting anything, establish what is *authored*:

- generated output — build directories, compiled assets, protobuf/OpenAPI output
- vendored dependencies committed into the tree
- fixtures and test data, which can dwarf the source

`.gitignore` tells you what the project itself considers disposable. Language
statistics and file counts that include generated code are worse than no
statistics, because they are confidently wrong.

### 3. Find the entry points

Where does control enter? `main`, the server bootstrap, the CLI definition, the
request router, the job scheduler, the event subscriber, the exported public
API. A codebase usually has two to five. Name them with `file:line`.

This is the highest-value step for whoever reads your map. Everything else is
reachable from here.

### 4. Establish the boundaries

What are the major parts, and how do they communicate — direct calls, HTTP,
queue, shared database, events? Two or three sentences and a list. Do not draw
a diagram of every module; draw the seams.

Pay attention to where the layering is *violated*, since that is where a change
will hurt.

### 5. Extract the conventions actually in force

Not the documented ones — the practised ones. Sample recent commits and a few
files from different areas, and look for what is consistent:

- naming, file organisation, module layout
- error handling and logging shape
- how configuration and secrets are reached
- test structure, naming, and what is left untested
- commit message and branch shape (`git log --oneline -50`)

**Consistency is the signal.** Something done the same way in twenty places is a
convention; something done two ways is a live disagreement worth flagging.

### 6. Verify one claim

Before reporting, check one thing you have asserted against reality — that the
build command in the README is the one CI runs, that the test directory
actually contains tests, that the entry point you named is referenced. A survey
built entirely from reading has an error rate; one verified claim tells you
roughly what it is.

## Output

```
<name> — one sentence on what it is.

Stack        language(s), framework(s), package manager, lock file y/n
Build        the command that actually builds it        (source: file:line)
Test         the command CI runs                        (source: file:line)
Ship         how it deploys, if the repo says

Entry points
  <what>     file:line
  ...

Shape
  2-4 sentences: the major parts and the seams between them.

Conventions
  - the practised ones, each with where it was observed
  - live disagreements, marked as such

Unknowns
  - what you could not establish, and what it would take
```

Keep it under a page. If it is longer than a page, you stopped surveying and
started reading.

## Anti-patterns

- **Reading source before the manifest.** The manifest reframes everything and
  costs one file.
- **Trusting the README.** It is the least reliable file in most repositories,
  and the most confidently worded.
- **Reporting counts of files or lines.** They are dominated by generated code,
  they answer no question anyone asked, and they go stale immediately.
- **Exhaustive module inventories.** A list of every directory is a directory
  listing with extra steps. The caller can run `ls`.
- **Continuing until you understand it.** The map is done when someone can
  decide where to look.
