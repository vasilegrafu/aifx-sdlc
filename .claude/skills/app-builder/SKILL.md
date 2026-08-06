---
name: app-builder
description: Generate a working part of an application by reading how one or more existing codebases already do it. Use when asked to build, generate, scaffold or add a layer — a database layer, models, repositories, controllers, services, API routes, handlers, React or TypeScript components, jobs, clients — "the way the other project does it", "like in atlas", "matching our existing code", or "combining the best from these repos". Also use when asked what a large codebase's structure is, what its conventions are, how a layer is wired, which conventions are dying, or where two codebases disagree. Reads Python, TypeScript, JavaScript and C# codebases of any size through a structural index rather than by opening files, so it also answers questions about ASP.NET, React or SQLAlchemy code without reading it.
---

# Generating a layer from codebases you were pointed at

You are given one or more codebases and a description in prose. You produce
working code in a target project, shaped the way those codebases shape it.

The whole method rests on one distinction:

> What is **always** true of a set of files is a **contract** — reproduce it.
> What **varies** is an **axis of choice** — decide it deliberately.
> What one codebase always does and another never does is a **disagreement** —
> ask. Do not average.

## Never read the codebase to understand it

A large codebase does not fit anywhere. Opening files until the shape emerges
burns the context and still misses the convention that lives in the files you
did not open.

Index once, query many times, then read two or three files in full — chosen by
the index, not by guessing.

```bash
./.venv/Scripts/python.exe .claude/skills/app-builder/scripts/index.py --name <index-name>
```

With no arguments it indexes every codebase declared in the config — see below.
Explicit roots override that for a one-off. Either way each codebase keeps its
own name in the index, which is what makes disagreement between them visible.
Rebuild whenever a source may have changed; indexing is cheap and staleness is
not. **Never open `index.jsonl`.**

## Configured, not asked for

The codebases available to this skill, and the destination it builds into, are
declared in `config.json` at the root of this repository. Do not ask the user for
paths that are already there.

```json
{
  "app-builder": {
    "repositories": [{ "name": "atlas", "path": "D:/code/solution.atlas" }],
    "solution": "solution.university"
  }
}
```

`solution` may be a plain path or an object carrying `exclude`, for the rare tree
that genuinely is not source.

**You do not need `exclude` to stop a shared library being indexed twice.** When
a target and a source are both linked to the same library, the two junctions
resolve to the same files — and indexing them twice would make every count
wrong, every `DISAGREEMENTS` row compare a file against itself, and every doubly
defined name ambiguous. `index.py` indexes one physical file once, under whichever
root reached it first, and reports how many it skipped. Config order decides the
owner: sources are indexed before the target, so a shared library lands with the
exemplars that call it, which is where you want to read it.

`name` is what the index calls that codebase and what `DISAGREEMENTS` reports
against, so it is worth choosing well. `solution` is where generated
applications are built, relative to this repository unless absolute.

**With one repository configured, `DISAGREEMENTS` never fires** — there is
nothing to disagree with, and step 6 has nothing to settle. Combining the best
of several codebases needs several entries here. If the user asks for that with
one configured, say so rather than implying a comparison happened.

## The target is a codebase too, and it outranks the source

The generated application is indexed alongside its sources, under its own name.
This matters the second time you are asked for something, and it is the failure
you will not notice: read only the source, and every deliberate departure made
last time is faithfully undone. A schema dropped on purpose comes back, because
the source still has it at 100%.

So once the target holds the layer being asked for, **it is the later decision
and it wins.** `shape` labels it and says so; where a feature is universal in
the source and absent from the target, the answer is already settled and there
is nothing to ask.

Ask only about rows where no target column appears. Reintroducing something the
target dropped is not fidelity, it is regression — and the person who dropped it
will have to drop it again.

A directory linked into a solution by junction or symlink is **part of that
solution**, and is indexed as part of it. It sits on the import path; the code
imports through it; splitting it out would describe a codebase that is not the
one on disk. `exclude` exists for the rare tree that genuinely is not source,
and is not the tool for a linked library.

## A library is not an exemplar

A solution usually contains both the application and the library it is built on
— often the linked directory above. They play different roles and must not be
read the same way:

- The **application** is what you copy. Its layer is the thing being reproduced.
- The **library** is what you call. You need its surface — what exists, what each
  method takes — not its style.

Separate them **at query time**, with `--path` to look inside one and
`--not-path` to hold it out:

```bash
scripts/query.py layers --name <index> --not-path 'devfx/*'   # the application
scripts/query.py find   --name <index> --path 'devfx/database/*'  # what it calls
```

A `shape` run across both averages a library's conventions into an
application's and produces a form neither one uses — the same error as averaging
two codebases in step 6. Query-time separation keeps the index faithful to the
solution while still letting you read one side at a time.

## When the library is not there

