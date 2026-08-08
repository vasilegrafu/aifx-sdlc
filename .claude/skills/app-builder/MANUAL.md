# app-builder — user manual

Read a codebase you did not write, find out what it actually does, and generate
new code that matches it.

`SKILL.md` is the procedure Claude follows. This file is for you: what the tools
do, how to run them yourself, and what the output means.

---

## What it is for

Two jobs, and the second depends on the first.

**Understanding a codebase.** How is it laid out, what is the contract of a
family, which conventions are dying, what does the wiring look like, where do two
repositories disagree. Answers come from a structural index, so it works on a
codebase far too large to read.

**Generating a family that matches.** Models, controllers, endpoints, components
— shaped the way the source shapes them, then checked against the contract that
produced them.

You can use the first without ever using the second.

**A family is just a set of sibling files that look alike.** Twelve models in
`models/`, forty handlers in one flat `routes.py`, the components in
`components/`, or one folder per feature where the siblings are the other
feature folders. It is not an architectural layer and does not require your
application to have any: what the method needs is **repetition**, so that you
are generating the seventh of something and there are six to learn from. If
nothing in your codebase repeats, there is no contract to be faithful to and
this tool has no advantage over writing the code by hand — which it will say
rather than pretend otherwise.

---

## Setup

Point it at codebases in `config.json`, at the root of this repository:

```json
{
  "app-builder": {
    "exemplar_corpus": [
      { "name": "atlas", "path": "D:/Dev.Work/project.finance/solution.atlas" }
    ],
    "solution": "solution.university",
    "questions": "many",
    "reference_corpus": [
      { "name": "django", "repo": "https://github.com/django/django.git" }
    ]
  }
}
```

- **`exemplar_corpus`** — the codebases you copy. `name` is what queries call it.
- **`solution`** — where generated code is built. **Not indexed:** it is the
  destination, not a source, and a stored copy is stale as soon as anything is
  generated into it. Indexing it also skewed every measurement, because the
  generated app is usually larger than the slice of the exemplar being copied —
  `shape` over a models family reported 10 classes of which 7 were the generated
  app. `conform` and `questions --target-path` read it fresh from disk instead,
  scoped to the family you name, which is faster and never stale.
  `index.py --with-solution` puts it in the index if you want it there.
- **`reference_corpus`** — widely-used codebases indexed as **evidence**, never as
  templates. Declared by `repo` URL and fetched into the skill's own
  `.reference_corpus/<name>` by `scripts/fetch.py`; nothing here is a local path, so the corpus is
  reproducible on any machine. They answer "is this still how anyone builds it", which one codebase
  cannot. Held out of every command except `practice` (and `deps`, only when
  passed `--references`) -- see "Is this still how anyone builds it?" under
  Recipes for why that matters.
- Any entry may take `"include": ["dir", "dir/sub"]` to read *only* those
  subtrees, or `"exclude": ["some/dir"]` to drop some. For a reference, prefer
  `include`: what you want from a library's repository is the part showing it
  being **used** (`examples/`), not its internals. A blacklist means naming
  everything you do not want and silently indexing whatever you miss. The
  repository's own top-level manifest is kept either way.
- **`questions`** — how eagerly to ask. `"many"` asks at every genuine decision
  point as the work reaches it; `"key"` asks only what is expensive to reverse;
  `"none"` decides everything and reports it.

Questions arrive **throughout**, not in one batch at the start — a decision about
delete behaviour cannot be raised before the entities exist. Each one offers
several real options and the choice to write your own wording. Whatever the
setting, every generation still ends with the numbered list of choices made, and
you can change any of them then.

