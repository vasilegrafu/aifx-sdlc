# Languages: what maps to what, and what does not

The index schema is the seam. Everything downstream — `families`, `find`, `shape`,
`exemplars`, `imports`, `calls`, `conform` — reads records and never asks what
produced them. A language is added by producing records, not by changing queries.

**Python, TypeScript, JavaScript and C# are implemented at AST fidelity**, one
extractor each, plus **HTML templates and stylesheets at heuristic fidelity**
and the container formats below. Every one was validated against a codebase nobody wrote for
the test, and the sections below record what that found — which was, every time,
something a fixture would have agreed with me about.

`selftest.py` holds them to one contract: same fixture shapes, same record keys,
same call recording. Where two extractors are deliberate near-copies, that is
what keeps the copy honest rather than merely intended.

## The extractor contract

```python
LANGUAGE   = "typescript"          # stamped on every record as `lang`
FIDELITY   = "ast"                 # "ast" or "heuristic"
EXTENSIONS = (".ts", ".tsx", ".mts", ".cts")

def available(root) -> str | None: ...          # None, or the reason it cannot run
def extract(files, root, repo, commits) -> Iterable[dict]: ...
```

Three things in that signature are not incidental, and two were learned the hard
way by writing the second one.

**`extract` takes a list of files, not one file.** Python parses in-process, so
per-file costs nothing. Everything else shells out, and one process per file
turns a three-second index into minutes.

**Availability is a reason, not a boolean.** No `node` means the `.ts` files are
skipped — and the index must *say so*, on stderr and in `meta.json`. A silently
incomplete index is the worst possible output from a tool whose whole job is to
report what is ALWAYS true: absent evidence reads as absent convention.

**`available()` checks the toolchain, not the library.** Where the *compiler*
lives is decided per file, not per repository. The first version of the
TypeScript extractor looked for `node_modules/typescript` at or above the
repository root and skipped all 167 files in a real codebase — because a Python
solution's frontend installs it *below* the root, in `webapp/`. Group files by
their nearest compiler; a monorepo has several.

**`FIDELITY` is not decoration.** A heuristic extractor claiming "100% of classes
do this" is a weaker statement than an AST one making the same claim, and `shape`
can only be read correctly if the reader knows which they are looking at.

**A call is `[name, line]`, and the line is the call's own.** Not the enclosing
function's — the difference between being pointed at a call site and being
pointed at a forty-line method and invited to go looking. `selftest.py` asserts
the pair shape on every extractor, because a bare string from any one of them
would make `calls` report a plausible wrong line rather than fail. Readers use
`call_sites()` in `query.py`, which still accepts the older string-only form so
an index built before the change keeps answering everything except *where*.

**Class, function and method records carry `end` as well as `line`**, so the
size of a definition is a question the index can answer — which is what stops
`exemplars` recommending an empty class merely because it is typical.

Both fields together cost about **9%** of index size, measured. That is the
budget they have to earn, and the reason the answer to "should the index store
more" is usually no: every query scans the whole file, so a field nobody reads
is paid for by every query forever. There is a live example of that mistake —
`doc` is written by the Python extractor and read by nothing.

## The mapping

