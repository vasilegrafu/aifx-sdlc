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

### C#

**Extension methods make `calls` cry wolf.** `x.Where(...)` is defined on
`Enumerable`, not on the type of `x`, so a naive called-but-not-defined check
reports MISSING for the most idiomatic code in the language. Resolve them or
exclude them — a check that fires on correct code is worse than no check, because
it teaches the reader to skip the output.

**Partial classes split one type across files.** `shape` counts classes; a type
declared in three files counts three times and skews every percentage in the
layer. Merge partials before emitting records.

**Reachability has no build-time analogue.** In Python, a class nothing imports
never registers, and that is the failure this skill exists to catch. In C# an
unreferenced class compiles perfectly. The same disease appears as a service
never added to the container or a controller never discovered — so the check
moves from the compiler to a query against the composition root.

### JavaScript

Same extractor as TypeScript, minus the types. Expect `ATTRIBUTE DETAIL` to be
nearly empty — without annotations there is no modal form to report — and expect
most `.js` files in a TypeScript project to be configuration rather than source.

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
