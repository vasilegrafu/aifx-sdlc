# Setup

Everything needed to get the toolchain in this repository working, in order.

This document is about the **skill**, not about any application built with it.
A solution — whatever `solution` in `config.json` points at — is generated code
with its own dependencies and its own way of being run; see
[Working on a solution](#working-on-a-solution) at the end.

Every command below was run on this machine and the output shown is real. Where
something could not be verified, it says so.

---

## 1. Prerequisites

| | Needed for | Verified here |
|---|---|---|
| **Python ≥ 3.11** | everything | 3.14.6 |
| **Node** | reading JavaScript and TypeScript | v24.18.1 |
| **git** | fetching the reference corpus | 2.53.0 |
| **.NET SDK** | reading C# only — skip it otherwise | 9.0.306 |

**Python 3.11 is a hard floor**, not a preference: `manifests.py` uses
`tomllib`, which entered the standard library in 3.11. On 3.10 the skill fails
at import with a `ModuleNotFoundError` that says nothing about the version.

A language whose toolchain is missing is **skipped and reported**, never
silently treated as absent — so an index built without the .NET SDK says so
rather than describing a C# codebase as empty.

---

## 2. Install

```bash
git clone <this repository>
cd aifx-sdlc

python -m venv .venv
.venv\Scripts\activate                 # Windows
source .venv/bin/activate              # macOS / Linux
pip install -r requirements.txt
```

**What `requirements.txt` is for.** Not the skill. Checked, not assumed — the
scripts under `.claude/skills/` import **nothing outside the standard library**:

```
third-party imports: none -- standard library only
```

That is deliberate: it is what lets the skill be copied into another checkout
and still work. `requirements.txt` holds what *solutions built here* have needed
so far — an ORM, a web framework, a test runner — kept in one venv at the root
for simplicity. Swap the solution and that file changes; the skill does not.

### The parsers

```bash
cd .claude/skills/app-builder
npm install
cd ../../..
```

```
  ├── acorn-jsx@5.3.2
  ├── acorn@8.18.0
  └── typescript@5.9.3
```

**Do not skip this if you care about JavaScript or TypeScript.** The parsers
live here, not in the codebases being read, so a repository that has never had
`npm install` run is still readable. Without them the extractors report a
missing parser and skip those languages loudly — but the whole reason they are
here is that the previous arrangement failed *silently*, indexing a 446-file
React project as five files of CSS and HTML.

`typescript` is pinned to 5.x. TypeScript 7 is the native port: no
`lib/typescript.js`, no `createSourceFile`, and an unpinned upgrade would report
every TypeScript codebase as empty.

---

## 3. Point it at codebases

`config.json` at the root. Three roles, and they are not interchangeable:

```json
{
  "app-builder": {
    "exemplar_corpus":  [{ "name": "atlas", "path": "D:/code/solution.atlas" }],
    "reference_corpus": [{ "name": "django", "repo": "https://github.com/django/django.git",
                           "include": ["django"] }],
    "solution": "solution.school",
    "questions": "many"
  }
}
```

| Key | Role | Located by |
|---|---|---|
| `exemplar_corpus` | **what you copy** — its conventions are the contract | `path` — local, yours |
| `reference_corpus` | **what you consult** — evidence, never a template | `repo` URL — fetched |
| `solution` | **what you build** — the later decision, and it wins | `path` |

`include` names the subtrees worth reading. For a reference that is the part
showing the library being *used* — `examples/`, `docs/data/`, `apps/` — not its
own internals. See `.claude/skills/app-builder/references/corpus.md`.

`questions` is a policy, not a count: `many`, `key`, or `none`.

---

## 4. Fetch the reference corpus

```bash
./.venv/Scripts/python.exe .claude/skills/app-builder/scripts/fetch.py
```

```
  have      django                 ae25a40be07e
  cloned    realworld              ec8552fee0d0
  ...
  N reference(s) in D:\...\aifx-sdlc\.reference_corpus
```

Clones into `.reference_corpus/<name>` — gitignored, disposable, and safe to
delete and re-fetch. **Budget disk**: a corpus of this kind runs to a couple of
gigabytes. The first run takes a while on a slow connection, and it is the only
step that touches the network.

`--update` pulls existing clones, `--prune` removes ones no longer configured,
`--dry-run` says what it would do. One unreachable URL is reported and the rest
continue.

Skipping this step is survivable: `practice` reports a smaller corpus rather
than an error. It will also then be quietly wrong about what the wider world
does, which is worse than failing.

---

## 5. Build the index

```bash
./.venv/Scripts/python.exe .claude/skills/app-builder/scripts/index.py --name main
```

**Expect minutes, not seconds** — it took about seven here. Most of that is the
reference corpus, and TypeScript is the slow part. `meta` will tell you what it
covered; do not trust a number typed into a document for that.

After editing your own code, rebuild only that:

```bash
index.py --name main --only <name>          # under a second
```

One file per repository, so a partial rebuild leaves every other shard alone.
`meta.json` carries per-repository totals, so the summary stays honest.

**Never open the index.** It is megabytes of JSONL, and every question you would
ask it has a subcommand that answers in a few hundred lines.

---

## 6. Verify

```bash
Q=".claude/skills/app-builder/scripts/query.py"

./.venv/Scripts/python.exe $Q config
./.venv/Scripts/python.exe $Q meta --name main
./.venv/Scripts/python.exe .claude/skills/app-builder/scripts/selftest.py
```

What a working setup looks like:

What to look for, rather than what the numbers should be:

- `config` — every configured codebase reads `ok`, none `MISSING`, and the
  reference count matches what you configured.
- `meta` — a file, class and function count that is plausibly your codebases,
  and an `unparsed` count that is a stray file or two rather than a language.
- `selftest.py` — `PASSED -- 0 problem(s)`. Any extractor listed as unavailable
  is a toolchain you have not installed, which is fine if you do not need it.

`selftest.py` checks that every extractor emits the same records and that the
commands hold their invariants — including the one that matters most, that a
reference codebase never reaches a contract computation.

Then ask it something real:

```bash
./.venv/Scripts/python.exe $Q layers --name main --depth 3
./.venv/Scripts/python.exe $Q practice --name main --on pathlib --versus os.path --lang python
```

Day-to-day use is [the manual](.claude/skills/app-builder/MANUAL.md), which
assumes this document is done.

---

## Working on a solution

A solution is generated code, and how you run it depends on what was generated.
It has its own tests, its own entry points, and its own dependencies — read its
own files, not this one.

Two things are worth knowing in general:

- **Some solutions link an external library** by junction or symlink, because
  the exemplar they were built from does. That link is part of *that solution's*
  setup, not this repository's, and without it nothing in that solution imports.
- **Generated databases and build output are gitignored.** Where a solution's
  tests create what they need, there is no setup step; where they do not, the
  solution says so.

---

## Troubleshooting

Only failures actually hit here, not imagined ones.

**A JavaScript or TypeScript codebase indexes as almost empty.** `npm install`
was not run in `.claude/skills/app-builder`. The extractors now report this
rather than collapsing every file into one `unparsed` record, but an index built
before that fix will look plausible and be wrong. Rebuild after installing.

**`ModuleNotFoundError: tomllib`.** Python is older than 3.11.

**`config.json is not valid JSON`.** Every command stops on this, deliberately —
a config that half-parses is worse than one that does not. Trailing commas are
the usual cause.

**`no index named 'main'`.** Build one (step 5). The name is a label for the
whole index, not a repository — one index holds every configured codebase.

**`practice` reports a smaller corpus than expected.** References were not
fetched, or a clone failed. `query.py config` lists each as `ok` or `MISSING`.

**A verdict from `practice` changed and nothing else did.** The corpus moved.
Verdicts are evidence, not facts: read how many codebases produced one before
quoting it — two is not a corpus.

**A partial rebuild reported the wrong totals.** Fixed, but if `meta.json` ever
disagrees with the shards, a full `index.py --name main` restores it.