This used to be a number, and the number was wrong: capping at three does not
make the fourth decision disappear, it makes it a silent guess.

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
| TypeScript, `.ts` `.tsx` `.mts` `.cts` | `node` + `typescript` | the skill ships its own (pinned 5.x); the indexed project's is preferred when it has one |
| JavaScript, `.js` `.jsx` `.mjs` `.cjs` | `node` + `acorn` | the skill ships its own; the indexed project's is preferred when it has one |
| C# | the .NET SDK | the adapter builds itself on first use, ~20s, then caches |
| HTML templates, `.html` `.jinja` `.j2` | nothing | Django and Jinja, read by regex — `heuristic` fidelity |
| Stylesheets, `.css` `.scss` `.less` | nothing | tokens, mixins and `@import`; `.sass` is not read |
| Manifests, `package.json` `pyproject.toml` `requirements*.txt` `.csproj` | nothing | read for declared dependencies and scripts, not as source; see `deps` |
| Vue `.vue`, Svelte `.svelte` | whatever the script block is written in | split first, then read as TypeScript or JavaScript |
| Razor `.razor` `.cshtml` | the .NET SDK | only the `@code` block is C#; the rest is markup |

A language whose toolchain is missing is **skipped and reported**, never silently
treated as absent.

---

## Quick start

There is **one index**, and it holds every configured repository *plus* the
solution — each in its own directory, under the role it was configured as.
Holding them together is what makes `DISAGREEMENTS` possible. `index.py` has no
per-repository filter; `query.py --repo` is where you narrow to one.

```bash
# 1. build the index: every configured repository, plus the solution
./.venv/Scripts/python.exe .claude/skills/app-builder/scripts/index.py

# ... and after editing your own code, rebuild only that:
#     index.py --only solution.university      (seconds, not minutes)

# 2. what is in there
scripts/query.py families --depth 3

# 3. what is the contract of a family
scripts/query.py shape --path 'database/*/models/*'

# 4. which file to copy
scripts/query.py exemplars --path 'database/*/models/*'
```

Indexing is cheap — a few seconds for hundreds of files — so rebuild whenever a
source may have changed. Staleness costs more than the rebuild.

**Never open the index.** It is a directory per repository under
`.indexes/<role>/<repo>/`, megabytes in total, and every question you would ask
it has a subcommand that answers in a few hundred lines.

```
.indexes/
  exemplar_corpus/atlas/     index.jsonl  meta.json
  solution/<yours>/          index.jsonl  meta.json
  reference_corpus/django/   index.jsonl  meta.json
  meta.json                  the roll-up, recomputed every build
```

**The role is the directory, not a field.** That is what holds references out of
`shape`, `families`, `exemplars`, `questions` and `DISAGREEMENTS` — those commands
do not walk into `reference_corpus/`, so there is no roles map that can be
absent, stale, or disagree with the index it describes.

The split is what makes `--only` possible: a full build of the whole corpus
takes minutes, rebuilding one repository takes under a second, and every other
directory is left untouched. Each repository's own `meta.json` carries its
totals and a record of which physical files it owns, so a partial rebuild still
reports the whole index honestly and cannot double-count a linked library.

The roll-up is never edited, only recomputed from those files. That is
deliberate: when totals lived in one shared document, a partial rebuild had to
merge back what it had not read, and the version that forgot dropped every
untouched repository — until the summary described three repositories while
twenty sat on disk. A summary that can only be recomputed cannot drift.

---

## Reading `shape` — the one thing worth learning

Everything else is navigation. This is the output that tells you what a family
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
== DISAGREEMENTS ==
   solution.university is the generated target, not another source.
   Where it differs it has already decided, and it wins.
  attributes: schema        atlas 3/3, solution.university 0/9
```

Read it as instructions, not as a report:

- **ALWAYS** — the contract. Code that omits any of it is wrong, however good it
  looks.
- **`nn%`** — usual. Follow it unless you have a reason, and say what the reason
  was.
- **VARIES** — a fork in the family, not a weak convention. Usually it means a
  subfamily: *fewer than half the models have a foreign key because fewer than
  half the entities reference another.* Decide which side you are on.
- **ATTRIBUTE DETAIL** — what an attribute *is*, not that it exists. `id` being
  present everywhere says far less than `id` being `Mapped[UUID]`. The `also:`
  line is the minority form, and is usually a real decision worth understanding.
- **AGEING** — present, but only in files nobody has touched for a year. A
  pattern being abandoned still wins on file count. Do not copy these blindly.
- **DISAGREEMENTS** — appears when the index holds more than one codebase. If
  one side is your generated target, it has already decided and it wins.

- **FUNCTIONS CALLED / CALLS ON A RECEIVER** — the family's vocabulary. For a
  data-model family this is a minor section; for anything built on a framework it is
  the main one, because nothing is declared. `ALWAYS StandardDbCtrl.filter`
  across nine controllers is as much a contract as any base class, and a tenth
  controller calling `.where` instead is the kind of thing that reaches
  production because it parses.

`--usually 50` moves the line between *usual* and *varies*. `--lang python`
narrows when an index holds a backend and a frontend — averaging the two
describes a form neither one uses.

### The same command, on a React family

```bash
scripts/query.py shape --kind func --tech react --path 'webapp/src/components/*'
```

```
25 functions  in atlas   touched 2026-06 .. 2026-06
  built on: react (100%), mui (52%)