|  | Python | TypeScript | JavaScript | C# |
|---|---|---|---|---|
| parser | stdlib `ast`, in-process | TS compiler API, via node | acorn, via node | Roslyn, via dotnet |
| `class` record | class | class, interface, type alias | class | class, struct, interface, record |
| `bases` | base classes | `extends`, `implements` | `extends` | base type + interfaces |
| `decorators` | decorators | decorators | — | attributes |
| `attrs` | annotated assignments | interface fields, class properties | class fields, typed by JSDoc | fields and properties |
| `methods` | def / async def | methods, arrow properties | methods | methods |
| `imports` | import, from-import | import, `import type` | import **and `require`** | using |
| `exports` | `__all__` or public names | export, export default | export **and `module.exports`** | none — namespaces |
| `calls` | `obj.method(...)` | `obj.method(...)` | `obj.method(...)` | `obj.Method(...)` |
| `invokes` | `f(...)` | `f(...)` — **hooks live here** | `f(...)` — hooks too | `F(...)` |
| call line from | `node.lineno` | `getLineAndCharacterOfPosition` | acorn `locations` | `GetLineSpan` |
| barrel file | `__init__.py` | `index.ts` | `index.js` | none |
| rung 1 | `smoke.py` | `tsc --noEmit` | `node --check` | `dotnet build` |
| rung 2 | `python -m <entry>` | `npm run build` | `npm run build` | `dotnet run` |
| rung 4 | pytest | vitest, jest | vitest, jest | `dotnet test` |

Rung 3 is absent from that table on purpose: it is a throwaway script exercising
the guarantee that fails silently, and no toolchain provides it in any language.

Markup and styles map onto the same records, at `heuristic` fidelity — no new
record kind, no new query, and every existing command works on them unchanged:

|  | HTML templates | Stylesheets |
|---|---|---|
| parser | regex | regex + a brace scanner |
| `class` record | the template | the stylesheet |
| `bases` | `{% extends %}` | `@extend` |
| `attrs` | — | `$vars` and `--tokens`, **with their values** |
| `methods` | `{% block %}` | `@mixin`, `@function` |
| `imports` | extends, include, load, `<script src>` | `@import`, `@use`, `@forward` |
| `exports` | the blocks it offers | its mixins and variables |
| `invokes` | `{% include %}` | `@include` |
| barrel file | none — inheritance is the chain | none — `@import` is the chain |
| what fails silently | a block nobody fills | a partial nobody imports |

## What breaks, per language

### TypeScript — implemented, and what it turned out to need

**The convention lives in `invokes`, not in declarations.** Confirmed on real
code: across the components, `useState`, `useEffect`, `useRef`, `useSelector`,
`useMemo`, `useCallback`, `useDispatch` — and `useConfig`, a *custom* hook, which
is the local convention an index recording only `receiver.method` would never
have seen. This is the whole reason `calls` and `invokes` are separate fields.

**Most components are not declarations.** `const X = (props) => {...}` is a
variable statement, not a `FunctionDeclaration`. An extractor that walks only
declarations finds almost no React components at all.

**Interfaces and object type aliases are `class` records.** A props interface is
the component's contract, and treating it as a class is what lets `shape` report
`sx: SxProps<Theme>` at 100% alongside a base of `Omit<BoxProps, 'sx'>`. Type
aliases that are not object types carry no members and are skipped.

**Build output parses perfectly.** `SKIP_DIRS` matched `dist` and missed
`dist.dev` — minified bundles were indexed as source and reported `Error` as a
dominant base class. Directories are skipped by prefix as well as by name.

**JSX is the markup.** There is no separate HTML family worth indexing in a React
codebase; four `.html` files at the root are the shell. Likewise styling under
MUI or emotion is TypeScript objects, not CSS. One extractor covers what looks
like three languages.

**A generated API client is not an exemplar.** `openapi-generator` output has the
shape of the generator, not of the codebase. Exclude it, or `shape` will report a
contract nobody chose. Look for `.openapi-generator/` and similar markers.

### C# — implemented, syntax-only, and one query does not transfer

Roslyn parses; no compilation is built, because that would need every project
restored and the structure of a family is visible without it. That one choice is
behind everything below.

**`calls --on <TypeName>` mostly does not work, and the reason is bigger than
extension methods.** Without a semantic model, the receiver of an instance call
is a *variable name*, not a type. Across a real ASP.NET codebase the commonest
receivers were `_userManager`, `_logger`, `_mockBasketRepo`, `builder` — fields
and locals. So `calls --on BasketService` finds nothing, while `calls --on
Assert` works, because a static call names its type at the call site.

