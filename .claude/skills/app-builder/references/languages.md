# Languages: what maps to what, and what does not

The index schema is the seam. Everything downstream — `layers`, `find`, `shape`,
`exemplars`, `imports`, `calls`, `conform` — reads records and never asks what
produced them. A language is added by producing records, not by changing queries.

**Python and TypeScript are implemented**, both at AST fidelity. C# is design
only — the rest of this file is the map for it, and the traps to avoid first.

## The extractor contract

```python
LANGUAGE   = "typescript"          # stamped on every record as `lang`
FIDELITY   = "ast"                 # "ast" or "heuristic"
EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mts", ".cts")

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

## The mapping

|  | Python | TypeScript / JavaScript | C# |
|---|---|---|---|
| parser | stdlib `ast`, in-process | TS compiler API, via node | Roslyn, via dotnet |
| `class` record | class | class, interface, type alias | class, struct, interface, record |
| `bases` | base classes | `extends`, `implements` | base type + interfaces |
| `decorators` | decorators | decorators | attributes |
| `attrs` | annotated assignments | interface fields, class properties | fields and properties |
| `methods` | def / async def | methods, arrow properties | methods |
| `imports` | import, from-import | import, `import type` | using |
| `exports` | `__all__` or public names | export, export default | none — namespaces |
| `calls` | `obj.method(...)` | `obj.method(...)` | `obj.Method(...)` |
| `invokes` | `f(...)` | `f(...)` — **hooks live here** | `F(...)` |
| barrel file | `__init__.py` | `index.ts` | none |
| rung 1 | `import M` | `tsc --noEmit` | `dotnet build` |
| rung 2 / 4 | pytest | vitest, `npm run build` | `dotnet test` |

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

**JSX is the markup.** There is no separate HTML layer worth indexing in a React
codebase; four `.html` files at the root are the shell. Likewise styling under
MUI or emotion is TypeScript objects, not CSS. One extractor covers what looks
like three languages.

**A generated API client is not an exemplar.** `openapi-generator` output has the
shape of the generator, not of the codebase. Exclude it, or `shape` will report a
contract nobody chose. Look for `.openapi-generator/` and similar markers.

### C# — implemented, syntax-only, and one query does not transfer

Roslyn parses; no compilation is built, because that would need every project
restored and the structure of a layer is visible without it. That one choice is
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
moves from the compiler to a query against the composition root.

**The adapter is built, not shipped.** `dotnet build -c Release` runs once on
first use and the assembly is cached. If you are reading a C# codebase the SDK
is present by definition — the same argument that lets the TypeScript extractor
use the project's own compiler.

### JavaScript — implemented, by the same extractor

One parser, two reported languages. The TypeScript compiler reads JavaScript at
the same fidelity, so `.js` costs nothing extra — but a `.js` file is stamped
`javascript`, not `typescript`. Reporting it as TypeScript would make `--lang
javascript` return nothing while JavaScript sat in the index, which is a lie the
reader has no way to catch.

Expect `ATTRIBUTE DETAIL` to be nearly empty: with no annotations there is no
modal form to report. And expect most `.js` in a TypeScript project to be
configuration — in a real one, the single `.js` file was `eslint.config.js`,
with seven imports and no definitions at all.

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

## Adding one

1. Write the extractor, emitting the same records. Start with `class`, `module`
   and `func`; `calls` and `invokes` earn their keep immediately after.
2. Add a row to `LANGUAGES` in `query.py`: proof files, barrel file, entry point.
3. Add a rung-1 and rung-2 command to the table above.
4. Index a real codebase in that language and run `shape` on a layer you already
   understand. If the output does not tell you something you knew, the extractor
   is not recording enough yet.

That last step is the test that matters. An extractor validated only against
files written to test it will agree with itself and nothing else.