== PARAMETERS ==
  VARIES   children (36%), sx (32%), props (28%)
== FUNCTIONS CALLED ==
  VARIES   useState (24%), useEffect (20%), useRef (16%), useConfig (12%)
```

`useConfig` is the one worth stopping on: a hook this codebase wrote itself.
Nothing about it is declared anywhere, and a family's local convention is
frequently a name like that one.

---

## Recipes

**I inherited this codebase and have no idea what is in it**

```bash
scripts/query.py families --depth 3
scripts/query.py proof             # tests, entry points, interpreter
scripts/query.py shape  --path '<the family that looked interesting>/*'
```

**I need to add a tenth model to a family that has nine**

```bash
scripts/query.py shape     --base <TheBaseClass>
scripts/query.py exemplars --base <TheBaseClass>
scripts/query.py imports   <AnExistingMember> --chain
```

The last one matters most. It follows the registration chain upward and lists
**every file that must change** for a new member to take effect. Miss one and
nothing errors — the table is simply never created.

**Did the code I generated keep the contract?**

```bash
scripts/index.py                   # re-index, target included
scripts/query.py conform \
    --repo <source> --path '<source family>' \
    --target-repo <target> --target-path '<generated family>'
```

Every DROPPED row is either a departure you can name or a mistake. There is no
third kind.

Add `--kind func` when the family is components, hooks or handlers — the default
reads classes and would report a directory of forty components as having nothing
to check. Two labels are worth knowing: **NOTHING TO CHECK** means the source
has no feature shared by all its members, so the run proved nothing and the
filter needs narrowing; and a one- or two-member side is flagged, because
"always true" of one member is not a contract.

**Running it as a gate.** `--json` prints the result and nothing else, so
`conform` can run again automatically — rung 4 of this skill's own ladder,
applied to what it generated:

```bash
scripts/query.py conform --json \
    --repo atlas --path 'database/*/models/*' \
    --target-repo solution.school --target-path 'database/models/*' \
  | python -c "import json,sys; d=json.load(sys.stdin); \
sys.exit(2 if d['contract_empty'] else len(d['dropped']))"
```

Read `contract_empty` before `dropped`. An empty `dropped` list means *nothing
was broken* or *nothing was checked*, and those are opposite results that look
identical — a gate that ignores the flag reports a green build for a check that
never ran. A filter that matched nothing is reported the same way: still JSON,
with an `error` field and `contract_empty` true, so a mistyped `--path` comes
back inconclusive rather than clean. `questions --json` is the same idea for the
decisions a family forces.

**Is anything calling a method that does not exist?**

```bash
scripts/query.py calls --on <ClassName>
```

Crosses every call made on that name against the members it defines. This found
four live call sites in a real codebase for a method that has never existed.
Read the C# caveat below before trusting it there.

The same command answers two neighbouring questions, and says which it is
answering. A name used as a *receiver* gets the check above. A name **invoked
directly** — a hook, a mixin, a plain function — has no member list to check, so
it reports the call sites instead: `calls --on useState` finds every component
using it, `calls --on media-breakpoint-up` every stylesheet including it. And a
name that is defined but neither called nor invoked is reported as dead, with a
warning worth heeding: a public mixin or an exported helper is called from
outside the index, and absence of a caller there is not absence of a caller.

**I added a C# service. What makes it take effect?**

C# has no barrel file, so `imports --chain` has nothing to follow — and an
unreferenced class compiles perfectly. The failure wears different clothes:
a service that is never registered, a controller never discovered. The
composition root is where that happens, and it is reachable as a *receiver*:

```bash
scripts/query.py calls --on services      # ServiceCollection extension methods
scripts/query.py calls --on builder       # minimal hosting: builder.Services...
scripts/query.py calls --on app           # the pipeline: app.Use..., app.Map...
```

Measured on `eShopOnWeb`, `calls --on services` reports `AddScoped` 21,
`AddDbContext` 4, `AddSingleton` 1, `AddTransient` 1 — and names the files:
`src/BlazorAdmin/ServicesConfiguration.cs` and `src/Infrastructure/Dependencies.cs`.
Those are the two files a new service has to be added to, which is exactly what
`imports <Symbol> --chain` tells you in Python.

This works because a static or field receiver keeps its name at the call site.
It is the same reason `calls --on <TypeName>` does *not* work in C# — see the
caveat below — and the two facts are one fact seen from opposite sides.

**Which pages break if I change this base template?**

```bash
scripts/query.py imports 'admin/base.html' --lang html --chain
```

Template inheritance is a registration chain with no barrel file, so this walks
*down* it — the pages that extend the base, then the pages that extend those.
Every level renders differently if the base changes, and none of them errors.

**Can I trust the dates?**

Every date in the index is the last commit that touched the file, and that is
what makes `AGEING` and the "last touched" column mean *when anyone last cared*.
Two situations quietly replace it with something weaker, and `shape` now says so
under its header rather than leaving you to notice:

- **A codebase not in git**, or one indexed with `--no-git`. Dates fall back to
  file modification times, which a copy, an unzip or a checkout resets wholesale.
  `meta` reports `git_dated: 0`.
- **A history git could not read in time.** `git log --name-only` over a full
  history prints one line per file per commit, and on a repository with tens of
  thousands of commits it can exceed the timeout — after which every file falls
  back to mtime. This used to happen in silence; `meta` now names the
  repository under `dates_unavailable`, `index.py` prints `DATES UNAVAILABLE`
  while building, and `shape` says the code *is* in git and its history was not
  read, rather than blaming git.
- **A shallow clone** (`git clone --depth 1`). The dates are real commit dates,
  but there is only one commit, so every file shares it and no file can ever
  look older than another. `meta` lists the repository under `shallow`, and
  `practice` marks such a row with `*` and says why underneath.

Neither breaks anything — every command still works, and only the dates change
meaning. But `AGEING` cannot fire in either case, and a date on a `VARIES` row
stops being evidence.

For a reference codebase, repair it rather than working around it:

```bash
./.venv/Scripts/python.exe .claude/skills/app-builder/scripts/fetch.py --deepen
```

`--deepen` gives every shallow clone its history back and touches nothing else.
This is not something `--update` used to fix: **pulling a shallow clone leaves
it shallow**, so a corpus cloned with `--depth 1` once stayed dateless through
every update, and nothing said so. Re-index afterwards — the dates only change
in the index when it is rebuilt.

**What should I actually be asked before generating?**

```bash
scripts/query.py questions --path '<family>' --limit 3
```

`shape` reports everything that varies. Most of it does not deserve a question.
`--limit` truncates the output; it is **not** a cap on how much gets asked.
Capping the questions does not remove the decisions — it turns the ones past the
cap into silent guesses, which is why the `questions` setting in `config.json`
is a policy (`many` / `key` / `none`) rather than a number. Ranking uses what the
index already knows: how irreversible the kind of decision is, how genuinely
forked the family is, and whether the majority form is a fossil.

Two things it deliberately does *not* ask about. **Presence of a field or method
in a minority** is the domain, not a decision: a model has `instrument_id`
because that entity references an instrument. And anything the **generated code
already answers**, when you pass `--target-path`:

```bash
scripts/query.py questions --path '<source family>'     --target-path '<generated family>'
```

Nothing is remembered between runs. Answers are not recorded anywhere, so every
generation asks fresh — a saved answer suppresses the question next time, and the
next generation is not the same generation. What the target already shows is read
back from the code instead, which is a fact you can look at rather than a
decision someone filed.

If it reports far more candidates than members, that set is several families at
once and the questions will be the wrong ones. Narrow it first.

**Which conventions are dying?**

Run `shape` over the family and read the `AGEING` section. Anything listed
survives only in files nobody has touched for over a year.

**Is this still how anyone builds it?**

`AGEING` answers that within one codebase. It cannot tell you the codebase is
uniformly behind, because a convention nothing disagrees with produces no
`VARIES` row and no question at all — the most embedded choice is the one nothing
raises. That needs a second opinion, which is what the `reference_corpus` in
`config.json` are: widely-used codebases indexed as **evidence**, never as
templates.

```bash
scripts/query.py practice --on useState --versus useQuery --lang typescript
```

```
  EXEMPLAR
    atlas                  6  100%  2026-06     --                    6
  REFERENCE
    bulletproof-react      5   28%  2024-12     13   72%  2024-12    18

  corpus favours   useQuery
  by codebase      useQuery   (useQuery 1 of 1 codebase(s))
  atlas DISAGREES -- it uses useState