What survives: `--on` a **field or a static type** answers "what does this
codebase do with this thing", which is a convention question worth asking. What
does not survive: called-but-not-defined. The check that found four dead
`.where()` call sites in Python cannot be trusted on C# instance calls and must
not be reported as though it could. Extension methods are one symptom of the
same missing information, not a separate problem.

**Partial classes are merged, by namespace *and* name.** `shape` counts classes,
and a type declared across three files would count three times and skew every
percentage. Verified on EF migrations, the classic case: `InitialModel.cs` and
`InitialModel.Designer.cs` yield one record carrying `Up`, `Down` and
`BuildTargetModel` together. The namespace in the key is not optional — the same
codebase has `CatalogItem` as both an entity and a Blazor model, and merging
those would invent a type that does not exist.

**Reachability has no build-time analogue.** In Python, a class nothing imports
never registers, and that is the failure this skill exists to catch. In C# an
unreferenced class compiles perfectly. The same disease appears as a service
never added to the container or a controller never discovered — so the check
moves from the compiler to a query against the composition root:

```bash
scripts/query.py calls --on services   # or --on builder, --on app
```

That works for the same reason `calls --on <TypeName>` does not: a field or
static receiver keeps its name at the call site, and `services` is one.
Measured on eShopOnWeb it reports `AddScoped` 21 and `AddDbContext` 4, naming
`ServicesConfiguration.cs` and `Dependencies.cs` — the files a new service has
to be added to, which is what `imports --chain` answers in Python. The recipe
is in `MANUAL.md`.

**The adapter is built, not shipped.** `dotnet build -c Release` runs once on
first use and the assembly is cached. If you are reading a C# codebase the SDK
is present by definition — the same argument that lets the TypeScript extractor
use the project's own compiler.

### JavaScript — implemented, on its own parser

Its own extractor, on **acorn**, not the TypeScript compiler. The reason is not
tidiness: a JavaScript project is not obliged to have TypeScript installed, and
while the two shared an extractor such a codebase **could not be indexed at
all** — the compiler lookup simply failed and every file came back unparsed.
acorn is the parser inside eslint, vite, webpack and rollup, so it is present in
essentially any real JavaScript project. `acorn-jsx` is loaded when found, and
only `.jsx` needs it.

The two adapters are deliberate near-copies emitting identical records, and
`selftest.py` is what keeps that true rather than aspirational. What is *not*
shared is what genuinely differs:

**CommonJS, which was previously invisible.** `require()` at any depth becomes an
import; `module.exports = {...}` and `exports.x` become exports. Both are
ordinary expressions rather than declarations, so an ESM-only walk misses them
entirely — before this, a published package showed 0 exports; after, 358 of 359
modules carry them.

**JSDoc types**, which give JavaScript an `ATTRIBUTE DETAIL` worth reading.
`@type {T}` fills `ann`, `@returns {T}` fills `returns`. A codebase that
documents its types has told you them, and discarding that would leave the
section empty for no reason.

**Parsed as a module, then as a script.** The two differ only where it matters —
`import` is a syntax error in a script — and CommonJS is legal in either.

Expect most `.js` in a *TypeScript* project to be configuration: in a real one
the single `.js` file was `eslint.config.js`, seven imports and no definitions.

Two shapes that only appear once you index real JavaScript:

**Anonymous default exports.** `export default (o, c, d) => {...}` is how
plugins, middleware and wrapped components are written, and it has no name for a
declaration walker to find. Indexing a real package recorded 74 functions before
this was handled and 111 after — a third of the codebase was invisible. They are
recorded under the name `default`; what such a function *calls* is the entire
convention.

**Published packages ship minified bundles at their own root.** Not under
`dist/`, so no directory rule catches them, and they parse perfectly — one
reported `Error` as a dominant base class. Files whose longest line runs past a
couple of thousand characters are build output, and are skipped and counted, not
read.

### HTML templates — a family whose contract is inheritance

