---
name: app-builder
description: Generate a working part of an application by reading how one or more existing codebases already do it. Use when asked to build, generate, scaffold or add a layer — a database layer, models, repositories, controllers, services, API routes, handlers, React, Vue, Svelte or TypeScript components, Django or Jinja templates, jobs, clients — "the way the other project does it", "like in atlas", "matching our existing code", or "combining the best from these repos". Also use when asked what a large codebase's structure is, what its conventions are, how a layer is wired, which conventions are dying, or where two codebases disagree. Reads Python, TypeScript, JavaScript, C# and HTML templates — including .vue, .svelte, .razor and .cshtml — at any size through a structural index rather than by opening files, so it also answers questions about ASP.NET, React, Vue, Django or SQLAlchemy code without reading it.
---

# Generating a layer from codebases you were pointed at

You are given one or more codebases and a description in prose. You produce
working code in a target project, shaped the way those codebases shape it.

The whole method rests on one distinction:

> What is **always** true of a set of files is a **contract** — reproduce it.
> What **varies** is an **axis of choice** — decide it deliberately.
> What one codebase always does and another never does is a **disagreement** —
> ask. Do not average.
> What is always true and no longer how anyone builds this is a **fossil** —
> say so, and let the user choose.

That fourth line is newer than the other three and pulls against them, so be
clear about what it does and does not license.

`ALWAYS` is the **strongest available evidence of intent** — someone chose it,
every file agrees, and departing from it breaks callers you have not read. It is
the default, and it stays the default. What it is *not* is proof of
correctness. A convention is unanimous in a codebase for two very different
reasons: it is right, or it was decided once and nothing has revisited it since.
The index cannot tell those apart, and neither can a percentage.

This matters because of an asymmetry that is easy to miss: **the strongest
convention in a codebase is the one nothing will ever question.** `questions`
ranks forks, and a fork needs disagreement; something the exemplar is unanimous
about produces no fork, no row, and no question. So the choices most deeply
embedded in a codebase are exactly the ones that get reproduced without anyone
noticing there was a choice.

Three rules keep that from becoming licence to rewrite whatever you dislike:

1. **Evidence, not taste.** A proposal cites `practice` — what the reference
   corpus does and when — or a named failure the current form causes. "More
   modern" is not a reason. `references/alternatives.md` is the checklist.
2. **The caller check is absolute.** Before keeping anything more ergonomic than
   the exemplar, find a real call site. This rule was paid for: defaulting
   `session` to `None` read better and broke every caller, with the error landing
   a frame from anything that explained it. No amount of corpus evidence
   overrides it.
