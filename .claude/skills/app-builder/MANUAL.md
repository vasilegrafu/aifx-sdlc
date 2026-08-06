# app-builder — user manual

Read a codebase you did not write, find out what it actually does, and generate
new code that matches it.

`SKILL.md` is the procedure Claude follows. This file is for you: what the tools
do, how to run them yourself, and what the output means.

---

## What it is for

Two jobs, and the second depends on the first.

**Understanding a codebase.** How is it laid out, what is the contract of a
layer, which conventions are dying, what does the wiring look like, where do two
repositories disagree. Answers come from a structural index, so it works on a
codebase far too large to read.

**Generating a layer that matches.** Models, controllers, endpoints, components
— shaped the way the source shapes them, then checked against the contract that
produced them.

You can use the first without ever using the second.

---

## Setup

Point it at codebases in `config.json`, at the root of this repository:

```json
{
  "app-builder": {
    "repositories": [
      { "name": "atlas", "path": "D:/Dev.Work/project.finance/solution.atlas" }
    ],
    "solution": "solution.university"
  }
}
```

- **`repositories`** — what to read. `name` is what queries call it.
- **`solution`** — where generated code is built. It is indexed too, and once it
  holds a layer it **outranks the sources** for that layer: a convention it
  deliberately dropped will not be reintroduced from a source that still has it.
- Either entry may take `"exclude": ["some/dir"]` for a tree that is not source.

Check it before anything else:

```bash
./.venv/Scripts/python.exe .claude/skills/app-builder/scripts/query.py config
```

Every configured path is reported `ok` or `MISSING`. A path that does not exist
on this machine is the failure worth catching first.

### What each language needs

| Language | Needs | Notes |
|---|---|---|
| Python, `.py` `.pyi` | nothing | the parser is in the standard library |
| TypeScript, `.ts` `.tsx` `.mts` `.cts` | `node` + the project's `node_modules/typescript` | present by definition in a TS project |
| JavaScript, `.js` `.jsx` `.mjs` `.cjs` | `node` + `node_modules/acorn` | ships inside eslint, vite, webpack, rollup |
| C# | the .NET SDK | the adapter builds itself on first use, ~20s, then caches |

A language whose toolchain is missing is **skipped and reported**, never silently
treated as absent.

---

## Quick start

```bash
# 1. build the index (reads config.json)
./.venv/Scripts/python.exe .claude/skills/app-builder/scripts/index.py --name atlas

# 2. what is in there
scripts/query.py layers --name atlas --depth 3

# 3. what is the contract of a layer
scripts/query.py shape --name atlas --path 'database/*/models/*'

# 4. which file to copy
scripts/query.py exemplars --name atlas --path 'database/*/models/*'
```

Indexing is cheap — a few seconds for hundreds of files — so rebuild whenever a
source may have changed. Staleness costs more than the rebuild.

**Never open `index.jsonl`.** It is megabytes, and every question you would ask
it has a subcommand that answers in a few hundred lines.

---

## Reading `shape` — the one thing worth learning

Everything else is navigation. This is the output that tells you what a layer
*is*:

```
12 classes  (atlas 3, solution.university 9)   touched 2026-06 .. 2026-08

== BASE CLASSES ==
  ALWAYS   BaseDatabaseModel
== ATTRIBUTES ==
  ALWAYS   id
   87%     created_at
  VARIES   instrument_id (43%, last 2026-08), name (31%, last 2024-01)
== ATTRIBUTE DETAIL ==
  id  Mapped[UUID] 67%   mapped_column(Uuid, default, primary_key) 67%
      also: Mapped[str] x1; mapped_column(String(256), primary_key) x1
== AGEING ==
  2023-01  methods: p  (16%)
```

Read it as instructions, not as a report:

- **ALWAYS** — the contract. Code that omits any of it is wrong, however good it
  looks.
- **`nn%`** — usual. Follow it unless you have a reason, and say what the reason
  was.
- **VARIES** — a fork in the layer, not a weak convention. Usually it means a
  subfamily: *fewer than half the models have a foreign key because fewer than
  half the entities reference another.* Decide which side you are on.
- **ATTRIBUTE DETAIL** — what an attribute *is*, not that it exists. `id` being
  present everywhere says far less than `id` being `Mapped[UUID]`. The `also:`
  line is the minority form, and is usually a real decision worth understanding.
- **AGEING** — present, but only in files nobody has touched for a year. A
  pattern being abandoned still wins on file count. Do not copy these blindly.
- **DISAGREEMENTS** — appears when the index holds more than one codebase. If
  one side is your generated target, it has already decided and it wins.

`--usually 50` moves the line between *usual* and *varies*. `--lang python`
narrows when an index holds a backend and a frontend — averaging the two
describes a form neither one uses.

---

## Recipes

**I inherited this codebase and have no idea what is in it**

```bash
scripts/query.py layers --name X --depth 3
scripts/query.py proof  --name X            # tests, entry points, interpreter
scripts/query.py shape  --name X --path '<the layer that looked interesting>/*'
```

**I need to add a tenth model to a layer that has nine**

```bash
scripts/query.py shape     --name X --base <TheBaseClass>
scripts/query.py exemplars --name X --base <TheBaseClass>
scripts/query.py imports   --name X <AnExistingMember> --chain
```

The last one matters most. It follows the registration chain upward and lists
**every file that must change** for a new member to take effect. Miss one and
nothing errors — the table is simply never created.

**Did the code I generated keep the contract?**

```bash
scripts/index.py --name X                   # re-index, target included
scripts/query.py conform --name X \
    --repo <source> --path '<source layer>' \
    --target-repo <target> --target-path '<generated layer>'
```