```

Two lines qualify that verdict, and both are printed rather than left to be
remembered. **`by codebase`** counts the same question one repository at a time,
because a single large example farm owns a module count outright; when the two
verdicts disagree the output says `SPLIT` and the corpus has not settled
anything. And a **`*`** beside a repository means its dates are not history —
either a shallow clone or a history git could not read — so weigh the counts and
ignore the dates on that row.

Percentages are head to head: the denominator is modules mentioning *either*
option, not modules in the repository, because the useful comparison is between
the two choices rather than against all the code that never faced the question.
A module using both counts under both.

Three things to keep in mind reading it:

- **`DISAGREES` does not mean wrong.** `--on requests --versus httpx` reports the
  corpus favouring `requests` while atlas is 88% `httpx` — atlas is *ahead*, not
  behind. Django and Flask are mature codebases whose tests still use `requests`.
  Read the dates, not only the counts.
- **The corpus is ten repositories, not a survey.** Enough to show a choice is
  contested; not enough to settle it.
- **It is the only command that reads references unasked** -- `deps` joins it
  only when passed `--references`. Every other command holds them out,
  deliberately: ten reference codebases outnumber one exemplar, and
  letting them into `shape` would replace your contract with an average of the
  internet. Measured — `shape --path '*/models/*'` sees 10 classes; with django
  let in it sees 674, of which 652 are django's.

---

## Command reference

Every command reads the one index, except `config` — it reads `config.json` and
no index, so it is the one thing that works before you have built anything.
Filters marked ● are shared by `find`, `shape`, `exemplars`, `imports` and
`calls`.

| Command | Answers |
|---|---|
| `config` | which codebases and destination are configured, and whether they exist |
| `meta` | what an index covers, when built, which languages, what was skipped, `git_dated` (how many **indexed** files got a real commit date), `shallow` (repositories with no history) and `dates_unavailable` (repositories whose history git could not read, so their dates are mtimes) |
| `families` | what parts exist — directories, class counts, dominant base |
| `find` | the definitions matching a filter, or `--files` for paths alone |
| `shape` | what is ALWAYS true, what VARIES, what is ageing, where repos disagree |
| `exemplars` | the most typical file to copy, and the outlier that shows what is optional. **Exemplars only** — the generated target is held out, since copying your own output makes one mistake a convention; `--include-target` or `--repo` overrides |
| `imports SYMBOL` | who imports it; `--chain` follows re-exports up the registration chain |
| `calls --on NAME` | methods called on a name vs. the ones it defines |
| `conform` | whether generated code still keeps the source's contract. Takes `--kind func` and `--tech`, so a component or hook family can be checked too |
| `proof` | how a codebase proves itself — test config, test dirs, entry points, interpreter |
| `questions` | the decisions this family forces, ranked by what they cost to get wrong |
| `practice --on T --versus T` | how the reference corpus resolves a choice, against how your exemplar resolves it |
| `deps` | what the exemplars and the target declare they depend on and run; `--on NAME` for who declares a package; `--references` widens to the corpus |

Shared filters ●: `--path GLOB`, `--not-path GLOB` (repeatable), `--base`,
`--decorator`, `--symbol REGEX`, `--repo`, `--lang`.

`--base` and `--decorator` match the **name exactly**, ignoring any generic
parameter: `--base Repository` finds `Repository` and `Repository[Student]`, and
a dotted expression matches on its last segment so `--decorator route` finds
`app.route`. What it no longer does is match a substring — `--base Model` used
to pull in `BaseModel` and `ModelForm`, quietly blending three families inside
the one filter meant to separate them. Put a `*` in the string when you do want
a pattern: `--base Base*`.

`--limit` is **not** one of them — it is per command, with a default suited to
that command: `families` 40, `find` 60, `shape` 25, `imports` 40, `calls` 6,
`proof` 20. `exemplars` takes `-n` instead (default 3), and `conform` takes
neither, because a contract is not a list you truncate.

Command-specific: `find --files --functions`, `families --depth`,
`shape --usually N` (default 60), `imports --chain`,
`calls --on NAME --defined-in GLOB`,
`conform --target-repo --target-path --kind --tech --json`,
`exemplars --include-target`, `deps --references`, `meta --verify`,
`questions --json`.

`--json` is on `conform` and `questions` only, and deliberately not on `shape`:
its output is written to be read by a person, no consumer wanted it, and the
change would have touched the most-used command in the skill for a benefit
nobody could name.

`shape`, `questions` and `conform` print a **STALE** line when a source has
changed since its shard was built. That check walks the exemplars and the target
only — a reference changes when you run `fetch.py` and not otherwise — and stops
at the first file newer than the index, so it costs a fraction of a second.

`imports --chain` keeps every hop **inside one repository**. A hop after a
barrel file is a bare directory name — `models`, `utils`, `controllers` — and
matched across the whole index those name a chain running through codebases
that have never heard of each other. A wiring answer is only useful if the
files in it are ones you can edit.

`shape`, `exemplars` and `find` also take `--tech NAME` — react, mui, redux,
vue, sqlalchemy, django, fastapi, aspnet, efcore, xunit and others, derived from
what each module imports rather than stored in the index, so the list improves
without a rebuild.

`shape` and `exemplars` take `--kind class|func`, and which one you want is not
a detail. **A React component is a function, not a class.** So is a hook, a
route handler and most modern JavaScript. `--kind class` (the default) describes
a family of classes and would report that a directory of 40 components contains
nothing at all; `shape` says so when the filter matched more functions than
classes, but it is worth knowing before you see it.

`--defined-in` is for the case that otherwise gives a wrong answer quietly: when
two classes in the index share a name, `calls --on` would cross calls made on
one against the members of both. Narrow it to the file you meant.

**Building an index**

```bash
scripts/index.py                 # every configured repository
scripts/index.py <path> <path>   # explicit roots, ignoring config
    --no-git         skip last-commit dates (recency falls back to mtime)
    --no-solution    sources only, leaving out the generated target
    --no-references  leave out the reference corpus (much faster)
    --only NAME[,..] rebuild only these, leaving every other one alone
    --max-bytes N    skip files larger than this