3. **Propose, never adopt.** The user chooses. A departure they did not choose
   is a defect, however well evidenced.

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
    "solution": "solution.university",
    "questions": "many",
    "references": [{ "name": "django", "repo": "https://github.com/django/django.git" }]
  }
}
```

**Three roles, and they are not interchangeable:**

| Role | Key | What it is for |
|---|---|---|
| exemplar | `repositories` | what you copy — its conventions are the contract |
| target | `solution` | what you build — the later decision, and it wins |
| reference | `references` | what you consult — what the wider world does, and when |

`questions` is a **policy**, not a count: `many` asks at every genuine decision
point as the work reaches it, `key` asks only what is expensive to reverse,
`none` decides everything and reports it. See step 6 — and note that a count was
tried and removed, because capping the questions does not remove the decisions,
it only turns the ones past the cap into silent guesses.

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
nothing to disagree with. Combining the best of several codebases needs several
entries here, and if the user asks for that with one configured, say so rather
than implying a comparison happened.

## References are evidence, never a template

A reference codebase answers a question the exemplar cannot: **is this
convention still how anyone does it?** One codebase cannot tell you that. It is
the difference between a live convention and a fossil that happens to hold a
majority, and no amount of querying the exemplar reveals it.

They are held out of `layers`, `shape`, `exemplars`, `questions`, `conform` and
`DISAGREEMENTS` — by `read_index`, so it is not something a command has to
remember. Only `practice` opts in.

That default is not tidiness. Nine reference codebases outnumber one exemplar,
so a reference reaching a contract computation replaces the convention being
reproduced with an average of the internet — the same failure as averaging two
exemplars, at nine times the scale. Measured, not assumed: `shape --path
'*/models/*'` matches 10 classes across atlas and the target, and **674** with
django let in. 652 of those are django's. Every ALWAYS row would have described
a codebase nobody asked to copy.

So: never move a repository from `references` to `repositories` to "get more
signal". That is the failure, not the fix.

**A reference is declared by URL and fetched, not by path.** `repo` names the
upstream; the directory is always `.reference_corpus/<name>`, so the config name
*is* the directory name and there is nothing to keep in sync. Setting the
solution up elsewhere is one command:

```bash
./.venv/Scripts/python.exe .claude/skills/app-builder/scripts/fetch.py
```

`fetch.py` is deliberately not part of `index.py`: indexing is local, offline and
repeatable, and a build that quietly reaches for the network fails differently
depending on where it runs. `.reference_corpus/` is gitignored and disposable
like `.data/` -- and must stay so for a second reason, that each clone carries
its own `.git` and `git add .` over such a directory writes a phantom submodule.

`repositories` and `solution` keep using `path`: they are local by nature.

**Index how a library is *used*, not how it is written.** A library's own
repository is mostly its internals, and its internals are written under
constraints no application shares. What you want from `react-admin` is
`examples/`; from a machine-learning library, its example gallery. Say so with
`include`, which names the subtrees to read and drops everything else without
enumerating it:

```json
{ "name": "react-admin", "path": "...", "include": ["examples"] }
```

`exclude` is the blacklist and it fails the way blacklists do -- the same
repository listed five directories to drop and still pulled in a documentation
site. `include` was ten files tighter *and* shorter. Both may be given: `include`
chooses the subtrees, `exclude` removes parts of them.

One deliberate exception: the repository's **own top-level manifest** is kept
whatever `include` says, because what a project declares overall is a fact about
the project rather than about a subtree.

The same trap applies to whole codebases, not just directories. `django`,
`flask` and `fastapi` are indexed here and every one of them is a *framework* --
their contents are `tests/` and framework internals, with no application
anywhere. They are good evidence for language-level questions (`pathlib` vs
`os.path`) and poor evidence for "how should an application be structured",
which is most of what gets asked. Prefer a codebase that *uses* the thing.

**Reading a codebase must not require having built it.** The skill carries its
own `acorn` and `typescript` (its `package.json`; `node_modules` is gitignored),
because locating a parser inside the *indexed* repository meant only repositories
that had run `npm install` could be read — and it failed silently, collapsing
every file into one `unparsed` record. A corpus of nine JavaScript projects
reported almost no JavaScript. TypeScript is pinned to 5.x deliberately:
TypeScript 7 is the native port, has no `lib/typescript.js`, and does not expose
the `createSourceFile` API the adapter is written against.

Step 6 still has work to do, though: most decisions are not disagreements
between codebases but forks *inside* one, and `questions` finds those in a
single repository.

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

**Then ask what no codebase can tell you.** Everything above is a fact you can
look up. The following are not in any index, are not in the config, and change
the right answer to many decisions further down:

| | Why it changes downstream answers |
|---|---|
| **Scale** | rows, users, requests. Decides indexing strategy, pagination shape, sync vs async, whether a random primary key matters at all. |
| **Who maintains it** | the author alone, a team, someone who has not arrived yet. Decides how much indirection is worth its cost. |
| **Simplicity or flexibility** | the single most useful answer. Almost every "should this be pluggable" question is already settled by it. |
| **One application, or a reusable framework** | decides whether public surface, extension points and backward compatibility are requirements or overhead. |
| **Backward compatibility** | whether existing callers and stored data constrain the shape, or nothing has shipped yet. |
| **Speed now, or longevity** | a prototype and a system with a five-year life want opposite trade-offs, and both are legitimate. |

Ask them **once, at the start, in one message** — never one at a time, and never
again later unless the request contradicts an answer. Nothing is recorded, for
the same reason nothing else is: a stored answer suppresses the question next
time, and the next generation is not the same generation.

Three restraints keep this from becoming a form to fill in:

- **Do not ask what you can see.** A target with seven models and one maintainer
  in the git history has already answered "scale" and "who maintains it".
  Infer it, state the inference in one line, and let it be corrected.
- **Do not ask what does not matter here.** Adding a controller to an existing
  layer needs none of this. Raise only what a decision in *this* request turns
  on.
- **Under `questions: none`, ask nothing.** Infer, state the assumptions
  explicitly in the report, and let step 10's numbered list carry them.

The failure this prevents is specific and expensive: a structural choice made
early on an assumption nobody checked, discovered only when the assumption turns
out to be wrong and the structure is load-bearing.

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
  code that omits any of it is wrong, whatever it looks like. It is also the
  section nothing else will question, so it is the one place where reading
  carefully is the only safeguard: ask of each row whether it is load-bearing
  for what was requested, and whether it is still how this gets built. Most
  rows are both, and reproducing them is the whole job. The occasional row that
  is neither is what `practice` and `references/alternatives.md` exist to catch.
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

### 6. Decisions arrive throughout — ask when the work reaches them

A generation is a conversation, not a form filled in at the start. Some
decisions cannot be raised until the work reaches them: you cannot ask about
delete behaviour before the entities exist, or about a barrel file before you
know how many modules there are. **Ask at each point as it arrives.**

```bash
scripts/query.py questions --name <index-name> --path '<source layer>'     --target-path '<generated layer>'
```

`questions` ranks what this layer forces by **what it costs to get wrong** — how
irreversible the kind of choice is, how genuinely forked the layer is, and
whether the majority form is a fossil. It excludes anything already recorded,
and anything that is really the domain rather than a decision.

**Pass `--target-path` once the target holds the layer.** That is what makes
"the target outranks the source" true of questions and not merely of `shape`:
anything the generated code is unanimous about is read back and reported, never
asked. Without it the command has no way to know the target's layout -- atlas
keeps models under `database/<domain>/models/`, a flattened app does not, and no
single glob matches both.

**The points where a decision actually arrives**, in order:

1. **The spec** — the entities and relations. From the request, never from the
   codebase. Restate it before generating; a wrong noun caught here costs a
   sentence and caught later costs the pass.
2. **Structure** — flat or grouped, where the layer lives, what the packages are
   called. Cheap to ask, expensive to change once imports exist.
3. **Conventions** — whatever `questions` ranks for that layer.
4. **The platform seam** — what the source assumes and the target does not. The
   *target* settles these, and the source cannot help.
5. **Wiring** — when step 5 reveals a chain with more than one reasonable shape.
6. **After generating** — the numbered list in step 10.

**And the decisions the source made badly, or long ago.** `questions` ranks
forks *inside* the exemplar. It cannot rank a choice the exemplar is unanimous
about, because unanimity is what it reports as the contract — so the strongest
convention in a codebase is the one nothing will ever question.

That is what `practice` is for:

```bash
scripts/query.py practice --name <index> --on <token> --versus <token> [--lang python]
```

It reads the reference corpus, which nothing else does, and answers head to head
— of the modules mentioning either option, what share uses each, and when each
was last touched. Then it says which way the corpus leans and whether the
exemplar disagrees.

```
  EXEMPLAR
    atlas                  6  100%  2026-06     --                    6
  REFERENCE
    bulletproof-react      5   28%  2026-05     13   72%  2026-05    18

  corpus favours   useQuery
  atlas DISAGREES -- it uses useState