Django and Jinja templates read through the existing schema with no new record
kind and no new query, because the mapping is exact rather than convenient:
`{% extends %}` is a base class, `{% block %}` is a method, `{% include %}` is
a call. On Django's admin family that yields, immediately:

```
28 classes
== BASE CLASSES ==   ALWAYS  admin/base_site.html
== METHODS ==        ALWAYS  content
                      89%    breadcrumbs
                      68%    title
                     VARIES  extrastyle (29%), coltype (25%), bodyclass (25%)
```

Which is the contract of that family, and recognisable to anyone who has written
a Django admin page. Flask's Jinja templates read the same way — a different
dialect of one family.

**Template inheritance is a registration chain**, and it is the reason this is
worth doing rather than decorative. There is no barrel file: a page names its
parent directly, so `imports --chain` walks *down* through inheritance —
`admin/base.html` → `admin/base_site.html` → 28 pages → 13 more. Change a base
template or forget to fill the block a parent expects, and nothing errors. The
page renders wrong, or empty. That is the same silent failure as a class
nothing imports.

**`FIDELITY` is `heuristic` here, and that is not a footnote.** There is no
template parser in the standard library, so this is regex. A heuristic
extractor claiming "100% of pages do this" is a weaker statement than an AST one
making the same claim, and `shape` can only be read correctly by someone who
knows which they have.

Two traps, both from the 393 real templates rather than from imagination:

- **`{% blocktranslate %}` is not a block.** It appears 25 times, and a
  `block\s*` pattern invents a block named `translate` on pages that have none.
  Requiring whitespace before the name excludes it exactly.
- **`{% include widget.template_name %}` names a variable, not a file** — the
  target is decided at render time. Recorded under `unresolved_includes` and
  never resolved, which is the same honesty as a C# instance call whose
  receiver is a field rather than a type.

A page with no directives and no assets gets a module record but no class
record. Static markup is not a convention, and one record per marketing page
would drown the family that has one.

### Stylesheets — a design system's contract is its tokens

CSS, SCSS and Less read as above. `ATTRIBUTE DETAIL` is the section that earns
it, because a token's *value* is the contract:

```
  --card-spacer-y        #{$card-spacer-y} 100%
  --card-border-radius   #{$card-border-radius} 100%
```

**Every design token is written interpolated.** Bootstrap spells them
`--#{$prefix}card-spacer-y`, and a pattern wanting `--[a-z]` finds **15** of
what are really **548** — reporting a token family that does not exist. The
interpolation is stripped from the recorded name so one token groups as one
across the whole system, which is why the output above reads `--card-spacer-y`.

**A partial nobody imports does nothing**, silently: no error, no style, a page
that merely looks wrong. `imports <partial>` answers it, and `@import` is the
chain — there is no barrel file.

**A mixin defined but never included is dead.** Bootstrap defines 80 and
includes 62 distinct ones. `calls --on <mixin>` reports this, but read the
caveat it prints: a public mixin is called from outside the index, and absence
of a caller is not absence of a caller.

**`shape` is weaker here than elsewhere, and that is the honest summary.** Model
classes and controllers are deliberately alike, so `ALWAYS` means something.
Stylesheets are deliberately *different* from one another — `_card.scss` and
`_modal.scss` share almost nothing — so `shape` across a whole `scss/` directory
returns a mush of one-percent rows. It is worth running on a set that really is
a family (component partials, a token file) and not otherwise. The durable value
here is `imports`, `calls` and `ATTRIBUTE DETAIL`, not `ALWAYS`.

`.sass` is deliberately excluded: it is indentation-based rather than braced, so
the scanner would read it wrongly rather than not at all. It is reported as not
covered.

## Container formats: one file, several languages

`.vue`, `.svelte`, `.razor` and `.cshtml` are **not languages** and have no
extractor. They are split by a *segmenter* under `scripts/segmenters/`, and each
span is then read by the extractor that already handles that language. Nothing
downstream learns a new concept.

