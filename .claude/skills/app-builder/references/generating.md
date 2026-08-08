# Generating: the parts of the method that need more than a step

Read this when the main procedure in `SKILL.md` meets something it does not
settle on its own.

Most worked examples below are Python, because that is where they were learned.
Each has an analogue in the other three languages, and where the analogue is not
obvious it is named. Two are worth knowing before you start:

- **The unit of a family is not always a class.** A React component, a hook, a
  route handler and most modern JavaScript are functions, and `shape --kind
  class` describes a directory of forty of them as empty. Read a family with
  `--kind func` when its members are functions, and remember that such a family's
  contract lives almost entirely in what it *calls*.
- **The registration chain has a different name in each language.** In Python it
  is `__init__.py`, in TypeScript and JavaScript `index.ts` / `index.js`, and in
  C# it is not a file at all — an unreferenced class compiles, and the same
  failure appears as a service never added to the container. `imports --chain`
  follows the first two; for the third, query the composition root.

## Turning prose into a spec

The request arrives as a sentence, not a schema. Most of what a schema would
have said is already in the codebase — the point is to take it from there rather
than from the user.

Extract from the sentence only what the codebase cannot tell you:

- **the family** — which part of the application (settled by `families`)
- **the entities** — the domain nouns, and any fields the user named explicitly
- **the relations** — which entity points at which

Take from the codebase, never ask:

- the base class, the file layout, the naming of files and tables and indexes
- which methods a member of this family carries
- the key strategy, the imports, the registration chain
- every default the ALWAYS section reports

Ask only when a **VARIES** row is genuinely load-bearing for what was requested
and nothing in the sentence settles it. Two entities that "belong to" each other
tell you there is a foreign key; they do not tell you the delete behaviour, and
if the family varies on that, it is worth one question.

Restate the spec you extracted in one short block before generating. A wrong
noun caught there costs a sentence; caught after generation it costs the pass.

## Reading `shape` output closely

```
== ATTRIBUTES ==
  ALWAYS   id
   87%    created_at
  VARIES   instrument_id (43%), name (31%), symbol (12%)
```

- `ALWAYS id` — every generated class has `id`, in the same form the exemplar
  uses. Not "an identifier"; that form.
- `87% created_at` — include it. If you leave it out, say so and why.
- `VARIES instrument_id (43%)` — this is not a weak convention, it is a
  **subfamily**: fewer than half the classes have a foreign key because fewer
  than half the entities reference another. The percentage is describing the
  domain, not a disagreement about style.

That last reading matters most. A `VARIES` row is usually a fork in the family,
and the fork is what the request has to choose. Find which side it is on before
generating, not while.

## Percentages are not the whole signal

Two things qualify every percentage above.

**Dates.** Every row carries when it was last touched, and the `AGEING` section
lists what has been in nothing for over a year. Count and currency disagree more
often than people expect: a convention can hold a majority precisely because the
files that use it stopped changing. When the majority form is ageing and the
minority is recent, the minority is the convention and the majority is the
fossil — say so and ask, rather than following the count.

**Attribute detail.** `ALWAYS id` means the name is universal. It says nothing
about the type, and a family that agrees on names while disagreeing on types has
no contract worth copying. Read the `ATTRIBUTE DETAIL` section for what each
attribute actually is:

```
  id  Mapped[UUID] 67%   mapped_column(Uuid, default, primary_key) 67%
      also: Mapped[str] x1; mapped_column(String(256), primary_key) x1
```

Read that as: the default is a UUID surrogate key, and one entity uses a natural
string key instead. Which is not noise — it is the decision row. An entity with
a natural key of its own follows the minority; everything else follows the
default. One `also:` line of this kind is worth more than any count on its own.

## When one codebase disagrees with itself

`shape` over a whole family can report a mush of low percentages because the
"family" is really two families sharing a directory. The fix is to split the set,
not to average it:

```bash
scripts/query.py shape --path '<dir>/*' --base <Base>
scripts/query.py find  --path '<dir>/*' --files
```

Narrow by `--base`, by `--decorator`, or by a `--path` one level deeper, and run
`shape` on each side. When both sides come back crisp, you have found the real
families, and the request belongs to exactly one of them. When the same request
matches both, that is a genuine question for the user.

`exemplars` on the narrowed set then gives a typical file worth copying. On an
un-narrowed set it gives a typical file worth nothing.

## Do not improve the exemplar -- silently

The other way to get this wrong is the opposite of copying a mistake: copying it
correctly and then making it nicer.

A signature that looks clumsy usually is not. The source's controllers take
`session` as a required first parameter, so every caller writes `None`
explicitly:

```python
StudentDbCtrl.get_by_id(None, id=student_id)
```

Defaulting it to `None` reads better and is wrong — `save(entity)` then binds
the entity to `session`, and the error arrives one frame away from anything that
explains it. The clumsiness was carrying information.

So: **when your version is more ergonomic than the exemplar, find a caller before
you keep it.** `imports <Symbol>` lists them, and one real call
site settles in a second what an argument about taste will not settle at all.
If the improvement survives that, keep it and say you deviated.