Every DROPPED row is either a departure you can name or a mistake. There is no
third kind.

**Is anything calling a method that does not exist?**

```bash
scripts/query.py calls --name X --on <ClassName>
```

Crosses every call made on that name against the members it defines. This found
four live call sites in a real codebase for a method that has never existed.
Read the C# caveat below before trusting it there.

**Which conventions are dying?**

Run `shape` over the layer and read the `AGEING` section. Anything listed
survives only in files nobody has touched for over a year.

---

## Command reference

All commands take `--name <index>`. Filters marked ● are shared by `find`,
`shape`, `exemplars`, `imports` and `calls`.

| Command | Answers |
|---|---|
| `config` | which codebases and destination are configured, and whether they exist |
| `meta --name X` | what an index covers, when built, which languages, what was skipped |
| `layers` | what parts exist — directories, class counts, dominant base |
| `find` | the definitions matching a filter, or `--files` for paths alone |
| `shape` | what is ALWAYS true, what VARIES, what is ageing, where repos disagree |
| `exemplars` | the most typical file to copy, and the outlier that shows what is optional |
| `imports SYMBOL` | who imports it; `--chain` follows re-exports up the registration chain |
| `calls --on NAME` | methods called on a name vs. the ones it defines |
| `conform` | whether generated code still keeps the source's contract |
| `proof` | how a codebase proves itself — test config, test dirs, entry points, interpreter |

Shared filters ●: `--path GLOB`, `--not-path GLOB` (repeatable), `--base`,
`--decorator`, `--symbol REGEX`, `--repo`, `--lang`, `--limit`.

**Building an index**

```bash
scripts/index.py --name X                 # every configured repository
scripts/index.py --name X <path> <path>   # explicit roots, ignoring config
    --no-git         skip last-commit dates (recency falls back to mtime)
    --no-solution    sources only, leaving out the generated target
    --max-bytes N    skip files larger than this
```

**Checking the tool itself**

```bash
scripts/selftest.py
```

Feeds one fixture to every extractor and asserts they emit the same records —
same keys, same language stamp, the same calls recorded. Run it after touching
an extractor. Four languages are deliberate near-copies of each other in places,
and this is what keeps the copies honest.

**Checking generated Python**

```bash
scripts/smoke.py --python <interpreter> [--app NAME | --root PATH] \
                 [--env KEY=VALUE] <files...>
```

`IMPORTS` catches the loud failures. `REACHABLE` catches the quiet one — a class
nothing imports, which never takes effect and never errors. `--env` is for code
that reads configuration at import time. Hand it non-Python files and it says so
rather than counting them as passing.

---

## What it cannot do

**It reads structure, not behaviour.** `shape` knows a method exists and what it
calls. It does not know what it means.

**Python, TypeScript, JavaScript and C# only.** Anything else is skipped, and
reported as skipped.

**C#: `calls --on <TypeName>` largely does not work.** C# is read syntax-only, so
an instance call is attributed to the *variable* it was made on, not to that
variable's type — real receivers look like `_userManager`, `_logger`, `builder`.
Static calls (`calls --on Assert`) work. The output says `NOT RESOLVED` rather
than `MISSING` there, and means it.

**JavaScript reads JSDoc for types.** `@type {T}` and `@returns {T}` fill in what
annotations would; a codebase that documents nothing has a thin `ATTRIBUTE
DETAIL`, and there is nothing to be done about that.

**Reachability is a Python idea.** In Python a class nothing imports never
registers. In C# it compiles perfectly, and the equivalent failure is a service
never added to the container — a different query.

**`conform` compares feature names.** It will tell you a `__table_args__` is
missing; it will not tell you the schema *inside* it changed. Pair it with
`calls`, which covers the other half.

---

## Troubleshooting

**`no index named 'X'`** — build it: `index.py --name X`.

**A repository shows `MISSING` in `config`** — the path in `config.json` does not
exist on this machine. Config holds absolute paths and is expected to be wrong on
someone else's.

**`N typescript files SKIPPED -- node is not on PATH`** — install node, or accept
a Python-only index. It is reported rather than silently omitted precisely so you
can decide.

**`no node_modules/typescript above them -- run npm install`** — the frontend has
not been installed. The compiler is found by walking up from each file, so a
monorepo with several packages needs each one installed.

**The index contains files nobody wrote** — build output. `dist/`, `obj/` and
friends are skipped by name, `dist.dev` and the like by prefix, and minified
bundles by line length. If something still gets through, add `exclude` to that
repository in `config.json`.

**`shape` output is a mush of low percentages** — the "layer" is really two
layers sharing a directory. Narrow with `--base`, `--decorator`, or a deeper
`--path`, and run it on each side.

**Counts look doubled** — they should not. One physical file is indexed once,
even when two solutions link to the same library through junctions. `meta` reports
`duplicates_skipped` so you can confirm.

---

## Where things live

```
.claude/skills/app-builder/
  SKILL.md                 the procedure Claude follows
  MANUAL.md                this file
  references/
    generating.md          how to read output closely; what to do when it conflicts
    languages.md           per-language mapping, traps, and how to add one
  scripts/
    index.py               build an index
    query.py               ask it questions
    smoke.py               check generated Python
    selftest.py            check that the extractors still agree
    extractors/            one per language
    adapters/              the toolchains they shell out to
  .data/                   indexes — gitignored, rebuildable, never edited by hand
```

Delete `.data/` any time. It is derived, and `index.py` rebuilds it in seconds.