The application may not be able to reach the library its exemplars call. There
are three answers, and the right one is rarely obvious:

- **Link it**, as the source does — a junction or symlink into the other
  repository. Highest fidelity, and the generated code stays identical to the
  exemplar. The cost is that a linked directory carries no package metadata, so
  **nothing declares its dependencies**: they have to be found by importing it
  until it stops raising, and written down by hand.
- **Reproduce its surface**, minimally — only the methods the generated code
  calls, under the same names. Self-contained, and honest as long as it stays
  small. It stops being honest the moment it grows behaviour of its own.
- **Deviate**, and call the underlying framework directly. Cheapest, and it
  breaks the contract `shape` reported. Only with the user's agreement.

Say which one you took and why. All three are defensible; silently picking one
is not.

## The target is not the source's platform

The contract has a platform baked into it, and the exemplars will not mention it
because to them it is not a variable. Reproducing the contract faithfully onto a
different database, runtime or operating system is where generated code fails —
each failure looking like a different problem, all of them the same seam.

Before generating, enumerate what the source assumes and the target does not:

- **dialect-only DDL** — schemas, `IF EXISTS` forms, collations, identity
- **isolation levels** the target rejects, including the source's default
- **constraint enforcement that is off by default** — SQLite ignores foreign
  keys unless every connection is told otherwise, so `ondelete='CASCADE'` is
  declared and never enforced, and nothing errors until a row is orphaned
- **types with no equivalent**, and how the source spells identity

Each of these is a VARIES that the **target** settles, not the source. Reproduce
what the contract means, not the SQL it happens to emit — and when you diverge,
say so in the file, next to the line that diverges.

## The procedure

Run every script with `./.venv/Scripts/python.exe`. All paths below are relative
to this repository's root.

### 1. Check what you have been given

```bash
scripts/query.py config                    # codebases, destination, indexes built
scripts/query.py meta --name <index-name>  # what a built index actually covers
```

`config` reports each repository as `ok` or `MISSING` — a configured path that
does not exist on this machine is the one failure worth catching before anything
else. No index yet, or one built from the wrong roots? Build it.

Ask for a path only when the config has none and the user has not given one.

### 2. Find the layer

```bash
scripts/query.py layers --name <index-name> --depth 3 --not-path '<library>/*'
```

Directories, class counts and the dominant base class of each. The layer the
user described in prose is one of these rows. If two rows could both be it, say
which you picked and why, in one line — do not ask yet.

Hold out the linked library from every query in steps 2 to 4, or its packages
will crowd out the application's. `--not-path` is repeatable.

`find` narrows further once you have a candidate — `--base`, `--decorator`,
`--symbol` for a name regex, `--files` for paths alone, `--functions` to include
module-level functions.

### 3. Learn its shape — the important step

```bash
scripts/query.py shape --name <index-name> --path '<dir>/*' [--base <Base>]
```

Read the output as separate instructions, not as a report:

- **ALWAYS** — every class in the layer has it. This is the contract. Generated
  code that omits any of it is wrong, whatever it looks like.
- **`nn%`** — usual but not universal. Follow it unless the request says
  otherwise, and say that you did.
- **VARIES** — the axis of choice. Each of these is a decision the request must
  settle, or that you settle and state. Each carries the date it was last
  touched.
- **ATTRIBUTE DETAIL** — what an attribute *is*, not merely that it is there:
  the modal annotation and constructor, and how much of the layer agrees. For a
  data layer this is the real contract — `id` being present everywhere says far
  less than `id` being `Mapped[UUID] = mapped_column(Uuid, primary_key=True)`.
  The `also:` line is the minority form, and is usually a genuine subfamily
  worth understanding before choosing.
- **AGEING** — present, but in nothing touched for over a year. A pattern being
  abandoned still wins on file count. Do not copy these without asking.
- **DISAGREEMENTS** — printed only when the index holds more than one codebase.
  Handle it in step 6.

- **FUNCTIONS CALLED / CALLS ON A RECEIVER** — the layer's vocabulary. What a
  definition calls is part of its shape, and in a framework layer it is nearly
  all of it: `useState` and a codebase's own `useConfig` are declared nowhere.
  `ALWAYS StandardDbCtrl.filter` across a controller layer is as binding as any
  base class.

`--usually` moves the threshold between *usual* and *varies*; the default is 60.
`--lang` narrows to one language when an index holds more than one — a backend
and its frontend have different conventions, and averaging them reports a form
neither one uses.

**`--kind func` when the layer's unit is not a class.** A React component, a
hook, a route handler and most modern JavaScript are functions, and the default
`--kind class` will report that a directory of forty components contains
nothing. `shape` warns when the filter matched more functions than classes;
believe it. `--tech react|sqlalchemy|aspnet|...` narrows to modules importing a
technology, which is how a framework layer is separated from the application
around it.