That rule is about *acting*, not about *mentioning*, and the distinction matters
because for a long time this section suppressed both. Reproducing the source
without comment is right; reproducing it without ever telling the user there was
an alternative is not. Where the source simply does not do something -- no
timestamps, no relationships, no delete policy -- there is no `VARIES` row to
find and no question gets asked, because an absence leaves no record in the
index at all. Propose, mark it as a departure, and let the user decide.

### The two silences

There are exactly two ways a decision escapes without ever being raised, and
they need different instruments:

| The source... | Leaves in the index | Caught by |
|---|---|---|
| does it two ways | a `VARIES` row | `questions` |
| does not do it at all | nothing | knowing the family kind; no query can |
| does it one way, always | an `ALWAYS` row read as contract | `practice` |

The third line is the least intuitive, because an `ALWAYS` row
looks like the *opposite* of a silence -- it is the loudest thing `shape`
prints. But loud is not the same as examined. Unanimity is what makes something
a contract, and it is equally what makes it invisible as a choice: nothing forks,
so nothing ranks it, so nobody asks.

Three worked cases, to show the difference between a fossil and a convention
doing its job:

- **A real fossil.** Every module reaches for `os.path`, the corpus moved to
  `pathlib` years ago, and nothing in the codebase depends on the difference.
  Worth raising; cheap to change; nothing breaks.
- **Not a fossil, however old it looks.** `session` as a required first
  parameter. Clumsy, universal, and load-bearing -- the caller check finds out
  in one command, which is why the caller check is not optional.
- **A fossil you still must not touch unasked.** POST-for-reads across an
  entire web API. The corpus disagrees; changing it also rewrites every client.
  Propose it *with* the blast radius, and expect "no" to be the right answer.

The failure mode of this whole section is not missing an improvement. It is a
generation that spends its attention arguing about the exemplar's taste instead
of reproducing it. Fidelity is still the default. Raise the handful of cases
where the default is genuinely wrong, and nothing else -- a proposal without
evidence, from `practice` or from a failure you can name, is noise wearing the
costume of diligence.

## Working from one directory is not working

Generated code gets tested from the directory it was generated into, and passes.
Three separate things then break the first time something runs from elsewhere:

- **a relative path in configuration**, resolved by one caller and not another.
  If the generator resolves it and the session maker does not, both work from
  inside the application and neither from the repository root. Put the rule in
  one module and have every caller use it.
- **an interpreter path** passed relative to where you are standing, then used
  in a subprocess whose working directory is somewhere else.
- **a package named after a dependency.** Running a script puts *its own
  directory* on `sys.path`, so `database/sqlalchemy/` shadows the real
  SQLAlchemy for anything launched from inside `database/`. The library the
  exemplar's own copy sits in gets away with the name because it is nested a
  level deeper and never lands on the path root. Never name a generated package
  after something it imports.

Run the entry point from **two** working directories before reporting it works —
the application root and the repository root. All three of the above pass every
static check and fail only there.

The other languages have the same disease under different names, and the cure is
the same — run it from somewhere else before believing it:

- **TypeScript and JavaScript** resolve `.` imports against the importing file
  and bare specifiers against the nearest `node_modules`, so a package that
  works inside `webapp/` fails from the repository root. A path alias in
  `tsconfig.json` that the bundler honours and `node` does not is the same bug
  with a configuration file in front of it.
- **C#** resolves content and appsettings against the *working directory*, not
  the assembly, so a service that reads configuration works under `dotnet run`
  from the project directory and not from the solution directory.

## Index scale

The index holds one record per module, class and module-level function —
signatures and structure, never bodies. It runs roughly a few kilobytes per
source file, so even a very large codebase produces a file that queries in
seconds and that no one ever needs to open.

`index.py` skips vendored trees, caches, virtualenvs and build output, and
records files it cannot parse as `unparsed` rather than failing. If `meta.json`
reports an unparsed count that is more than a stray file or two, the roots
probably include something that is not source — check before trusting `shape`.

## Reporting proof honestly

The rungs are in `SKILL.md`. What matters here is what you may then claim.

Say which rung you reached, and claim only that. `smoke.py` proves two things
and no more: the modules import, and something imports what they define. It
cannot tell you the code is right. An entry point that runs proves the wiring,
not the behaviour. Only rung 3 touches the guarantees that fail silently, and
only rung 4 keeps them true after the next change.

Name what you did not check, in the same breath. A family whose SQL Server
branches have never executed is generated and partly unverified, and saying so
costs a sentence — while calling it working because it looked right costs
whoever believes you.

Two failures read identically and are not the same, so separate them before
reporting either: **generated code that is wrong**, and **an interpreter that
cannot import what the code imports**. Check where the dependencies are declared
before concluding the first. `query.py proof` reports the interpreter living in
the source tree, which can at least import what the source imports.

If there is no proof available at all, or none of it can run here, say that
plainly. An honest "generated, unverified" is a usable result. A confident one
that turns out to be wrong is not.
