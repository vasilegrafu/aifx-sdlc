---
name: pyapp
description: Generate a working part of a Python application by reading how one or more existing codebases already do it. Use when asked to build, generate, scaffold or add a layer — a database layer, models, repositories, controllers, services, API routes, handlers, jobs, clients — "the way the other project does it", "like in atlas", "matching our existing code", or "combining the best from these repos". Also use when asked what a large codebase's structure is, what its conventions are, how a layer is wired, or where two codebases disagree. Reads codebases of any size through a structural index rather than by opening files.
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
./.venv/Scripts/python.exe .claude/skills/pyapp/scripts/index.py --name <index-name>
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
  "pyapp": {
    "repositories": [{ "name": "atlas", "path": "D:/code/solution.atlas" }],
    "solution": "solution"
  }
}
```

`name` is what the index calls that codebase and what `DISAGREEMENTS` reports
against, so it is worth choosing well. `solution` is where generated
applications are built, relative to this repository unless absolute.

**With one repository configured, `DISAGREEMENTS` never fires** — there is
nothing to disagree with, and step 6 has nothing to settle. Combining the best
of several codebases needs several entries here. If the user asks for that with
one configured, say so rather than implying a comparison happened.

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

`--usually` moves the threshold between *usual* and *varies*; the default is 60.

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
not against the exemplar — `find --path '<library>/*'` lists what actually
exists. Where exemplars disagree, the one matching the library wins, however
typical the other is. This is not hypothetical: it is how `.where()` — a method
the library does not have — reached nine generated controllers at once.

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

Read `.claude/skills/pyapp/.data/<index-name>/decisions.md` first. If it already
answers a disagreement, apply the recorded answer silently.

For anything not recorded, ask the user — one question per genuine
disagreement, with what each codebase actually does and the counts. Then append
the answer to that file:

```markdown
| id | decision | answer | asked |
|----|----------|--------|-------|
| primary-key-type | atlas uses Uuid surrogate keys; other uses natural String keys | Uuid | 2026-08-05 |
```

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

```bash
./.venv/Scripts/python.exe .claude/skills/pyapp/scripts/smoke.py \
    [--app <subdirectory>] --python <interpreter> <generated files>
```

Paths are relative to the application root. Omit `--app` when the solution
directory is itself that root.

`IMPORTS` catches the loud failures. `REACHABLE` catches the quiet one — a class
nothing imports, which is the failure step 5 exists to prevent.

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

Then run whatever the source codebase itself uses as proof. Do not ask which
that is; the repository already says:

```bash
scripts/query.py proof --name <index-name>
```

It reports the test configuration, the test directories, the interpreter in the
tree, and every module guarded by `__main__` — which is where a schema
generator or migration entry point shows up. Run the one that would exercise
what you generated. If there is none, say so plainly rather than calling the
work verified.

### 9. Report

State, briefly:

- which exemplar the structure came from, by path
- what you reproduced because it was contract
- every VARIES you chose, and on what grounds
- what `smoke.py` and the project's own check actually proved
- anything you could not verify

## When the layer does not exist yet

If nothing in the index resembles what was asked for, say that. Generating a
layer with no exemplar is ordinary work, not this skill's method — the skill's
value is fidelity to existing code, and there is none to be faithful to. Offer
the nearest layer as a source of conventions instead.

## Boundaries

- Python only. The index is built from Python's own parser; other languages are
  not covered and must not be guessed at.
- The index holds facts derived from other people's repositories. It lives in
  `.data/` beside this file — inside a tracked skill, so it must stay ignored,
  and nothing from it belongs in a tracked file.
- `references/generating.md` holds the detail: turning prose into a spec,
  reading `shape` output closely, and what to do when the exemplars conflict
  with each other inside one codebase.