### 4. Read the exemplars — and only these

```bash
scripts/query.py exemplars --name <index-name> --path '<dir>/*' [--base <Base>]
```

Read the most typical file **in full** — it is what you copy the structure of.
Read one atypical file too: it shows which parts are optional, which the typical
file alone cannot tell you. Copy structure, never domain nouns.

**Typical is not the same as correct.** `exemplars` ranks by how many features a
file shares with its siblings; nothing in that measures whether it works. A file
can be the most representative in the layer and still call a method that does
not exist, because nothing ever ran it. Copying it faithfully then spreads one
dead line across everything you generate.

So when a layer calls into a library, check the names against the **library**,
not against the exemplar. Do not read for this — ask:

```bash
scripts/query.py calls --name <index-name> --on <ReceiverName>
```

It crosses every method invoked on that name against the members that name
defines, and reports the ones that do not exist, with call sites. Run it on the
source before copying, and on your output afterwards.

Where exemplars disagree, the one matching the library wins, however typical the
other is. This is not hypothetical: `.where()` is called four times in the file
`exemplars` ranks most typical, `StandardDbCtrl` has no such method, and that
dead line reached nine generated controllers at once before anything ran.

### 5. Find the wiring

```bash
scripts/query.py imports <an-existing-member> --name <index-name> --chain
```

Every layer has something that makes a new member take effect — a package
`__init__` that imports it, a registry it is added to, a generator that walks
it. **This is where generated code fails silently.** The definition is perfect,
nothing errors, and the thing simply never happens.

`--chain` follows package `__init__` re-exports upward, because the file that
makes a definition take effect is often several hops from the definition, and
**every hop is another file that has to be edited**. Name an existing member of
the layer rather than the base class: you want the path a sibling already
travels, which is the path yours must travel too.

Find that chain now, before generating, so the files it forces you to edit are
part of the plan rather than a discovery afterwards.

### 6. Settle disagreements — ask once, not every time

```bash
scripts/query.py decisions --name <index-name>
```

If a recorded answer settles a disagreement, apply it silently. `shape` also
prints these under `DISAGREEMENTS`, so the two questions — what differs, and
what was already decided — arrive together.

For anything not recorded, ask the user — one question per genuine
disagreement, with what each codebase actually does and the counts. Then record
the answer, in their words:

```bash
scripts/query.py decide --name <index-name> --id primary-key-type \
    --decision "atlas: Uuid surrogate keys. other: natural String keys." \
    --answer "Uuid"
```

The file lives in `decisions/<index-name>.md`, **not** in `.data/` — an index
rebuilds in seconds and an answer cannot be recovered from anything, so it is
kept out of the directory that is safe to delete, and it is meant to be
committed.

An answer is a standing instruction, not a cache. Apply it without mentioning
it, unless the request contradicts it — then the request wins and you re-record
the row under the same id.

Never average two codebases into a form neither one uses.

### 7. Generate

Into the destination named by `solution` in the config, unless the user names a
different target project. Look at that directory before writing: if it already
holds an application, it **is** the application root and you extend it in place;
if it holds applications in named subdirectories, add another. Do not impose a
level of nesting the destination does not already use.

Write the definition files and the wiring edits from step 5 in the same pass. An
application generated without its registration chain is the failure this whole
procedure exists to avoid, and writing the two separately is how it happens.

Never write into an indexed codebase. Those are read-only sources; the index
records where their files are, not permission to edit them.

### 8. Prove it, do not assume it

A generated application has no proof of its own yet, so build it in four rungs.
Each catches something the one before cannot, and skipping a rung means claiming
what you did not check.

**Rung 1 — it imports, and something imports it.**

```bash
./.venv/Scripts/python.exe .claude/skills/app-builder/scripts/smoke.py \
    [--app <subdirectory>] --python <interpreter> [--env KEY=VALUE] <generated files>
```

Paths are relative to the application root. Omit `--app` when the solution
directory is itself that root. `--env` is for a module that reads configuration
at import time, which is common enough to expect: the exemplar does it, so the
generated code does too, and without the variable the import fails for a reason
that has nothing to do with the code.

`IMPORTS` catches the loud failures. `REACHABLE` catches the quiet one — a class
nothing imports, which is the failure step 5 exists to prevent.

`smoke.py` checks **Python**; hand it anything else and it says so rather than
counting it as passing. The other three have their own rung 1, and
`query.py proof` prints the one that fits each language it found:

| Language | Rung 1 |
|---|---|
| Python | `smoke.py` — imports, and something imports it |
| TypeScript | `tsc --noEmit` |
| JavaScript | `node --check <file>` per file, or the project's lint script |
| C# | `dotnet build` |