```

Read that as a **question**, never a verdict. A corpus can be unanimous and
still wrong for this target, and `DISAGREES` is the start of a conversation with
the user, not a defect to go and fix. What it removes is the alternative:
proposing a change on the strength of your own opinion about what is modern.

Use it when a choice is load-bearing and the exemplar is unanimous — precisely
where `questions` goes quiet. Do not run it on matters of taste; a token with no
consequence produces a table with no meaning.

**And the decisions the source never made.** `questions` reports what is *in*
the index, so it can raise a fork the source contains and never an absence:
something the source does not do at all leaves no record to rank. Those are the
expensive ones -- no relationships, no delete policy, no timestamps -- and
`references/decisions.md` lists them per layer kind. Check it against the layer
being generated, raise what is both absent and load-bearing, and mark each one
as a departure from the source so the user is choosing rather than being
steered.

**`questions` in `config.json` is a policy, not a count:**

- **`many`** — ask at every genuine decision point, however many that is.
- **`key`** — ask only what is expensive to reverse; decide the rest and say so.
- **`none`** — decide everything and report it. Never interrupt.

A count was the wrong axis, and it is worth understanding why: capping at three
does not make the fourth decision go away, it makes it a **silent guess**. What
limits questions properly is the rule below, not arithmetic.

**Never ask what the codebase, the config or the request already answers.** That
is the whole restraint. Before asking anything about the target, read the target
— it is indexed, it outranks the source, and if the answer is visible in code
already generated then there is no question. Asking there is a bug, not
diligence.

**Every question offers real options and the user's own wording.** Three or four
substantive alternatives, each with what it actually means — the counts from the
codebase, the consequence of choosing it — and always the option to write
something else. A question with one plausible answer is not a question.

**What every option owes.** Not prose about a choice — these five, or the option
is not ready to be offered:

| | |
|---|---|
| **What it is** | concretely, in the target's own terms |
| **Advantage** | what it buys, specifically |
| **Disadvantage** | what it costs. An option with none listed has not been thought about |
| **When it is right** | the circumstance that makes this the answer — this is what makes options comparable rather than merely different |
| **Departure or fidelity** | whether it matches the source, and if not, that `conform` will report it as ADDED or DROPPED |

Then **recommend one, and say why.** A list of options with no recommendation
pushes the work back onto the person who asked you to do it. Put the
recommendation first and mark it, and be willing to be overruled — being
overruled is the mechanism working, not failing.

Two failure modes to avoid, both common:

- **The fake option.** Three choices where two are obviously wrong. It reads as
  diligence and is really a decision already made, presented as a question.
- **The unbounded option.** "Use a query library" without saying which, or what
  it adds to the dependency list. An option that cannot be costed cannot be
  chosen.

**Say the blast radius when it is large.** Some choices are cheap now and
enormous later — changing POST-for-reads to GET rewrites every client. The cost
of *reversing* a choice belongs in the question, not in the post-mortem.

**Price every option.** An option that adds a dependency says which, and
whether anything already declares it:

```bash
scripts/query.py deps --name <index> --on '@tanstack/react-query'
```

A package the exemplar already carries costs nothing to adopt; one nothing
declares is a new commitment, and "use a query library" without that is the
unbounded option above. Generated code importing something no manifest declares
installs nothing and fails at run time with a resolution error that reads as a
path problem.

**Show the code, not a description of it.** When the options differ in shape
rather than in degree, attach a **preview** to each: the two or three lines it
would actually generate. A choice between `Mapped[UUID] = mapped_column(Uuid,
primary_key=True, default=uuid4)` and `Mapped[str] = mapped_column(String(256),
primary_key=True)` is decided in a second when both are on screen, and argued
about for a paragraph when they are described in prose. This is the same reason
step 10 exists: people judge an artefact faster and better than a proposition.

Nothing is recorded. There is no ledger of past answers, and that is deliberate:
a saved answer suppresses the question next time, and the next generation is not
the same generation. Ask, use the answer, and state it in the report at step 10 --
where it stays visible in the code rather than in a file about the code.

What *is* still read is the generated code itself. `--target-path` reports
anything the target already answers instead of asking, because that is a fact
you can look at rather than a decision someone saved.

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

### 9. Read your own output before anyone else does

Step 8 proves the code **works**. Nothing so far asks whether it should have been
built this way — and the moment to ask is now, while it is fresh, cheap to change
and not yet defended in a report.

Read what you generated as though someone else wrote it and you are reviewing it.
Six questions, and they are deliberately not about correctness:

1. **Is this the simplest thing that satisfies the request?** Not the simplest
   imaginable — the simplest that meets what was asked and keeps the contract.
2. **What is here that nothing needs?** An abstraction with one implementation,
   a parameter every caller passes the same value for, a layer that only
   forwards. Generation tends to produce these because the exemplar had a reason
   for them that the target does not.
3. **Would I build it this way starting today**, knowing the brief from step 1
   and not merely the exemplar?
4. **What will the next person misread?** The line that looks wrong and is not
   usually needs the comment, not the line that looks clever.
5. **What did I decide by default rather than on purpose?** Anything you cannot
   give a reason for is a candidate for step 10's list, not a settled matter.
6. **Where did I claim more than I checked?** Cross-check the wording you are
   about to use against the rungs you actually climbed.

Step 8 already ran `conform` and `calls`; do not run them again. Read their
output a second time with a different question in mind. In step 8 they answered
*did anything break*. Here they answer *what does the shape of this output say*
— a `DROPPED` row you can name is a departure, a `DROPPED` row you cannot is
something you did without deciding to, and only the second reading tells them
apart.

**Every finding goes to the user, including the ones you are not going to act
on.** A regret you fix silently and a regret you keep silently look identical
from outside, and both deny the person a decision that is theirs. Number them
into step 10's list.

Three rules keep this from becoming a second generation pass:

- **Do not rewrite what merely offends taste.** The caller check and the
  evidence gate apply here exactly as in step 6 — reviewing your own output is
  not a licence the source never got.
- **A finding with no proposed action is still a finding.** "This will not scale
  past a few thousand rows, and that is fine for now" is worth one line.
- **Say when you found nothing.** A review that always produces findings is
  performing diligence; one that never does is not happening. Either way, say
  which.

The failure this prevents is the specific one where generated code is *correct*,
*proven*, *reported* — and structurally wrong in a way that was obvious for
about ninety seconds after it was written, and expensive from then on.

### 10. Report — and end with the choices, numbered

Every generation ends with the choices you made, numbered, whichever `questions`
policy was in force. This is the half of the decision process that does not
interrupt: a person reacts to a concrete artefact far more easily than to an
abstract question, and by the time they see the list the code already exists to
look at.

```
CHOICES -- say a number to change one, and I will re-run that part
  1. primary key      Uuid surrogate            2 of 3 sources; the third uses
                                                a natural String key
  2. timestamps       created_at only           87% have it; updated_at is 12%
  3. delete behaviour ondelete='CASCADE'        the layer varies; the request
                                                said "belongs to"
  4. table naming     snake_case plural         ALWAYS in the source
  5. relationships    many-to-one only     DEPARTURE  atlas declares none;
                                                conform reports this as ADDED
  6. read verb        POST, as the source  CONSIDERED  practice: corpus favours
                                                GET. Kept -- changing it
                                                rewrites every client