```

A shard is written to `index.jsonl.pending` and moved into place once the
repository is finished, so an interrupted build never leaves a truncated shard —
it leaves the previous one. `scripts/query.py meta --verify` checks the pair.

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

**Python, TypeScript, JavaScript and C# only** — plus Django/Jinja HTML
templates, CSS/SCSS stylesheets, and `.vue`, `.svelte`, `.razor` and `.cshtml`, which are split into
those languages rather than parsed in their own right. Anything else is skipped,
and reported as skipped.

**Templates are read by regex, not by a parser.** `shape` labels them
`heuristic`, and it means it: "100% of these pages override `content`" is a
weaker claim than the same sentence about Python classes. `{% include %}` whose
target is a variable is recorded as unresolved and never guessed at.

**A Vue 2 component defines nothing this can see.** `export default { methods:
{ … } }` is an object literal, so the Options API yields imports and exports but
no classes or functions — measured at zero across 130 real components. Vue 3's
`<script setup>` declares properly and reads fine. Read a Vue 2 family through
`imports` and `families`, not `shape`.

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
missing, and — since calls are part of a definition's shape — that the generated
family stopped calling something every source class calls. It will not tell you
the schema *inside* `__table_args__` changed. Pair it with `calls --on`, which
covers the other half.

**A file type with no extractor is invisible to `shape`.** It is counted and
reported as `not covered` by `index.py` and in `meta`, and that report is the
only warning you get: `shape` cannot distinguish "this codebase has no
components" from "nothing read them". Check `meta` before believing an absence.

---

## Troubleshooting

**`no index at .claude/skills/app-builder/.indexes`** — build it: `index.py`.

**`.indexes holds reference codebases only`** — references are evidence, never a
template, so no contract can be computed from them. Configure an
`exemplar_corpus` or a `solution` and rebuild.

**Build it somewhere else** — `APP_BUILDER_INDEX=/some/path` moves the whole
index. This is what the old `--name` was for; a path cannot be mistaken for a
repository the way a name could.

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

**`shape` output is a mush of low percentages** — the "family" is really two
families sharing a directory. Narrow with `--base`, `--decorator`, or a deeper
`--path`, and run it on each side.

**`shape` says it is blending repositories** — because it is. Every percentage
is computed across all of them at once, so a row can describe a form neither
codebase uses. `DISAGREEMENTS` catches the clean splits, where one side always
does something and the other never does; it says nothing about a 40/60. Read
each side with `--repo`.

**Counts look doubled** — they should not. One physical file is indexed once,
even when two solutions link to the same library through junctions. `meta` reports
`duplicates_skipped` so you can confirm.

**Counts look too low, or a `practice` denominator moved without a rebuild** —
check the index against itself:

```bash
scripts/query.py meta --verify
```

That compares every shard against the number of files its `meta.json` claims. A
build that was interrupted used to leave the two disagreeing: records are
buffered, so a killed build discarded each repository's unwritten tail, while
every `meta.json` had already been written with the full count. Measured once at
15 of 26 repositories truncated and 720 records gone, four shards empty, and the
**exemplar** 85 files short — with no error, every query answering, and every
answer computed from a codebase that was not the one on disk.

Shards are now written to a temporary file and moved into place when complete,
so the shard and its summary agree by construction and an interruption leaves
the previous shard untouched. `--verify` stays because an index built by an
older `index.py` may still be on disk. If it reports a mismatch, rebuild —
nothing else repairs it, and nothing else will tell you.

---

## Where things live

```
.claude/skills/app-builder/
  SKILL.md                 the procedure Claude follows
  MANUAL.md                this file
  references/
    generating.md          how to read output closely; what to do when it conflicts
    languages.md           per-language mapping, traps, and how to add one
    corpus.md              what is in the reference corpus, and why each one
  scripts/
    index.py               build an index
    fetch.py               clone the reference corpus declared in config.json
    query.py               ask it questions
    smoke.py               check generated Python
    selftest.py            check that the extractors still agree
    extractors/            one per language
    segmenters/            one per container format: .vue, .svelte, .razor
    adapters/              the toolchains they shell out to
  package.json             acorn + typescript, so JS/TS can be read from a fresh
                           checkout without npm install in the indexed repository.
                           typescript is pinned to 5.x: 7 is the native port and
                           does not expose the API the adapter uses
  node_modules/            those parsers — gitignored; restore with npm install
  .indexes/                   indexes — gitignored, rebuildable, never edited by hand
  .reference_corpus/       the reference codebases, cloned by fetch.py —
                           gitignored, disposable, restore with fetch.py
```

Every `meta.json` carries a `schema` number. When it disagrees with the scripts
reading it, queries say so instead of quietly misreading records — one migration
in this codebase is already handled by *sniffing* the shape of a field, which
works once and only while the two shapes are distinguishable.

Delete `.indexes/` any time. It is derived, and `index.py` rebuilds it in seconds.
Its neighbour `.reference_corpus/` is derived too, and that is exactly why they
are siblings rather than nested: one comes back from local disk in minutes, the
other over the network, and "delete the derived directory" must not silently
mean the second one.