Only the Python rung checks reachability, because only in Python does an
unimported class silently fail to register. The barrel chain is answered from
the index in every language by `imports <Symbol> --chain` — an `index.ts` that
fails to re-export is the same failure as an `__init__.py` that does, and it is
just as silent.

Then re-index and ask the two questions nothing else answers — whether the
output still keeps the contract that produced it, and whether it calls anything
that does not exist:

```bash
scripts/index.py --name <index-name>
scripts/query.py conform --name <index-name> \
    --repo <source> --path '<source layer>' \
    --target-repo <target> --target-path '<generated layer>'
scripts/query.py calls --name <index-name> --on <library or base>
```

`conform` reports what is ALWAYS true of the source and not of the output. Every
row is either a departure you can name or a mistake; there is no third kind.

**Rung 2 — the entry point runs.** Execute the thing the layer exists to feed:
the generator, the migration, the server startup. Well-formed code that no one
has run is not working code.

**Rung 3 — the behaviour that fails silently actually holds.** This is the rung
that earns the others, and it is the one nothing will do for you. Write a short
throwaway script that exercises the guarantees the schema and the contract claim
to make, and watch each one:

- a write followed by a read back
- a uniqueness rule rejecting a duplicate
- a reference rejecting an unknown parent
- a cascade actually removing dependants
- an upsert updating rather than inserting a second row

Every one of those can be declared, generated perfectly, and not happen. That is
the whole reason this skill exists, and it is invisible to rungs 1 and 2.

**Rung 4 — pin it in the layer's own tests**, so the next change has to keep it
true. Rung 3 proves it once; rung 4 proves it from then on.

The interpreter must be one that can import what the generated code imports.
Pointing `--python` at one that cannot turns a missing dependency into what
looks like a generation error — so check before concluding the code is wrong.

Look at where the dependencies are declared before assuming which interpreter
that is — one venv at the repository root, one per application, or neither, in
which case `proof` reports the source codebase's own, which can at least import
what the code imports.

Whatever you add to a generated application, add its dependency to the
`requirements.txt` that governs the venv it runs in. A skill never needs one:
skills import nothing but the standard library, which is what lets one be copied
into another checkout and still work.

For rungs 2 and 4, do not ask what the project runs as proof — the repository
already says:

```bash
scripts/query.py proof --name <index-name>
```

It reports, **per language and including the generated target**: the test
configuration wherever it lives, the toolchain that can actually run it, the
rung-1 command, any npm scripts, and the entry points — ranked, so a schema
generator or migration outranks a module with a demo block at the bottom. Run
the one that would exercise what you generated. If there is none, say so
plainly rather than calling the
work verified.

### 9. Report

State, briefly:

- which exemplar the structure came from, by path
- what you reproduced because it was contract
- every VARIES you chose, and on what grounds — including every place the
  target's platform forced a departure from the source's
- which rungs of step 8 you climbed, and what each one actually proved
- anything you could not verify

And report **what generating found wrong in the source**. Reading a layer closely
enough to reproduce it, then running the result, exercises that layer harder than
its own repository may ever have — a method that is never called, a convention
two files disagree about, a constraint that was never enforced. The source is
read-only, but the finding is not: hand it back, with the file and line. Working
around it silently leaves the next person to discover it again.

## When the layer does not exist yet

If nothing in the index resembles what was asked for, say that. Generating a
layer with no exemplar is ordinary work, not this skill's method — the skill's
value is fidelity to existing code, and there is none to be faithful to. Offer
the nearest layer as a source of conventions instead.

## Boundaries

- **Python, TypeScript, JavaScript and C#** — four languages, four extractors,
  each on a real parser rather than on pattern matching, and every record says
  which language produced it and at what fidelity. Python needs nothing;
  TypeScript needs `node` and the project's own `node_modules/typescript`;
  JavaScript needs `node` and `acorn`; C# needs the .NET SDK — each present by
  definition in a codebase of that language. Nothing else is covered and must
  not be guessed at. A language whose toolchain is missing, and a file type no
  extractor claims, are both **reported** — as `skipped` and as `not covered` in
  `meta` — never treated as absent. Check `meta` before concluding that a
  codebase does not do something: absent evidence and absent convention look
  identical in `shape` and are not the same thing.
  `references/languages.md` holds the mapping, the traps, and how to add one.
- The index holds facts derived from other people's repositories. It lives in
  `.data/` beside this file — inside a tracked skill, so it must stay ignored,
  and nothing from it belongs in a tracked file.
- `MANUAL.md` is written for the person, not for you: what each command answers,
  how to read `shape` output, and what the tool cannot do. Point them at it when
  they ask how to run something themselves.
- `references/generating.md` holds the detail: turning prose into a spec,
  reading `shape` output closely, what to do when exemplars conflict inside one
  codebase, why not to improve a signature that looks clumsy, why code that
  works from one directory may work from nowhere else, and what you may honestly
  claim to have proved.
