# The reference corpus: what is in it, and why each one is there

Declared by URL in `config.json`, fetched into this skill's `.reference_corpus/`
by `scripts/fetch.py`. Gitignored, disposable, and reproducible on any machine.

Each entry earns its place in one or both of two ways, and they are worth
keeping distinct:

- **Evidence.** `practice` reads these to answer *is this still how anyone builds
  it* — a question no single codebase can answer about itself.
- **Validation material.** Real code nobody wrote for a test. Every gap this
  skill has ever had was found this way and would have been missed by a fixture:
  anonymous default exports hiding a third of a package, minified bundles
  reported as a dominant base class, C# instance calls attributed to a variable
  rather than a type, the Vue rule that a top-level block starts at column 0,
  a multi-line `%timeit` orphaning its continuation, `@mui/material/Box` never
  matching `@mui/material`. A fixture agrees with whoever wrote it. These do not.

## The rule that decides what goes in

**Index how a technology is *used*, not how it is implemented.** A library's own
source is written under constraints no application shares, so `include` names
the subtree where the library is being *used* — `examples/`, `docs/data/`,
`apps/` — and everything else is dropped without being enumerated.

Two failures this prevents, both paid for:

- **Framework internals as application evidence.** `django`, `flask` and
  `fastapi` are frameworks; before scoping, their corpus was 2,244 test files
  and zero applications, and "the corpus favours pytest" was really "Django
  tests Django with pytest".
- **Near-duplicate example farms.** `refine` ships 281 tiny demo variants —
  one opinion amplified 281×, which would dominate every React verdict by count.
  It was rejected for that reason. MUI ships every demo as both `.tsx` and
  `.js`, so MUI queries need `--lang typescript`.

`Netflix/dispatch` was measured and rejected for both reasons at once. It is a
real production application, which is what made it tempting — but it declares
with `Column()` in 75 modules and `mapped_column` in none, so adding it to close
the SQLAlchemy 2.0 gap would have argued *against* the idiom the gap is about.
Its 161 alembic hits are migration files: one project's opinion amplified 161×,
which would have owned every alembic verdict outright. A candidate that would
move a verdict is exactly the one to measure before adding, not after.

## What each one is for

| Reference | include | Evidence for | Also validates |
|---|---|---|---|
| `django` | `django` | Python idiom at scale — `pathlib`, typing, module layout | HTML templates, large-tree indexing |
| `fastapi` | `docs_src` | FastAPI usage, pydantic signatures | typing-heavy Python |
| `flask` | `examples`, `src` | a third Python data point | Jinja templates |
| `fastapi-fullstack` | `backend`, `frontend` | a real FastAPI + SQLModel + Alembic application | the only migrations evidence |
| `sqlalchemy-examples` | `examples` | ORM patterns — inheritance, associations, async | 2.0 `Mapped[...]` beside legacy `Column()` |
| `litestar-fullstack` | `src/py` | the only SQLAlchemy **2.0 application** — 92% `mapped_column` | a second alembic source |
| `pydata-handbook` | `notebooks` | pandas, numpy, scipy idiom | `.ipynb` segmentation |
| `pytorch-examples` | — | PyTorch training scripts | — |
| `keras-io` | `examples`, `guides` | Keras and TensorFlow usage | 200 `.py` files, no notebooks needed |
| `dash-apps` | `apps` | Plotly applications; the best pandas evidence here | 286 real apps |
| `bulletproof-react` | `apps` | React + TypeScript application structure | hooks as convention |
| `react-admin` | `examples` | MUI-based CRUD admin — closest shape to a students screen | — |
| `mui-demos` | `docs/data` | MUI component vocabulary | `.tsx`/`.js` duplication |
| `mui-x-demos` | `docs/data/data-grid`, `date-pickers` | the data grid the target is built around | — |
| `redux-toolkit` | `examples` | Redux Toolkit usage | — |
| `zustand` | `examples` | the alternative to Redux | mixed `.ts`/`.js` in one tree |
| `echarts-examples` | `public/examples/ts` | charting in TypeScript | — |
| `htmx` | `www` | htmx attributes — 85 real pages | HTML directive extraction |
| `alpine` | `tests` | Alpine directives (thin: most usage is inside JS strings) | — |
| `vue-element-admin` | `src` | Vue 2 Options API | 131 components declaring nothing at top level |
| `vuestic-admin` | `src` | Vue 3 `<script setup lang="ts">` | container split, TypeScript spans |
| `realworld` | `src` | SvelteKit | script blocks with no `<template>` |
| `eShopOnWeb` | `src` | ASP.NET, EF Core, layered C# | Razor `.cshtml`, Blazor `@code` |
| `bootstrap` | `site`, `scss` | SCSS at scale | stylesheet reading |

## Rules

- **Read-only.** Nothing here is edited. A codebase that looks wrong is a
  finding to report, not a file to fix.
- **Disposable.** Delete any of it and run `fetch.py`. Nothing depends on a
  particular commit — though `meta.json` records which one was measured, so a
  verdict can be traced afterwards.
- **Never promoted.** Moving a reference into `exemplar_corpus` to "get more
  signal" is the failure, not the fix: it would put an average of the internet
  where the exemplar's contract belongs.

## Known gaps

Measured, not remembered. Re-run the query before quoting any of this.

- **The SQLAlchemy 2.0 aggregate is misleading — read the rows, not the
  verdict.** `practice --on mapped_column --versus Column --lang python` reports
  *corpus favours Column* at 30 to 32. That aggregate is not about applications:
  `sqlalchemy-examples` is the library's own teaching material and keeps legacy
  `Column()` examples deliberately, for the people migrating. The only
  application in the corpus, `litestar-fullstack`, is 92% `mapped_column`.

  This was worse before that application was added — 18 to 31 from a single
  source — and the fix was to add evidence, not to re-scope `sqlalchemy-examples`
  until the number came out right. One more 2.0 application would flip the
  aggregate, and that is a reason to keep looking, not a reason to go shopping:
  a corpus curated until it agrees with you is not evidence about anything.

- **Alembic is thin: two sources, 6 modules and 2.** Its own repository is
  library internals, and migration usage lives in user projects. Two is not a
  corpus — the guidance about quoting a verdict without reading how many
  codebases produced it applies to every alembic answer here.

- **Alpine cannot be closed by adding repositories, and that is the finding.**
  `x-data` appears in **11 `.html` files across the entire corpus** and in
  **126 `.md` files**. The evidence exists; it is written in Markdown prose and
  inside JavaScript test strings, and this skill reads neither as markup —
  `.md` is in `NOT_A_LANGUAGE` on purpose. Another Alpine project would land in
  the same place, because that is how Alpine is documented and demonstrated.
  Closing it means reading fenced HTML blocks out of Markdown, which is a
  change to the extractors, not to this file. Until then, treat every Alpine
  verdict as unusable rather than thin: `x-data 2, x-on 0`, dated 2022, is not
  a small sample of the truth but a measurement of the wrong thing.