A segmenter declares `EXTENSIONS` and `FORMAT`, and yields
`(extension, text, line_offset, role)`. The extension decides the extractor; a
span whose extension nothing claims — the markup, the styles — is counted as
**not covered**, because a component whose template went unread is not a
component with no template.

**The line offset is the whole contract.** A record pointing into a temporary
span rather than at the file a person will open looks correct and is not, so
`selftest.py` puts a definition on a known line of each format and asserts it
survives the trip. Verified across 230 Vue, 24 Svelte and 13 Razor files from
real projects: 83 definitions, every one landing on the line that declares it.

**A top-level block starts at column 0.** This is the rule that makes the scan
work and the one a naive parser gets wrong. Across those 230 components every
top-level `<template>`, `<script>` and `<style>` is at the first column, while
`<template v-if=…>` and `<template slot-scope=…>` — ordinary elements *inside*
the template, and far more numerous — are always indented. Scanning for
`<template` anywhere finds dozens of false blocks per file; closing at the first
`</template>` ends the block in the middle of the markup.

**Attributes are parsed, not matched.** `<script lang="ts" setup>` and
`<script setup lang="ts">` both occur, 58 and 19 times in the sample.

**A `@code` block is not a compilation unit.** It holds class *members* with no
class around them, so Razor wraps it in one, named after the file — which is
also the name Blazor generates. The wrapper is deliberately **one** line: with
two, the synthetic class and its members disagree by one, because the class must
land on the `@code {` line and each member one line further down.

**Spans are read with the temporary directory as their root.** An adapter is
entitled to compute a relative path by trimming the root it was given, and one
of them does — a file outside that root came back named `.js` and every record
was silently dropped. The package's own parser is passed separately, through the
override the extractors already carry.

What this does *not* reach, and why:

- **Vue 2 Options API components define nothing at the top level.** `export
  default { methods: { … } }` is an object literal, so 130 components yield 130
  module records, 86 with imports and 120 with exports, and **zero** classes or
  functions. The same shape as React: the convention is not in declarations.
  Vue 3's `<script setup>` does declare, and reads properly.
- **A Vue 2 script block written in JSX fails to parse**, because the block is
  handed over as `.js` and nothing declares otherwise — one file in 130. It is
  reported as `unparsed` with the reason, not silently skipped.
- **`.cshtml` has no `@code` in practice** — zero across 48 real views. What it
  has is `@{ … }` statement blocks, which are statements rather than members and
  would need a second synthetic wrapper around a method nobody wrote.
- **`@inject`, `@inherits` and `@page` are not recorded.** They are the Blazor
  form of imports and routing — the wiring question — and reaching them means
  emitting records, which a segmenter does not do.

## Adding one

First decide which of the three things you are adding, because only one of them
is a language:

- **A language** — a parser of its own. An extractor, below.
- **A technology** — React, Vue, SQLAlchemy, ASP.NET. *Not* an extractor: it is
  visible in what a module imports, so it is a row in `TECHNOLOGIES` in
  `query.py` and reaches `--tech` immediately, with no rebuild.
- **A container format** — one file holding several languages. A segmenter, not
  an extractor, and it must add a fixture to `CONTAINERS` in `selftest.py` with
  a definition on a known line.

To add a language:

1. Write the extractor, emitting the same records. Start with `class`, `module`
   and `func`; `calls` and `invokes` earn their keep immediately after.
2. Add a row to `LANGUAGES` in `query.py`: proof files, barrel file, entry
   point, rung-1 command, and where its toolchain lives.
3. Add a rung-1 and rung-2 command to the table above.
4. Index a real codebase in that language and run `shape` on a family you already
   understand. If the output does not tell you something you knew, the extractor
   is not recording enough yet.

That last step is the test that matters. An extractor validated only against
files written to test it will agree with itself and nothing else.