```

Rows 5 and 6 are the ones that used not to appear. A departure the user chose is
invisible in a diff unless it is named, and a fossil you *decided to keep* is a
choice as much as one you changed — reporting only what you altered hides the
half of the reasoning that preserved something deliberately.

Rules for that list, and they are what make it useful rather than decorative:

- **Every choice that was not forced.** If `shape` said ALWAYS, it was contract
  and it is not a choice — say that once, and do not pad the list with it. The
  exception is an ALWAYS row you *considered* departing from and did not: that
  was a choice, and it belongs in the list with the evidence that settled it.
- **Say what it was weighed against**, with the counts. A choice with no
  alternative shown cannot be judged.
- **Anything the user changes is a decision**, not a correction. Re-run only the
  part it affects, and carry the new answer through the rest of the session.
  Nothing is written to disk — see step 6.

**For each significant choice, five things.** The numbered list is the index;
this is what a person needs to disagree with it usefully:

- **Chosen**, and on what evidence — counts from `shape`, a row from `practice`,
  the user's own answer.
- **Rejected**, and why. The alternative that was real and lost. Silence here
  reads as "no alternative existed", which is almost never true.
- **The trade-off accepted.** Every choice costs something. If you cannot name
  what this one costs, you have not finished choosing it.
- **The assumption it rests on** — especially any inferred rather than asked at
  step 1. An unstated assumption is the thing nobody can correct.
- **The future limitation.** What this makes harder later, and roughly when it
  would start to hurt.

Keep it to a line each. The point is that a reader can find the load-bearing
assumption without reading the code, not that every choice gets an essay.

Then state, briefly:

- which exemplar the structure came from, by path
- what you reproduced because it was contract
- every VARIES you chose, and on what grounds — including every place the
  target's platform forced a departure from the source's
- **every departure from the source, marked as such**, with what `conform`
  reports for it. A departure the user chose is not a defect, but it is
  invisible in the diff unless it is named here
- which rungs of step 8 you climbed, and what each one actually proved
- anything you could not verify
- **what step 9's review found**, including anything you decided not to act on
  and why — and say plainly if it found nothing. A review whose findings never
  reach the report has not happened; the user cannot overrule a regret they were
  never told about
- **what the index could not see**, where it bears on what was asked. Deployment,
  CI, dependency manifests and observability are not indexed at all
  (`references/decisions.md`), so silence about them is not evidence they are
  fine

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
  which language produced it and at what fidelity. **Django and Jinja HTML
  templates and CSS/SCSS stylesheets** are read too, at `heuristic` fidelity,
  by mapping onto the same records: `{% extends %}` and `@extend` are base
  classes, `{% block %}` and `@mixin` are methods, `{% include %}` and
  `@include` are calls. Every command works on them unchanged, and both carry
  a registration chain that fails silently — a block nobody fills, a partial
  nobody imports. **`.vue`, `.svelte`,
  `.razor` and `.cshtml`** are read as well, but they are not languages: a
  segmenter splits each file into the languages it holds and the ordinary
  extractors read the spans. Their markup and styles are reported as not
  covered. Python needs nothing;
  TypeScript and JavaScript need `node` only -- the skill carries its own
  `typescript` and `acorn` and prefers the indexed project's when it has one, so
  a repository that has never had `npm install` run is still readable; C# needs
  the .NET SDK, which is present by definition in a C# codebase. Nothing else is covered and must
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
- `references/decisions.md` holds the decisions each kind of layer normally
  faces, including the ones the source never made -- an absence produces no
  index record, so nothing else can surface it.
- `references/corpus.md` says what each reference codebase is for, the rule that
  decides what goes in -- index how a technology is *used*, not how it is
  implemented -- and the corpus's known gaps.
- `references/alternatives.md` is its mirror: what the source decided once,
  everywhere, and never revisited. Unanimity is reported as contract and
  produces no question, so the most embedded choice in a codebase is the one
  nothing raises. Read it with `practice`, and mind the gate -- corpus evidence
  or a named failure, or say nothing.
- `references/generating.md` holds the detail: turning prose into a spec,
  reading `shape` output closely, what to do when exemplars conflict inside one
  codebase, why not to improve a signature that looks clumsy, why code that
  works from one directory may work from nowhere else, and what you may honestly
  claim to have proved.
