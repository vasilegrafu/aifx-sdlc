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

## What each one is for

| Reference | include | Evidence for | Also validates |
|---|---|---|---|
| `django` | `django` | Python idiom at scale — `pathlib`, typing, module layout | HTML templates, large-tree indexing |
| `fastapi` | `docs_src` | FastAPI usage, pydantic signatures | typing-heavy Python |
| `flask` | `examples`, `src` | a third Python data point | Jinja templates |
| `fastapi-fullstack` | `backend`, `frontend` | a real FastAPI + SQLModel + Alembic application | the only migrations evidence |
| `sqlalchemy-examples` | `examples` | ORM patterns — inheritance, associations, async | 2.0 `Mapped[...]` beside legacy `Column()` |
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

- **No SQLAlchemy 2.0 application.** `fastapi-fullstack` uses SQLModel, a
  wrapper; session and relationship idiom transfers, `Mapped[...] =
  mapped_column(...)` declaration does not.
- **Alpine is thin** — 10 pages. Most Alpine usage lives inside JavaScript test
  strings, which are not readable as HTML.
- **Alembic is one source.** Its own repository is library internals; migration
  usage lives in user projects, so only `fastapi-fullstack` supplies it.
