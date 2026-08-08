"""Query a structural index built by index.py.

Every subcommand answers a question with a few hundred lines at most, so that a
codebase of any size can be understood without reading it.

    config      which codebases and which destination are configured
    proof       how a codebase proves itself: tests, entry points, interpreter
    layers      what parts exist, and which is the one you were asked about
    calls       methods invoked on a name vs. the ones that name defines
    conform     whether generated code still keeps the contract that produced it
    find        the classes/functions matching a filter -- and their files
    shape       what is ALWAYS true of a set of classes vs. what VARIES
    exemplars   the most typical file to copy, and the outlier that shows why
    imports     who imports a symbol -- the wiring that makes it take effect
    questions   the decisions a layer forces, ranked by what they cost
    practice    how a reference corpus resolves a choice vs. the exemplar
    deps        what a codebase declares it depends on, and what it runs
    meta        what this index covers and when it was built

`shape` is the one that matters. What is always true is contract: reproduce it.
What varies is the axis of choice: decide it, deliberately. What one repository
always does and another never does is a disagreement: ask, do not average.

`practice` is the counterweight, and reads the reference corpus that every other
command holds out. `shape` cannot question what a codebase is unanimous about --
unanimity is exactly what it reports as the contract -- so the most deeply
embedded choice in a codebase is the one nothing ever raises. That is what
`practice` is for, and evidence is all it produces: the user decides.
"""

from __future__ import annotations

import argparse
import datetime
import fnmatch
import json
import re
import shutil
from collections import Counter, defaultdict

from _common import (configured_questions, configured_references,
                     configured_repositories, configured_solution, corpus_root,
                     INDEX_SCHEMA, ROLE_DIRS, ROLE_ORDER,
                     display_path, find_files, index_meta, index_root,
                     index_schema_warning, indexed_repositories, iter_source_files,
                     load_config, pct,
                     indexed_roles, read_index, rollup_path, skill_root,
                     truncate)
from extractors import ALL_EXTENSIONS

# ---------------------------------------------------------------- filtering


def head(expr: str) -> str:
    """`session_injector` from `session_injector(x)`; `app.route` from `app.route(...)`."""
    return expr.split("(", 1)[0].strip()


def symbol_root(expr: str) -> str:
    """`Base` from `Base[Model]`, `Base<T>`, `Base(x)`; `app.route` keeps its dot.

    Generic parameters are not part of the name. A layer written
    `Repository[Student]`, `Repository[Subject]` is one base class used twice,
    and treating the parameter as part of it reports two families of one.
    """
    e = head(expr).strip()
    for sep in ("[", "<"):
        if sep in e:
            e = e.split(sep, 1)[0]
    return e.strip()


def symbol_matches(expr: str, wanted: str) -> bool:
    """Whether a base or decorator expression is the one asked for.

    Exact on the root, not a substring. `--base Model` matching `BaseModel`,
    `ModelForm` and `db.Model` alike was silently blending families inside the
    one command whose job is separating them -- and the blend is invisible,
    because the output looks like a layer that merely disagrees with itself.

    Two accommodations, both narrow. A dotted expression matches on its last
    segment, so `--decorator route` finds `app.route` and `--base Model` finds
    `db.Model`; that is qualification, not a different name. And a `*` or `?`
    in the wanted string means the caller wants a pattern and gets one, which
    is how the old loose behaviour stays available to anyone who meant it.

    The dotted tail is withheld from anything path-shaped. A template's base is
    `admin/base_site.html`, whose last dotted segment is `html` -- so `--base
    html` would match every template in the project.
    """
    if any(ch in wanted for ch in "*?"):
        return (fnmatch.fnmatch(head(expr), wanted)
                or fnmatch.fnmatch(symbol_root(expr), wanted))
    root = symbol_root(expr)
    if root == wanted:
        return True
    return "/" not in root and root.rsplit(".", 1)[-1] == wanted


def call_sites(entries) -> list[tuple[str, int | None]]:
    """`(name, line)` for each recorded call, whatever shape it was stored in.

    Calls used to be bare strings and are now `[name, line]`. Both are accepted
    on purpose: an index built before the change still answers every question
    except *where*, and the alternative is making a rebuild mandatory to read
    anything at all.
    """
    out = []
    for entry in entries or ():
        if isinstance(entry, str):
            out.append((entry, None))
        elif entry:
            out.append((entry[0], entry[1] if len(entry) > 1 else None))
    return out


def call_names(entries) -> list[str]:
    return [name for name, _ in call_sites(entries)]


def add_filters(ap):
    ap.add_argument("--path", help="glob on the file path, e.g. 'database/*/models/*'")
    ap.add_argument("--not-path", action="append", metavar="GLOB", default=[],
                    help="exclude paths matching this glob; repeatable. Use it to "
                         "hold a linked-in library out of an application's shape")
    ap.add_argument("--base", help="only classes with this base (matches any base)")
    ap.add_argument("--decorator", help="only classes/functions carrying this decorator")
    ap.add_argument("--symbol", help="regex on the class/function name")
    ap.add_argument("--repo", help="restrict to one repository")
    ap.add_argument("--lang", help="restrict to one language, e.g. python, typescript")


def add_kind_and_tech(ap):
    """The two filters that only the measuring commands can honour.

    `--tech` needs the whole index before it can filter, and `--kind` chooses
    what is being measured, so neither belongs in the shared filter set that
    `calls` and `imports` also use.
    """
    ap.add_argument("--kind", choices=("class", "func"), default="class",
                    help="what to describe: classes (default), or module-level "
                         "functions -- components, hooks and handlers are functions")
    ap.add_argument("--tech", metavar="NAME",
                    help="restrict to modules importing this technology, e.g. "
                         "react, sqlalchemy, aspnet (see TECHNOLOGIES)")


def matches(rec, args) -> bool:
    if args.repo and rec["repo"] != args.repo:
        return False
    if getattr(args, "lang", None) and language_of(rec) != args.lang:
        return False
    if args.path and not fnmatch.fnmatch(rec["path"], args.path):
        return False
    for glob in getattr(args, "not_path", ()) or ():
        if fnmatch.fnmatch(rec["path"], glob):
            return False
    if args.base:
        if rec["k"] != "class" or not any(symbol_matches(b, args.base)
                                          for b in rec["bases"]):
            return False
    if args.decorator:
        if not any(symbol_matches(d, args.decorator)
                   for d in rec.get("decorators", [])):
            return False
    if args.symbol and not re.search(args.symbol, rec.get("name", "")):
        return False
    return True


def collect(args, kinds=("class",)):
    """Matching definitions, plus the technology map they are filtered by.

    One pass. A definition's technology is a property of the module that holds
    it, so the map has to be complete before anything can be filtered by it --
    which is why the filter is applied at the end rather than per record.
    """
    recs, tech, other = [], {}, 0
    for r in read_index():
        # Directive-borne technologies live on the *class* record, because that
        # is where a template's attributes are recorded -- so the map is fed
        # from both kinds and merged, rather than from modules alone.
        markup = markup_technologies_of(r)
        if markup:
            tech.setdefault((r["repo"], r["path"]), set()).update(markup)
        if r["k"] == "module":
            found = technologies_of(r.get("imports"))
            if found:
                tech.setdefault((r["repo"], r["path"]), set()).update(found)
        elif r["k"] in kinds and matches(r, args):
            recs.append(r)
        elif r["k"] == "func" and matches(r, args):
            # Counted so `shape` can say that the filter also matched functions
            # it is not describing -- silence there reads as "there is nothing".
            other += 1
    args._tech, args._other_kind = tech, other
    want = getattr(args, "tech", None)
    if want:
        recs = [r for r in recs if want in tech.get((r["repo"], r["path"]), ())]
    return recs


def describe_size(rec) -> str:
    if rec["k"] == "func":
        return (f"{len(rec.get('params', ()))} params,"
                f" {len(rec.get('invokes', ())) + len(rec.get('calls', ()))} calls")
    return f"{len(rec['attrs'])} attrs, {len(rec['methods'])} methods"


def kinds_for(args) -> tuple[str, ...]:
    """`shape` and `exemplars` describe one kind at a time, deliberately.

    A layer of classes and a layer of functions have different shapes, and
    measuring them together reports a form neither one has -- the same error as
    averaging two codebases.
    """
    return ("func",) if getattr(args, "kind", "class") == "func" else ("class",)


# ---------------------------------------------------------------- features


def param_names(param: str) -> list[str]:
    """The names a parameter binds.

    A destructured parameter is recorded as its source text, because that is
    the honest record of what was written -- but `{ sx = undefined, children,
    ...props }` is one useless feature where it should be three useful ones.
    A component layer's real contract is that every component takes `children`,
    and that is only visible once the blob is split.
    """
    p = (param or "").strip()
    if not (p.startswith("{") or p.startswith("[")):
        return [p.split(":", 1)[0].strip().lstrip("*&") or p]
    out, depth, current = [], 0, ""
    for ch in p[1:-1] if len(p) > 1 else "":
        if ch in "{[(":
            depth += 1
        elif ch in "}])":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(current)
            current = ""
        else:
            current += ch
    out.append(current)
    names = []
    for item in out:
        # `children`, `sx = undefined`, `a: b`, `...props` -- the bound name is
        # what stands before a default or a rename.
        name = item.split("=", 1)[0].split(":", 1)[0].strip().lstrip(".").strip()
        if name and all(c.isalnum() or c in "_$" for c in name):
            names.append(name)
    return names or ["(destructured)"]


def features(rec) -> set[str]:
    """The comparable shape of one definition, as a set of `kind:item` strings.

    Both record kinds reduce to the same form, so `shape`, `exemplars` and
    `conform` can measure a layer of classes and a layer of functions with one
    piece of machinery.

    What a definition *calls* is part of its shape. In a class-based data layer
    that is a minor signal next to its attributes; in a React or hook-based
    codebase it is nearly the whole convention, because nothing is declared --
    `useState`, `useSelector` and a codebase's own `useConfig` appear only as
    calls, and a measure that ignored them would report that such a layer has
    no conventions at all.
    """
    if rec["k"] == "func":
        f = {f"funcdec:{head(d)}" for d in rec.get("decorators", ())}
        f |= {f"param:{n}" for p in rec.get("params", ()) for n in param_names(p)}
        if rec.get("returns"):
            f.add(f"returns:{head(rec['returns'])}")
        if rec.get("async"):
            f.add("modifier:async")
        f |= {f"invoke:{i}" for i in call_names(rec.get("invokes"))}
        f |= {f"call:{c}" for c in call_names(rec.get("calls"))}
        return f

    f = {f"base:{head(b)}" for b in rec["bases"]}
    f |= {f"classdec:{head(d)}" for d in rec["decorators"]}
    f |= {f"assign:{a['name']}" for a in rec["assigns"]}
    f |= {f"attr:{a['name']}" for a in rec["attrs"]}
    f |= {f"attrcall:{a['call']}" for a in rec["attrs"] if a["call"]}
    f |= {f"method:{m['name']}" for m in rec["methods"]}
    for m in rec["methods"]:
        f |= {f"methoddec:{head(d)}" for d in m["decorators"]}
        f |= {f"invoke:{i}" for i in call_names(m.get("invokes"))}
        f |= {f"call:{c}" for c in call_names(m.get("calls"))}
    return f


LABELS = {
    "base": "base classes", "classdec": "class decorators",
    "assign": "class-level assignments", "attr": "attributes",
    "attrcall": "attribute constructors", "method": "methods",
    "methoddec": "method decorators",
    "funcdec": "decorators", "param": "parameters", "returns": "returns",
    "modifier": "modifiers",
    "invoke": "functions called", "call": "calls on a receiver",
}

# A technology is not a language: React is JavaScript, SQLAlchemy is Python,
# and neither is a thing to parse. Both are visible in what a module imports,
# so they are derived here at query time rather than stamped into the index --
# improving this table costs nothing and never needs a rebuild.
TECHNOLOGIES = {
    "react": ("react", "react-dom", "next", "preact"),
    "redux": ("react-redux", "@reduxjs/toolkit", "redux"),
    "mui": ("@mui", "@emotion"),
    "vue": ("vue", "nuxt"),
    "angular": ("@angular",),
    "svelte": ("svelte",),
    "vitest": ("vitest",),
    "jest": ("jest", "@testing-library"),
    "muix": ("@mui/x-data-grid", "@mui/x-date-pickers", "@mui/x-tree-view",
             "@mui/x-charts"),
    "sqlalchemy": ("sqlalchemy",),
    "alembic": ("alembic",),
    "django": ("django",),
    "flask": ("flask",),
    "fastapi": ("fastapi", "starlette"),
    "pydantic": ("pydantic",),
    # Split. Bundling these meant `--tech pandas` matched 66 modules that import
    # numpy and never touch pandas -- they are different technologies answering
    # different questions, and a filter that conflates them describes neither.
    "pandas": ("pandas",),
    "numpy": ("numpy",),
    "scipy": ("scipy",),
    "sklearn": ("sklearn", "scikit-learn"),
    "torch": ("torch", "torchvision", "pytorch_lightning", "lightning"),
    "tensorflow": ("tensorflow", "tf"),
    "keras": ("keras",),
    "plotly": ("plotly", "dash"),
    "echarts": ("echarts", "echarts-for-react"),
    "pytest": ("pytest", "unittest"),
    "aspnet": ("Microsoft.AspNetCore",),
    "efcore": ("Microsoft.EntityFrameworkCore",),
    "xunit": ("Xunit", "NUnit", "Moq"),
    "blazor": ("Microsoft.AspNetCore.Components",),
}


# Technologies that are not imported at all. htmx and Alpine arrive as a script
# tag -- usually a CDN URL that no prefix match will recognise -- and are *used*
# entirely through attributes. The directive is the only reliable signal, so it
# is the one used.
#
# `@click` and `:class` are deliberately absent: Alpine and Vue share them, and
# a signal that cannot tell two technologies apart should not name either.
DIRECTIVE_TECHNOLOGIES = {
    "htmx": ("hx-",),
    "alpine": ("x-",),
}


def technologies_of(imports) -> set[str]:
    out = set()
    for imp in imports or ():
        mod = imp.get("mod") or ""
        for tech, prefixes in TECHNOLOGIES.items():
            if any(mod == p or mod.startswith(p + ".") or mod.startswith(p + "/")
                   for p in prefixes):
                out.add(tech)
    return out


def markup_technologies_of(rec) -> set[str]:
    """Technologies evidenced by directives rather than by imports."""
    names = call_names(rec.get("calls"))
    return {tech for tech, prefixes in DIRECTIVE_TECHNOLOGIES.items()
            if any(n.startswith(p) for n in names for p in prefixes)}

# ---------------------------------------------------------------- commands


def cmd_config(args):
    """What this skill has been pointed at, and whether it is actually there."""
    cfg = load_config()
    print(f"config  {display_path(cfg['_file'])}"
          f"{'' if cfg['_exists'] else '   (does not exist)'}\n")

    repos = configured_repositories()
    if not repos:
        print("REPOSITORIES  none configured. Add them to the config file:\n")
        print('  "app-builder": {\n'
              '    "exemplar_corpus": [{"name": "atlas", "path": "D:/code/atlas"}],\n'
              '    "solution": "solution"\n'
              '  }')
    else:
        print("EXEMPLARS     what you copy -- their conventions are the contract")
        for r in repos:
            print(f"  {'ok ' if r['exists'] else 'MISSING'}  {r['name']:<20} "
                  f"{display_path(r['path'])}")

    target = configured_solution()
    print(f"\nTARGET        {'ok ' if target['exists'] else 'not built yet'}  "
          f"{target['name']:<20} {display_path(target['path'])}")
    print("              indexed with the sources; where it has already diverged,"
          "\n              it is the later decision and it wins")

    refs = configured_references()
    if refs:
        missing = [r for r in refs if not r["exists"]]
        print(f"\nREFERENCES    {len(refs)} codebase(s), "
              f"{len(refs) - len(missing)} present")
        print("              evidence about what the wider world does, never a"
              "\n              template. Held out of shape, layers, exemplars,"
              "\n              questions and DISAGREEMENTS; read by `practice`,"
              "\n              and by `deps` only with --references.")
        print(f"              under {display_path(corpus_root())}/")
        for r in refs:
            # The path is deliberately not repeated per row. A fetched
            # reference is located by its name -- the directory *is* the name --
            # so printing the same prefix twenty-three times says nothing the
            # header did not. A reference given an explicit `path` instead is
            # the exception, and only that one shows where it points.
            elsewhere = ("" if r["path"] == (corpus_root() / r["name"]).resolve()
                         else f"   {display_path(r['path'])}")
            print(f"  {'ok ' if r['exists'] else 'MISSING'}  "
                  f"{r['name'] + elsewhere if elsewhere else r['name']}")
            # Scoping is the difference between evidence about how a library is
            # used and a dump of how it is written, so it is worth seeing here
            # rather than only in the config file.
            if r.get("include"):
                print(f"        include  {', '.join(r['include'])}")
            if r.get("exclude"):
                print(f"        exclude  {', '.join(r['exclude'])}")
    else:
        print("\nREFERENCES    none configured -- every claim about what is or is not"
              "\n              current practice is then an assertion, not evidence."
              '\n              Add them under "reference_corpus": [{"name": ..., "repo": ...}]'
              '\n              then fetch them:  scripts/fetch.py')

    mode = configured_questions()
    explain = {
        "many": "ask at every genuine decision point, as the work reaches it",
        "key": "ask only what is expensive to reverse; decide the rest",
        "none": "decide everything and report it; never interrupt",
    }
    print(f"\nQUESTIONS     {mode}   {explain[mode]}")
    if mode != "none":
        print("              Questions arrive throughout, not in one batch up front:")
        print("              a decision cannot be raised before the work reaches it,")
        print("              and every one offers options plus your own wording.")

    # There is one index, so what is worth reporting is not its name but what
    # it holds, by role -- which is the only thing that decides what any other
    # command can see.
    built = indexed_repositories()
    if not built:
        print(f"\nINDEX         not built -- run scripts/index.py")
        return
    counts = Counter(s["role"] for s in built)
    print(f"\nINDEX         {display_path(index_root())}")
    print("              " + ", ".join(
        f"{counts[role]} in {ROLE_DIRS[role]}/" for role in ROLE_ORDER if counts[role]))


# Per-language facts, kept in one table rather than scattered through the
# queries. Everything else here reads the index schema and does not care what
# produced it; these are the few places that must. A new language is a new row.
LANGUAGES = {
    "python": {
        "proof_files": ("pytest.ini", "tox.ini", "setup.cfg", "pyproject.toml",
                        "noxfile.py", "Makefile", "manage.py", "conftest.py",
                        "alembic.ini", "requirements.txt"),
        # the file that re-exports a package, and so continues a registration chain
        "barrel": "__init__.py",
        "entry": "a module guarded by __main__",
        "rung1": "smoke.py -- it imports, and something imports it",
        "toolchain": (".venv/Scripts/python.exe", ".venv/bin/python",
                      "venv/Scripts/python.exe", "venv/bin/python"),
    },
    "typescript": {
        "proof_files": ("package.json", "tsconfig.json", "vitest.config.ts",
                        "jest.config.js", "playwright.config.ts", "vite.config.ts"),
        "barrel": "index.ts",
        "entry": "a script in package.json",
        "rung1": "tsc --noEmit",
        "toolchain": ("node_modules/typescript/package.json",),
    },
    "javascript": {
        "proof_files": ("package.json", "jest.config.js", "vitest.config.js",
                        "playwright.config.js", "eslint.config.js"),
        "barrel": "index.js",
        "entry": "a script in package.json",
        "rung1": "node --check <file>, or the project's lint script",
        "toolchain": ("node_modules/acorn/package.json",),
    },
    "css": {
        "proof_files": ("package.json", "postcss.config.js", ".stylelintrc.json"),
        # No barrel file: a partial is named directly by whatever imports it,
        # so the chain is `@import`, and a partial nobody imports is dead.
        "barrel": None,
        "entry": "the stylesheet that imports the partials",
        "rung1": "the project's sass/postcss build, or stylelint",
        "toolchain": ("node_modules/sass/package.json",),
    },
    "html": {
        # A template layer proves itself through whatever renders it, so its
        # proof files are the web framework's, not its own.
        "proof_files": ("manage.py", "pyproject.toml", "package.json"),
        # Template inheritance has no barrel file: a page names its parent
        # directly, so the chain is `bases`, and `imports --chain` follows it.
        "barrel": None,
        "entry": "a view or route that renders it",
        "rung1": "render it -- a template only fails when something renders it",
        "toolchain": (),
    },
    "csharp": {
        "proof_files": ("Directory.Build.props", "global.json", "nuget.config",
                        "*.sln", "*.csproj"),
        # C# has no re-export file: a namespace is visible without one, and the
        # analogue of an unimported class is a service never registered.
        "barrel": None,
        "entry": "a Main method or a host builder",
        "rung1": "dotnet build",
        "toolchain": ("global.json",),
    },
}


def language_of(rec) -> str:
    return rec.get("lang") or "python"


def barrel_for(rec) -> str | None:
    return LANGUAGES.get(language_of(rec), LANGUAGES["python"])["barrel"]


# An entry point that generates a schema, migrates, or starts a server is worth
# far more here than a module with a demo block at the bottom -- and a codebase
# has many more of the second kind.
ENTRY_RANK = ("generator", "generate", "migrat", "main", "program", "app",
              "server", "host", "startup", "importer", "seed", "cli", "manage")


def rank_entry(path: str) -> tuple[int, str]:
    low = path.lower()
    if "test" in low or "spec" in low:
        return (2, path)
    for i, word in enumerate(ENTRY_RANK):
        if word in low:
            return (0, f"{i:02d}{path}")
    return (1, path)


def find_toolchain(root, found: list[str], spec) -> str | None:
    """Where the toolchain for one language actually lives.

    Not at the repository root, in general. `node_modules/typescript` sits
    beside the `package.json` that asked for it, four directories down; a venv
    may sit *above* the codebase when one environment serves a whole checkout.
    So look beside every configuration file found, then at the root, then
    upward -- the same lesson as `find_files`, in the other direction too.
    """
    seen, bases = set(), []
    for f in found:
        d = (root / f).parent
        while d != root and d not in seen and root in d.parents:
            seen.add(d)
            bases.append(d)
            d = d.parent
    bases.append(root)
    bases += [p for p in list(root.parents)[:3]]
    for base in bases:
        for candidate in spec["toolchain"]:
            here = base / candidate
            if here.exists():
                try:
                    return rel_to(here, root)
                except ValueError:
                    return str(here)
    return None


def rel_to(path, root) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def npm_scripts(root, rel_path: str) -> list[str]:
    try:
        data = json.loads((root / rel_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return list((data.get("scripts") or {}).keys())


def cmd_proof(args):
    """What the codebase itself uses as proof -- step 8 needs this, and asking
    the user for it is asking them something their repository already says.

    Reported per language, because the answer is per language. A repository's
    Python side can have a venv and a pytest.ini while its TypeScript side has
    a package.json four directories down, and a single root-level answer
    describes neither.
    """
    # Index first: it says which languages are actually present, so the
    # filesystem is only asked about those.
    per_repo_langs, test_dirs, entries = defaultdict(Counter), Counter(), defaultdict(list)
    for rec in read_index():
        if args.repo and rec["repo"] != args.repo:
            continue
        if rec["k"] != "module":
            continue
        lang = language_of(rec)
        per_repo_langs[rec["repo"]][lang] += 1
        top = rec["path"].split("/")[0]
        if "test" in top.lower() or "spec" in top.lower():
            test_dirs[f"{rec['repo']}/{top}"] += 1
        if rec.get("main"):
            entries[rec["repo"]].append((lang, rec["path"]))

    targets = configured_repositories() + [configured_solution()]
    for repo in targets:
        if args.repo and repo["name"] != args.repo:
            continue
        label = f"{repo['name']}{'   (the generated target)' if repo.get('is_target') else ''}"
        print(f"== {label} ==   {display_path(repo['path'])}\n")
        if not repo["exists"]:
            print("  path does not exist on this machine\n")
            continue
        langs = per_repo_langs.get(repo["name"])
        if not langs:
            print("  nothing from this repository is in the index\n")
            continue

        for lang, n_files in langs.most_common():
            spec = LANGUAGES.get(lang)
            if not spec:
                continue
            print(f"  {lang}  ({n_files} files)")
            found = find_files(repo["path"], spec["proof_files"])
            print("      CONFIG     " + (", ".join(found[: args.limit])
                                         if found else "none found"))
            tool = find_toolchain(repo["path"], found, spec)
            if not tool and lang == "csharp" and shutil.which("dotnet"):
                tool = "dotnet (on PATH)"
            if not tool and lang in ("typescript", "javascript") and shutil.which("node"):
                tool = "node (on PATH), but the project's own is not installed"
            print("      TOOLCHAIN  " + (str(tool) if tool else "none in the tree"))
            print(f"      RUNG 1     {spec['rung1']}")
            if lang in ("typescript", "javascript"):
                for pkg in [f for f in found if f.endswith("package.json")]:
                    scripts = npm_scripts(repo["path"], pkg)
                    if scripts:
                        print(f"      SCRIPTS    {pkg}: "
                              + ", ".join(scripts[:8]))
            mine = [p for l, p in entries.get(repo["name"], ()) if l == lang]
            if mine:
                print("      ENTRY      " + f"{spec['entry']}")
                for p in sorted(mine, key=rank_entry)[: args.limit]:
                    print(f"                 {p}")
                if len(mine) > args.limit:
                    print(f"                 ... {len(mine) - args.limit} more")
            elif lang in ("python", "csharp"):
                print(f"      ENTRY      none found -- looked for {spec['entry']}")
        print()

    print("  TESTS       " + (", ".join(f"{d} ({n} files)"
                                        for d, n in test_dirs.most_common())
                              if test_dirs else "no test directories in the index"))


def check_shards() -> list[str]:
    """Repositories whose records do not match what their meta.json claims.

    Cheap insurance against a class of corruption that is otherwise completely
    silent. A shard and its summary are written by the same run, so they agree
    unless something interrupted it -- and an interrupted build used to leave a
    truncated shard beside a meta.json boasting the full count. Every query then
    answered, from a codebase that was not the one on disk.

    Shards are written atomically now, so this should never fire. It is kept
    because "should never" is what the previous arrangement also assumed, and
    because an index built by an older `index.py` is still on disk somewhere.
    """
    out = []
    for shard in indexed_repositories():
        try:
            claimed = json.loads(shard["meta"].read_text(encoding="utf-8"))
        except (OSError, ValueError):
            out.append(f"{shard['dir']}: unreadable meta.json beside a shard")
            continue
        actual = 0
        try:
            with shard["records"].open("r", encoding="utf-8") as fh:
                for line in fh:
                    if line.strip() and json.loads(line).get("k") == "module":
                        actual += 1
        except (OSError, ValueError) as exc:
            out.append(f"{shard['dir']}: unreadable records ({exc})")
            continue
        expected = claimed.get("files")
        if isinstance(expected, int) and expected != actual:
            out.append(f"{claimed.get('repo') or shard['dir']}: meta claims "
                       f"{expected} files, the shard holds {actual}")
    return out


def cmd_meta(args):
    path = rollup_path()
    if not path.exists():
        return print(f"no index at {display_path(index_root())}"
                     "\nbuild one first:  scripts/index.py")
    meta = json.loads(path.read_text(encoding="utf-8"))
    if args.verify:
        problems = check_shards()
        print("== INTEGRITY ==")
        if problems:
            print("  Every count below is therefore describing a codebase that"
                  " is not the one on\n  disk. Rebuild: scripts/index.py\n")
            for p in problems:
                print(f"  MISMATCH  {p}")
        else:
            print("  ok -- every shard holds the number of files its meta"
                  " claims")
        print()
    for k, v in meta.items():
        if isinstance(v, dict):
            print(f"{k:>10}:")
            for kk, vv in v.items():
                print(f"{'':>12}{kk} -> {vv}")
        elif isinstance(v, list):
            print(f"{k:>10}: {', '.join(map(str, v))}")
        else:
            print(f"{k:>10}: {v}")


def cmd_layers(args):
    dirs = defaultdict(lambda: {"files": 0, "classes": 0, "loc": 0,
                                "bases": Counter(), "names": []})
    for rec in read_index():
        # Only kinds this counts. Anything else -- a manifest, an unparsed file
        # -- would otherwise create a directory row with no files and no classes
        # in it, which reads as a layer that exists and is empty.
        if rec["k"] not in ("module", "class"):
            continue
        if args.repo and rec["repo"] != args.repo:
            continue
        if args.path and not fnmatch.fnmatch(rec["path"], args.path):
            continue
        if any(fnmatch.fnmatch(rec["path"], g) for g in args.not_path or ()):
            continue
        # A solution with a Python backend and a TypeScript frontend reports both
        # under one directory tree, and the question "where is the React" cannot
        # be asked without this. Every other measuring command already takes it.
        if getattr(args, "lang", None) and language_of(rec) != args.lang:
            continue
        d = rec.get("dir") if rec["k"] == "module" else (
            rec["path"].rsplit("/", 1)[0] if "/" in rec["path"] else "")
        key = "/".join(d.split("/")[: args.depth]) if args.depth else d
        key = f"{rec['repo']}/{key}" if key else rec["repo"]
        e = dirs[key]
        if rec["k"] == "module":
            e["files"] += 1
            e["loc"] += rec.get("loc", 0)
        elif rec["k"] == "class":
            e["classes"] += 1
            for b in rec["bases"]:
                e["bases"][head(b)] += 1
            if len(e["names"]) < 3:
                e["names"].append(rec["name"])

    rows = sorted(dirs.items(), key=lambda kv: -kv[1]["classes"])[: args.limit]
    print(f"{'DIRECTORY':<58} {'FILES':>6} {'CLASSES':>8} {'LOC':>8}  DOMINANT BASE")
    for key, e in rows:
        base = e["bases"].most_common(1)
        base_s = f"{base[0][0]} ({base[0][1]})" if base else "-"
        print(f"{truncate(key, 57):<58} {e['files']:>6} {e['classes']:>8} "
              f"{e['loc']:>8}  {truncate(base_s, 40)}")


def cmd_find(args):
    recs = collect(args, kinds=("class", "func") if args.functions else ("class",))
    if args.files:
        for p in sorted({f"{r['repo']}/{r['path']}" for r in recs}):
            print(p)
        print(f"\n{len(recs)} definitions in {len({r['path'] for r in recs})} files")
        return
    for r in recs[: args.limit]:
        if r["k"] == "class":
            bases = f"({', '.join(head(b) for b in r['bases'])})" if r["bases"] else ""
            print(f"{r['repo']}/{r['path']}:{r['line']}  class {r['name']}{bases}"
                  f"  [{len(r['attrs'])} attrs, {len(r['methods'])} methods]")
        else:
            print(f"{r['repo']}/{r['path']}:{r['line']}  def {r['name']}"
                  f"({', '.join(r['params'])})")
    if len(recs) > args.limit:
        print(f"... {len(recs) - args.limit} more (--limit)")
    print(f"\n{len(recs)} matched")


def when(ts) -> str:
    """`2026-08` from an epoch. The index carries the last commit that touched
    the file, falling back to mtime, so this is 'when anyone last cared'."""
    if not ts:
        return "?"
    return datetime.date.fromtimestamp(ts).strftime("%Y-%m")


def stamp(rec) -> int:
    return rec.get("commit") or rec.get("mtime") or 0


def shallow_repos() -> frozenset:
    """Repositories the index recorded as shallow clones.

    Absent from an index built before this was recorded, in which case nothing
    is claimed -- silence is the honest answer to a question that was never
    asked.
    """
    path = rollup_path()
    try:
        return frozenset(json.loads(path.read_text(encoding="utf-8"))
                         .get("shallow") or ())
    except (OSError, ValueError):
        return frozenset()


def dates_unavailable() -> dict[str, str]:
    """`{repo: why it has no commit dates}`, as `index.py` recorded it.

    Separate from `shallow`, and the distinction is the point: a shallow clone
    has real dates that are all the same, while these have no commit dates at
    all because git could not answer. Both make `AGEING` meaningless and they
    are not the same fact, so they do not share a message.
    """
    try:
        return dict(json.loads(rollup_path().read_text(encoding="utf-8"))
                    .get("dates_unavailable") or {})
    except (OSError, ValueError):
        return {}


def date_provenance(recs, shallow=frozenset(), unavailable=None) -> str | None:
    """Why the dates in this set cannot be trusted, or None if they can.

    Dates are the only thing separating a live convention from a fossil, and
    they degrade silently: a codebase outside git, or a shallow clone, still
    produces a confident date for every file. The fallback is mtime -- "when
    this was last written to disk" -- which a copy, an unzip or a checkout
    resets wholesale.

    Shallowness is judged per *repository*, not per matched set. Nine models
    generated in one commit share one date and are perfectly well dated; a
    `--depth 1` clone shares one date across every file it contains, and only
    that means the dates are not history.

    Absent evidence must not read as absent convention, and a date is evidence.
    """
    if not recs:
        return None
    if not any(r.get("commit") for r in recs):
        # Say which of the three it is. "Nothing here is in git" was printed for
        # a repository that is in git and whose history was simply too large to
        # read in the time allowed -- a wrong explanation is worse than a vague
        # one, because it sends the reader to fix the wrong thing.
        blamed = sorted({r["repo"] for r in recs} & set(unavailable or {}))
        if blamed:
            return ("file mtimes, not commits -- " + (unavailable or {})[blamed[0]]
                    + f"\n         ({', '.join(blamed)}). The code is in git;"
                    " its history was not read.\n         AGEING is not"
                    " meaningful here.")
        return ("file mtimes, not commits -- nothing here is in git, or it was"
                "\n         indexed with --no-git. A copy or checkout resets "
                "every one of them\n         to the same instant, so AGEING is "
                "not meaningful.")
    repos = {r["repo"] for r in recs}
    if repos and repos <= shallow:
        return ("a shallow clone -- git says so, and a `--depth 1` checkout has"
                "\n         one commit, so every file carries its date. Real "
                "dates, no history:\n         AGEING cannot fire.")
    return None


_STALE_CACHE = None


def stale_repositories(budget: int = 40000) -> list[str]:
    """Repositories whose source has changed since their shard was built.

    Staleness is the one failure this skill documents at length and never
    detects: "rebuild whenever a source may have changed" is discipline, and
    discipline is exactly what a contract computed from last week's index does
    not benefit from. The answer is wrong in the most expensive way -- it is
    plausible, it is specific, and it describes code that has since moved.

    Exemplars and the target only. A reference changes when `fetch.py` is run
    and not otherwise, so paying to walk twenty-odd of them on every query buys
    nothing.

    Cheap on purpose: the walk stops at the first file newer than the shard,
    because one is proof and the rest is arithmetic. The budget bounds the
    opposite case -- an up-to-date monorepo, where there is no early exit to
    find -- and a walk that runs out says nothing rather than guessing.
    """
    global _STALE_CACHE
    if _STALE_CACHE is not None:
        return _STALE_CACHE
    _STALE_CACHE = []
    seen = 0
    for record in configured_repositories() + [configured_solution()]:
        if not record["exists"]:
            continue
        role = "target" if record.get("is_target") else "exemplar"
        try:
            built = json.loads(index_meta(role, record["name"])
                               .read_text(encoding="utf-8")).get("built")
            built_at = datetime.datetime.strptime(built, "%Y-%m-%d %H:%M:%S")
        except (OSError, ValueError, TypeError):
            continue
        cutoff = built_at.timestamp()
        for path in iter_source_files(record["path"], 2_000_000,
                                      record.get("exclude", ()),
                                      ALL_EXTENSIONS,
                                      include=record.get("include", ())):
            seen += 1
            if seen > budget:
                return _STALE_CACHE
            try:
                if path.stat().st_mtime > cutoff:
                    _STALE_CACHE.append(record["name"])
                    break
            except OSError:
                continue
    return _STALE_CACHE


def warn_if_stale() -> None:
    """One line, before the answer, when the answer may describe old code."""
    schema = index_schema_warning()
    if schema:
        print(f"  SCHEMA: {schema}\n")
    stale = stale_repositories()
    if stale:
        print(f"  STALE: {', '.join(stale)} changed since the index was built."
              " What follows may\n         describe code that has moved."
              "  scripts/index.py --only "
              + ",".join(stale) + "\n")


def cmd_shape(args):
    recs = collect(args, kinds=kinds_for(args))
    if not recs:
        return print("nothing matched -- widen --path, drop --base,"
                     " or try --kind func")
    warn_if_stale()
    total = len(recs)
    per_repo = Counter(r["repo"] for r in recs)
    noun = "functions" if recs[0]["k"] == "func" else "classes"

    counts = Counter()
    repo_counts = defaultdict(Counter)
    newest: dict[str, int] = {}
    for r in recs:
        for f in features(r):
            counts[f] += 1
            repo_counts[f][r["repo"]] += 1
            newest[f] = max(newest.get(f, 0), stamp(r))

    set_newest = max((stamp(r) for r in recs), default=0)
    set_oldest = min((stamp(r) for r in recs if stamp(r)), default=0)
    ageing = 365 * 24 * 3600
    dates_are = date_provenance(recs, shallow_repos(), dates_unavailable())

    print(f"{total} {noun}"
          + (f"  ({', '.join(f'{k} {v}' for k, v in per_repo.items())})"
             if len(per_repo) > 1 else f"  in {next(iter(per_repo))}")
          + f"   touched {when(set_oldest)} .. {when(set_newest)}")
    if dates_are:
        print(f"  dates: {dates_are}")

    # What the layer is built on. A frontend layer's real contract is often the
    # framework rather than anything it declares, and this is the line that says
    # which one to read the rest of the output against.
    tech = Counter()
    for r in recs:
        for t in args._tech.get((r["repo"], r["path"]), ()):
            tech[t] += 1
    if tech:
        print("  built on: " + ", ".join(f"{t} ({pct(n, total)}%)"
                                         for t, n in tech.most_common(6)))
    if noun == "classes" and args._other_kind > total:
        print(f"  note: {args._other_kind} module-level functions also match this"
              f" filter and are not\n        described here. If this layer's unit is"
              f" the function -- components,\n        hooks, handlers -- run --kind"
              f" func.")

    # Every percentage below is computed across all of these repositories at
    # once. DISAGREEMENTS catches the clean splits -- always here, never there
    # -- and says nothing about a 40/60, which is exactly where a blended row
    # describes a form neither codebase uses. That is the failure this skill
    # names for averaging two exemplars, arriving through a glob instead.
    if len(per_repo) > 1:
        print(f"  note: these percentages blend {len(per_repo)} repositories."
              " A row can describe a form"
              f"\n        neither one uses -- read one side with --repo"
              f" <{'|'.join(list(per_repo)[:3])}>."
              "\n        DISAGREEMENTS below catches the clean splits, not a"
              " 40/60.")

    for kind, label in LABELS.items():
        items = [(f.split(":", 1)[1], n) for f, n in counts.items()
                 if f.startswith(kind + ":")]
        if not items:
            continue
        always = sorted([i for i in items if i[1] == total], key=lambda x: x[0])
        usually = sorted([i for i in items if args.usually <= pct(i[1], total) < 100],
                         key=lambda x: -x[1])
        varies = sorted([i for i in items if pct(i[1], total) < args.usually],
                        key=lambda x: -x[1])[: args.limit]
        print(f"\n== {label.upper()} ==")
        if always:
            print("  ALWAYS   " + ", ".join(n for n, _ in always))
        for n, c in usually:
            print(f"  {pct(c, total):>3}%    {n}")
        if varies:
            print("  VARIES   " + ", ".join(
                f"{n} ({pct(c, total)}%, last {when(newest.get(f'{kind}:{n}'))})"
                for n, c in varies))
        if not always and not usually and not varies:
            print("  -")

    # What an attribute IS, not merely that it is there. For a data layer this
    # is the contract: `id` being present everywhere says far less than `id`
    # being `Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)`.
    by_attr: dict[str, list] = defaultdict(list)
    for r in recs:
        for a in r.get("attrs", ()):
            by_attr[a["name"]].append(a)
    detailed = [(n, a) for n, a in by_attr.items()
                if pct(len(a), total) >= args.usually]
    if detailed:
        print(f"\n== ATTRIBUTE DETAIL ==   (present in >= {args.usually}% of {noun})")
        print("   the modal form, and how much of the layer agrees on it\n")
        width = max(len(n) for n, _ in detailed)
        for name, uses in sorted(detailed, key=lambda x: -len(x[1]))[: args.limit]:
            anns = Counter(a["ann"] for a in uses if a["ann"])
            calls = Counter(
                f"{a['call']}({', '.join([*a['args'], *sorted(a['kw'])])})"
                for a in uses if a["call"])
            bits = []
            if anns:
                ann, n = anns.most_common(1)[0]
                bits.append(f"{truncate(ann, 40)} {pct(n, len(uses))}%")
            if calls:
                call, n = calls.most_common(1)[0]
                bits.append(f"{truncate(call, 60)} {pct(n, len(uses))}%")
            print(f"  {name:<{width}}  " + "   ".join(bits))
            if len(anns) > 1 or len(calls) > 1:
                others = [f"{truncate(v, 50)} x{c}" for v, c in
                          [*anns.most_common()[1:], *calls.most_common()[1:]]][:3]
                print(f"  {'':<{width}}  also: " + "; ".join(others))

    stale = sorted(((f, n) for f, n in counts.items()
                    if set_newest and newest.get(f, 0)
                    and set_newest - newest[f] > ageing),
                   key=lambda x: newest[x[0]])
    if stale:
        print("\n== AGEING ==")
        print("   present, but in nothing touched for over a year. A pattern being"
              "\n   abandoned still wins on file count -- do not copy these blindly.\n")
        if dates_are:
            print("   UNRELIABLE HERE: these are modification times, not commits."
                  "\n   A file untouched on disk is not a convention anyone"
                  " abandoned.\n")
        for f, n in stale[: args.limit]:
            kind, item = f.split(":", 1)
            print(f"  {when(newest[f])}  {LABELS.get(kind, kind)}: {item}"
                  f"  ({pct(n, total)}%)")

    if len(per_repo) > 1:
        target_name = configured_solution()["name"]
        involves_target = target_name in per_repo
        print("\n== DISAGREEMENTS ==")
        if involves_target:
            print(f"   {target_name} is the generated target, not another source."
                  "\n   Where it differs it has already decided, and it wins: do not"
                  "\n   reintroduce what it deliberately dropped. Ask only about the"
                  "\n   rows where no target column appears.\n")
        else:
            print("   one repository always does this, another never does."
                  "\n   These are decisions, not averages. Ask before choosing.\n")
        found = False
        for f, by_repo in repo_counts.items():
            hi = [(r, by_repo.get(r, 0), n) for r, n in per_repo.items()
                  if pct(by_repo.get(r, 0), n) >= 90]
            lo = [(r, by_repo.get(r, 0), n) for r, n in per_repo.items()
                  if pct(by_repo.get(r, 0), n) <= 10]
            if hi and lo:
                found = True
                kind, item = f.split(":", 1)
                verdict = ""
                if involves_target:
                    on_target = pct(by_repo.get(target_name, 0),
                                    per_repo[target_name]) >= 90
                    verdict = ("   -> the target keeps it" if on_target
                               else "   -> the target dropped it: leave it dropped")
                print(f"  {LABELS.get(kind, kind)}: {item}{verdict}")
                for r, c, n in hi + lo:
                    mark = " (target)" if r == target_name else ""
                    print(f"      {r + mark:<24} {c}/{n} ({pct(c, n)}%)")
        if not found:
            print("  none -- the repositories agree on every feature of this set.")


def cmd_exemplars(args):
    """The file to copy, and the outlier that shows what is optional.

    Exemplars only, unless asked otherwise. This command's whole output is an
    instruction to *copy the structure of these*, and the generated target is
    not a thing to copy from -- ranking one of its files most typical tells you
    to reproduce your own last pass, which is how a mistake made once becomes
    the convention. The target still outranks the source everywhere it decides
    something; that is `shape`, `conform` and `questions`, none of which are
    telling you what to imitate.
    """
    recs = collect(args, kinds=kinds_for(args))
    # `--repo` is explicit and wins: naming the target means meaning it.
    if recs and not args.repo and not args.include_target:
        roles = indexed_roles()
        only_exemplars = [r for r in recs
                          if roles.get(r["repo"], "exemplar") == "exemplar"]
        held = len(recs) - len(only_exemplars)
        if only_exemplars and held:
            recs = only_exemplars
            print(f"  ({held} definition(s) in the generated target held out --"
                  f" it is not what you copy.\n   --include-target, or --repo,"
                  f" to read it anyway.)\n")
        elif not only_exemplars:
            print("  (no exemplar matched, so this describes the generated"
                  " target itself.\n   Read it as what you already wrote, not"
                  " as a model to copy.)\n")
    if not recs:
        return print("nothing matched -- widen --path, drop --base,"
                     " or try --kind func")
    total = len(recs)
    noun = "functions" if recs[0]["k"] == "func" else "classes"
    counts = Counter()
    for r in recs:
        counts.update(features(r))
    modal = {f for f, n in counts.items() if pct(n, total) >= 50}

    scored = []
    for r in recs:
        f = features(r)
        # reward the shared shape, penalise what nothing else has
        rare = sum(1 for x in f - modal if counts[x] <= max(1, total * 0.1))
        size = len(r.get("attrs", ())) + len(r.get("methods", ())) \
            + len(r.get("params", ()))
        # most modal features wins; then fewest oddities; then the fuller class,
        # because an empty class is a poor thing to copy even when it is typical
        scored.append((-(len(f & modal) - rare), rare, -size, r))
    scored.sort(key=lambda t: t[:3])

    print("MOST TYPICAL -- copy the structure of these\n")
    for negscore, _, _, r in scored[: args.n]:
        print(f"  {r['repo']}/{r['path']}:{r['line']}  {r['name']}"
              f"  [{describe_size(r)}, score {-negscore}]")

    print("\nMOST ATYPICAL -- read one to learn which parts are optional\n")
    for negscore, _, _, r in scored[-args.n:][::-1]:
        f = features(r)
        missing = sorted(x.split(":", 1)[1] for x in modal - f)[:6]
        extra = sorted(x.split(":", 1)[1] for x in f - modal
                       if counts[x] <= max(1, total * 0.1))[:6]
        print(f"  {r['repo']}/{r['path']}:{r['line']}  {r['name']}  [score {-negscore}]")
        if missing:
            print(f"      lacks: {', '.join(missing)}")
        if extra:
            print(f"      alone in having: {', '.join(extra)}")

    print(f"\n{total} {noun} considered. Read the typical one in full before "
          f"generating; read the atypical one to see what is optional.")


def _imports_any(mod, names: set[str]) -> tuple[str, str] | None:
    for imp in mod["imports"]:
        target = imp["mod"] or ""
        # The whole specifier, then its last segment under either separator. A
        # dotted split alone turns `admin/base.html` into `html` and matches
        # every template in the project against nothing anyone asked for.
        if (target in names or imp.get("name") in names or imp.get("as") in names
                or target.split(".")[-1] in names
                or target.rsplit("/", 1)[-1] in names):
            return target, imp.get("name")
    return None


def cmd_calls(args):
    """Every method invoked on a name, against the methods that name defines.

    The index records what a class defines and, separately, what each function
    calls. Crossing the two finds a call to a method that does not exist -- which
    imports cleanly, passes every linter, and raises only when something finally
    runs that line.
    """
    on = args.on
    called: dict[str, list] = defaultdict(list)
    defined: set[str] = set()
    found_class = None
    # Where `on` is *defined*, as a class, a method or a function. Needed for
    # the opposite question to the one below: not "is this call real" but "is
    # this definition reached by anything" -- a mixin nobody includes, a helper
    # nobody imports. Both are silent.
    defined_at: list[str] = []
    # `on` invoked as itself rather than as a receiver. Every language records
    # both, and a mixin, a hook or a plain function is only ever the second
    # kind -- so a check that reads `calls` alone concludes that nothing uses
    # `media-breakpoint-up`, which is included 482 times.
    direct: list[str] = []

    for rec in read_index():
        if rec["k"] == "func" and rec.get("name") == on:
            defined_at.append(f"{rec['repo']}/{rec['path']}:{rec['line']}")
        if rec["k"] == "class":
            for m in rec["methods"]:
                if m.get("name") == on:
                    defined_at.append(f"{rec['repo']}/{rec['path']}:{m['line']}")
            if rec["name"] == on and (not args.defined_in
                                      or fnmatch.fnmatch(rec["path"], args.defined_in)):
                found_class = rec
                defined |= {m["name"] for m in rec["methods"]}
                defined |= {a["name"] for a in rec["attrs"]}
                defined |= {a["name"] for a in rec["assigns"]}
            for m in rec["methods"]:
                for call, line in call_sites(m.get("calls")):
                    root, _, attr = call.partition(".")
                    if root == on and matches(rec, args):
                        called[attr].append(
                            f"{rec['repo']}/{rec['path']}:{line or m['line']}")
                for name, line in call_sites(m.get("invokes")):
                    if name == on and matches(rec, args):
                        direct.append(
                            f"{rec['repo']}/{rec['path']}:{line or m['line']}")
        elif rec["k"] == "func":
            for call, line in call_sites(rec.get("calls")):
                root, _, attr = call.partition(".")
                if root == on and matches(rec, args):
                    called[attr].append(
                        f"{rec['repo']}/{rec['path']}:{line or rec['line']}")
            for name, line in call_sites(rec.get("invokes")):
                if name == on and matches(rec, args):
                    direct.append(
                        f"{rec['repo']}/{rec['path']}:{line or rec['line']}")

    if not called:
        if found_class is not None:
            defined_at.insert(0, f"{found_class['repo']}/{found_class['path']}"
                                 f":{found_class['line']}")
        if direct:
            print(f"{on} is invoked directly, not as a receiver "
                  f"({len(direct)} call sites)\n")
            for site in direct[: args.limit]:
                print(f"  {site}")
            if len(direct) > args.limit:
                print(f"  ... {len(direct) - args.limit} more (--limit)")
            if defined_at:
                print("\n  defined at " + ", ".join(defined_at[:3]))
            return print("\n  Nothing is called *on* it, so there is no member "
                         "list to check against.")
        if not defined_at:
            return print(f"nothing calls anything on {on!r}, and nothing in this"
                         f" index defines it either.")
        print(f"{on} is defined, and nothing in this index calls or invokes it.\n")
        for site in defined_at[: args.limit]:
            print(f"  defined  {site}")
        if len(defined_at) > args.limit:
            print(f"  ... {len(defined_at) - args.limit} more")
        return print(
            "\n  Dead here -- but say so carefully. A public mixin, an exported"
            "\n  helper or a plugin entry point is called from outside this"
            "\n  index, and absence of a caller is not absence of a caller.")

    print(f"{len(called)} distinct methods called on {on}"
          f"  ({sum(len(v) for v in called.values())} call sites)\n")

    if found_class is None:
        print(f"  {on} is not defined in this index, so nothing can be checked "
              f"against it.\n  Calls found:\n")
        # With the sites, not just the counts. This branch is what answers the
        # C# wiring question -- a service registered on `services` or `builder`
        # is the analogue of a class nothing imports -- and "AddScoped 21" is
        # useless for that while "AddScoped, in these two files" is the answer.
        # The sites were being collected and thrown away.
        ranked = sorted(called.items(), key=lambda kv: -len(kv[1]))
        for attr, sites in ranked[: args.limit]:
            print(f"    {attr:<28} {len(sites)}")
            for site in sites[:3]:
                print(f"      {site}")
            if len(sites) > 3:
                print(f"      ... {len(sites) - 3} more")
        if len(ranked) > args.limit:
            print(f"    ... {len(ranked) - args.limit} more method(s) (--limit)")
        return

    print(f"defined at {found_class['repo']}/{found_class['path']}:{found_class['line']}"
          f"  ({len(defined)} members)\n")
    missing = {a: s for a, s in called.items() if a not in defined}
    for attr, sites in sorted(called.items(), key=lambda kv: -len(kv[1])):
        if attr not in missing:
            print(f"  ok       {attr:<28} {len(sites)} call site(s)")
    if missing and language_of(found_class) == "csharp":
        print("\n== NOT RESOLVED ==")
        print("   Advisory only. C# is read syntax-only, so an instance call is"
              "\n   attributed to the variable it was made on, not to that variable's"
              "\n   type -- and an extension method is declared outside the type"
              "\n   entirely. Absence here is not evidence of a missing member.\n")
        for attr, sites in sorted(missing.items(), key=lambda kv: -len(kv[1])):
            print(f"  unresolved  {attr:<26} {len(sites)} call site(s)")
    elif missing:
        print("\n== NOT DEFINED ==")
        print("   called, but no such member. These raise when the line runs, and"
              "\n   never before -- the file imports and every linter passes.\n")
        for attr, sites in sorted(missing.items(), key=lambda kv: -len(kv[1])):
            print(f"  MISSING  {attr:<28} {len(sites)} call site(s)")
            for site in sites[: args.limit]:
                print(f"           {site}")
    else:
        print(f"\nevery method called on {on} exists.")


# How much a decision of each kind costs to get wrong. Not how interesting it
# is -- how expensive the reversal is. A wrong table name is a rename; a wrong
# key strategy propagates into every foreign key, every fixture and every test,
# and is discovered late.
DECISION_WEIGHT = {
    "base": 1.0, "attrdetail": 1.0, "assign": 0.8, "attrcall": 0.7,
    "attr": 0.6, "classdec": 0.5, "methoddec": 0.5, "method": 0.4,
    "call": 0.25, "invoke": 0.25, "param": 0.2, "returns": 0.2,
    "modifier": 0.1, "funcdec": 0.4,
}

WHY = {
    "base": "the base class decides what every member inherits",
    "attrdetail": "the form of a universal attribute -- it propagates into "
                  "everything that references it",
    "assign": "a class-level declaration: structural, and read by the framework",
    "attrcall": "how the attribute is constructed, not merely that it exists",
    "attr": "whether this field exists at all",
    "method": "whether members of this layer carry this method",
}


def slugify(text: str) -> str:
    out = "".join(c.lower() if c.isalnum() else "-" for c in text)
    return "-".join(p for p in out.split("-") if p)[:60]


# Whether a member *has* a field or a method usually tracks the domain, not a
# decision: a model carries `instrument_id` because that entity references an
# instrument. `generating.md` states it -- the percentage there is describing
# the domain, not a disagreement about style. So presence is scored differently
# from form, or the ranking fills up with domain nouns and the feature dies of
# bad questions.
PRESENCE_KINDS = {"attr", "method", "call", "invoke", "param", "returns"}


def split_score(n: int, total: int) -> float:
    """How genuinely forked a *structural* feature is.

    A base class or a constructor on half the members is a real fork the
    request has to land on. One on 5% is a single odd file; one on 95% is a
    default with an exception. Neither deserves a person's attention.
    """
    if not total:
        return 0.0
    return 1.0 - abs(pct(n, total) - 50) / 50


def majority_score(n: int, total: int) -> float:
    """How much a *presence* question is a convention rather than the domain.

    `created_at` on eight models of nine is a convention with three exceptions,
    and worth one question. `instrument_id` on one of three is what that entity
    happens to be. So this peaks where most-but-not-all have it, and is zero
    for a minority.
    """
    if not total:
        return 0.0
    p = pct(n, total)
    if p < 50 or p >= 100:
        return 0.0
    return max(0.0, 1.0 - abs(p - 80) / 30)


def target_settled(args, ranked) -> dict[str, str]:
    """Candidates the generated code has already answered, and how.

    "The target outranks the source" is stated all through this skill, and it
    applies to questions before it applies to anything else: a choice visible in
    code that already exists is not a question, it is a fact to read back. The
    target is unanimous or it is not -- a layer where half the members do it is
    still a live decision.

    Needs `--target-path`, because the target's layout is not the source's:
    atlas keeps models under `database/<domain>/models/`, a single-domain app
    flattens them, and no glob matches both.
    """
    if not getattr(args, "target_path", None):
        return {}
    repo = getattr(args, "target_repo", None) or configured_solution()["name"]
    target = [r for r in read_index()
              if r["k"] in kinds_for(args) and r["repo"] == repo
              and fnmatch.fnmatch(r["path"], args.target_path)]
    if not target:
        return {}
    n = len(target)

    counts = Counter()
    for r in target:
        counts.update(features(r))
    forms = defaultdict(Counter)
    for r in target:
        for a in r.get("attrs", ()):
            if a.get("ann"):
                forms[a["name"]][a["ann"]] += 1

    out = {}
    for _score, ident, kind, _title, _note, item in ranked:
        if kind == "attrdetail":
            shapes = forms.get(item)
            if shapes and len(shapes) == 1:
                out[ident] = f"{repo} uses {next(iter(shapes))} throughout"
            continue
        seen = counts.get(f"{kind}:{item}", 0)
        if seen == n:
            out[ident] = f"{repo} keeps it, {n}/{n}"
        elif seen == 0:
            out[ident] = f"{repo} dropped it, 0/{n} -- leave it dropped"
    return out


def cmd_questions(args):
    """The decisions this layer would force, ranked by what they cost to get wrong.

    `shape` reports everything that varies. Most of it does not deserve a
    question: it is one odd file, or a default with a single exception. This
    ranks the candidates so that a budget of three questions spends itself on
    the three that matter, and everything below the line is decided and stated
    rather than asked.

    Read-only. It records nothing and asks nothing -- `decide` does that.
    """
    recs = collect(args, kinds=kinds_for(args))
    if not recs:
        # Parseable even when it is empty -- see `nothing_matched` in
        # `cmd_conform` for why prose on this stream is the wrong answer.
        if getattr(args, "json", False):
            return print(json.dumps({
                "schema": INDEX_SCHEMA, "command": "questions",
                "kind": kinds_for(args)[0], "error": "nothing matched",
                "members": 0, "candidates": 0, "stale": stale_repositories(),
                "asked": [], "settled_by_code": [], "below_the_line": 0,
            }, indent=2))
        return print("nothing matched -- widen --path, or try --kind func")
    # Not under `--json`: a warning printed above the payload is text on a
    # stream a machine is parsing, and it would break every consumer exactly
    # when the index is stale -- the moment the consumer most needs an answer.
    # The same fact travels inside the document, as `stale`.
    if not getattr(args, "json", False):
        warn_if_stale()
    total = len(recs)
    per_repo = Counter(r["repo"] for r in recs)
    target = configured_solution()["name"]

    counts, repo_counts, newest = Counter(), defaultdict(Counter), {}
    for r in recs:
        for f in features(r):
            counts[f] += 1
            repo_counts[f][r["repo"]] += 1
            newest[f] = max(newest.get(f, 0), stamp(r))
    set_newest = max((stamp(r) for r in recs), default=0)
    ageing = 365 * 24 * 3600

    candidates = []

    # 1. A feature some members have and others do not.
    for f, n in counts.items():
        kind, item = f.split(":", 1)
        weight = DECISION_WEIGHT.get(kind, 0.3)
        shape_of = majority_score if kind in PRESENCE_KINDS else split_score
        score = weight * shape_of(n, total)
        note = f"{n} of {total} have it"
        if set_newest and newest.get(f) and set_newest - newest[f] > ageing:
            # The count says follow it; the clock says it was abandoned. That
            # disagreement is always worth a person's attention.
            score += 0.35
            note += f", and nothing since {when(newest[f])}"
        if score > 0:
            candidates.append((score, f"{kind}-{slugify(item)}", kind,
                               f"{LABELS.get(kind, kind)}: {item}", note, item))

    # 2. An attribute everything has, in more than one form. This is the
    #    primary-key question, and it never shows up as a VARIES row because
    #    the *name* is universal -- only the form differs.
    by_attr = defaultdict(list)
    for r in recs:
        for a in r.get("attrs", ()):
            by_attr[a["name"]].append(a)
    for name, uses in by_attr.items():
        if pct(len(uses), total) < args.usually:
            continue
        forms = Counter(a["ann"] for a in uses if a["ann"])
        if len(forms) < 2:
            continue
        (top, n_top), (second, n_second) = forms.most_common(2)
        score = DECISION_WEIGHT["attrdetail"] * split_score(n_top, len(uses))
        candidates.append((
            score, f"attrdetail-{slugify(name)}", "attrdetail",
            f"attribute detail: {name}",
            f"{truncate(top, 32)} x{n_top} vs {truncate(second, 32)} x{n_second}", name))

    # 3. What one repository always does and another never does. Never averaged,
    #    and settled already when the target is one of the sides.
    for f, by_repo in repo_counts.items():
        hi = [r for r, n in per_repo.items() if pct(by_repo.get(r, 0), n) >= 90]
        lo = [r for r, n in per_repo.items() if pct(by_repo.get(r, 0), n) <= 10]
        if not (hi and lo):
            continue
        kind, item = f.split(":", 1)
        if target in hi or target in lo:
            continue                      # the target has decided; it wins
        candidates.append((
            DECISION_WEIGHT.get(kind, 0.3) + 0.5, f"{kind}-{slugify(item)}",
            kind, f"DISAGREEMENT -- {LABELS.get(kind, kind)}: {item}",
            f"{', '.join(hi)} always; {', '.join(lo)} never", item))

    best: dict[str, tuple] = {}
    for cand in candidates:
        if cand[0] > best.get(cand[1], (0,))[0]:
            best[cand[1]] = cand
    ranked = sorted(best.values(), key=lambda c: -c[0])

    # Answered by the code already. The target is indexed and it outranks the
    # source, so if the generated layer is unanimous about something there is
    # nothing to ask -- reading it back is cheaper than a question, and asking
    # anyway invites the user to re-decide what they already decided.
    by_code = target_settled(args, ranked)
    asked = [c for c in ranked if c[1] not in by_code][: args.limit]

    if getattr(args, "json", False):
        # The decisions, with the numbers that justify each one. `--limit`
        # still applies: what is below the line is decided and stated rather
        # than asked, and a consumer that wants all of it can raise the limit.
        print(json.dumps({
            "schema": INDEX_SCHEMA,
            "command": "questions",
            "kind": recs[0]["k"],
            "members": total,
            "candidates": len(ranked),
            "stale": stale_repositories(),
            "asked": [{"id": ident, "score": round(score, 2), "kind": kind,
                       "title": title, "evidence": note,
                       "why": WHY.get(kind)}
                      for score, ident, kind, title, note, _item in asked],
            # Not questions. Facts read back out of code that already exists,
            # which is what "the target outranks the source" means here.
            "settled_by_code": [{"id": ident, "how": how}
                                for ident, how in by_code.items()],
            "below_the_line": max(0, len(ranked) - len(by_code) - len(asked)),
        }, indent=2))
        return

    print(f"{total} {'functions' if recs[0]['k'] == 'func' else 'classes'} "
          f"-> {len(ranked)} candidate decisions, showing {len(asked)}\n")
    if len(ranked) > total * 2:
        print(f"  NOTE: {len(ranked)} candidates for {total} members means this"
              f" is not one layer.\n  These questions average several families"
              f" together and will not be the\n  right ones. Narrow with --base,"
              f" --decorator or a deeper --path first.\n")
    if by_code:
        print(f"  {len(by_code)} answered by the code already -- the target "
              f"outranks the source,\n  so these are read back, not asked:")
        for ident, how in list(by_code.items())[:6]:
            print(f"      {ident:<28} {how}")
        print()

    if not asked:
        if by_code:
            return print("  nothing left to ask: the generated code already "
                         "answers every candidate.")
        return print("  nothing worth asking about: everything that varies here"
                     "\n  is one odd file, a default with one exception, or the"
                     " domain itself.")

    for score, ident, kind, title, note, _item in asked:
        print(f"  {score:.2f}  {ident}")
        print(f"        {title}")
        print(f"        {note}")
        if WHY.get(kind):
            print(f"        why it matters: {WHY[kind]}")
        print()

    below = len(ranked) - len(by_code) - len(asked)
    if below > 0:
        print(f"  {below} more below the line. Those are not asked -- they are "
              f"decided\n  and stated in the report.")


def cmd_conform(args):
    """Does the generated layer still satisfy the contract that produced it?

    `shape` says what is ALWAYS true of the source. Nothing else checks that the
    output kept it. This does: same measure, both sides, difference reported.

    `--kind func` is not a refinement, it is the difference between this command
    working and not existing. A React component, a hook and a route handler are
    functions, and while this read classes only, every function layer this skill
    can generate had **no rung-8 check at all** -- the one step that asks whether
    the output still keeps the contract simply had nothing to say about half of
    what the skill builds.
    """
    kinds = kinds_for(args)
    noun = "functions" if kinds == ("func",) else "classes"
    source, target, tech = [], [], {}
    # Counted so a filter that matched the *other* kind can say so. Silence
    # there reads as "the layer is empty", which for a directory of forty
    # components is the wrong conclusion drawn confidently.
    other_source = other_target = 0
    for r in read_index():
        if r["k"] == "module":
            found = technologies_of(r.get("imports"))
            if found:
                tech.setdefault((r["repo"], r["path"]), set()).update(found)
            continue
        markup = markup_technologies_of(r)
        if markup:
            tech.setdefault((r["repo"], r["path"]), set()).update(markup)
        if r["k"] not in ("class", "func"):
            continue
        is_source = (fnmatch.fnmatch(r["path"], args.path)
                     and (not args.repo or r["repo"] == args.repo))
        is_target = (fnmatch.fnmatch(r["path"], args.target_path)
                     and (not args.target_repo or r["repo"] == args.target_repo))
        if r["k"] in kinds:
            if is_source:
                source.append(r)
            if is_target:
                target.append(r)
        else:
            other_source += 1 if is_source else 0
            other_target += 1 if is_target else 0

    want = getattr(args, "tech", None)
    if want:
        source = [r for r in source if want in tech.get((r["repo"], r["path"]), ())]
        target = [r for r in target if want in tech.get((r["repo"], r["path"]), ())]

    def swap(n: int) -> str:
        if not n:
            return ""
        if kinds == ("func",):
            return (f"\n  The filter matched {n} class(es). This layer's unit"
                    " looks like the class -- run --kind class.")
        return (f"\n  The filter matched {n} module-level function(s). If this"
                " layer's unit is the\n  function -- components, hooks,"
                " handlers are -- run --kind func.")

    def nothing_matched(message: str) -> None:
        """A filter that matched nothing is a result, and under `--json` it has
        to be a *parseable* one.

        A mistyped path would otherwise print prose to a stream a machine is
        reading -- and the failure mode is worse than a crash: an empty
        `dropped` list reads as "nothing was broken". `contract_empty` is true
        here for the same reason it exists at all, so the gate in `MANUAL.md`
        treats a typo as inconclusive rather than as a pass.
        """
        if getattr(args, "json", False):
            print(json.dumps({
                "schema": INDEX_SCHEMA, "command": "conform", "kind": kinds[0],
                "error": message,
                "source": {"repo": args.repo, "path": args.path,
                           "count": len(source)},
                "target": {"repo": args.target_repo, "path": args.target_path,
                           "count": len(target)},
                "contract_empty": True, "stale": stale_repositories(),
                "kept": [], "dropped": [], "added": [],
            }, indent=2))
        else:
            print(message)

    if not source:
        return nothing_matched(f"no source {noun} matched --path/--repo"
                               + swap(other_source))
    if not target:
        return nothing_matched(f"no target {noun} matched"
                               " --target-path/--target-repo"
                               + swap(other_target))

    source_always = set.intersection(*(features(r) for r in source))
    target_always = set.intersection(*(features(r) for r in target))

    kept = sorted(source_always & target_always)
    dropped = sorted(source_always - target_always)
    added = sorted(target_always - source_always)

    if getattr(args, "json", False):
        # For a gate, not for a person. `conform` is the one command whose
        # answer is a pass or a fail about code that already exists, which
        # makes it the one worth running again automatically -- rung 4 of the
        # skill's own ladder, applied to the skill's own output.
        #
        # `contract_empty` is in here rather than left to be inferred from an
        # empty `dropped`, because those two look identical to a caller and
        # mean opposite things: nothing was broken, versus nothing was checked.
        print(json.dumps({
            "schema": INDEX_SCHEMA,
            "command": "conform",
            "kind": kinds[0],
            "source": {"repo": args.repo, "path": args.path, "count": len(source)},
            "target": {"repo": args.target_repo, "path": args.target_path,
                       "count": len(target)},
            "contract_empty": not source_always,
            "stale": stale_repositories(),
            "kept": [f.split(":", 1)[1] for f in kept],
            "dropped": [{"kind": f.split(":", 1)[0], "item": f.split(":", 1)[1],
                         "absent_from": [r["name"] for r in target
                                         if f not in features(r)]}
                        for f in dropped],
            "added": [f.split(":", 1)[1] for f in added],
        }, indent=2))
        return

    warn_if_stale()
    print(f"source {len(source)} {noun}  ->  target {len(target)} {noun}\n")

    # "Always true" of one member is just "true of that member", and an
    # intersection over two is barely stronger. Both sides are worth saying out
    # loud, because the arithmetic is silent about it: a one-member target makes
    # every one of its features ADDED, and the reader sees seventy rows that
    # mean nothing.
    singular = "function" if noun == "functions" else "class"
    thin = [f"{side} is {n} {singular if n == 1 else noun}"
            for side, n in (("the source", len(source)), ("the target", len(target)))
            if n < 3]
    if thin:
        print(f"  note: {', and '.join(thin)}. What is 'always true' of one or"
              " two members is\n        barely a contract -- read the rows"
              " below as description, not as a rule.\n")

    # An empty intersection is not a pass. The DROPPED section below would say
    # "the target keeps everything the source contracts", which is true and
    # worthless when the source contracts nothing -- and it reads exactly like
    # a clean result. This is the one outcome of this command that could be
    # mistaken for proof of something.
    if not source_always:
        print("  NOTHING TO CHECK -- the source has no feature common to all"
              f" {len(source)} {noun},\n  so there is no contract here to keep"
              " or drop. That is a fact about the\n  filter, not about the"
              " output: narrow it with --base, --tech or a deeper\n  --path"
              " until the source is one family, then run this again.\n")

    print(f"== KEPT ({len(kept)}) ==")
    print("  " + (", ".join(f.split(':', 1)[1] for f in kept) if kept else "-"))

    print(f"\n== DROPPED ({len(dropped)}) ==")
    if dropped:
        print("   always true of the source, not always true of the target. Each is"
              "\n   either a deliberate departure you can name, or a mistake.\n")
        for f in dropped:
            kind, item = f.split(":", 1)
            missing_in = [r["name"] for r in target if f not in features(r)]
            print(f"  {LABELS.get(kind, kind)}: {item}")
            print(f"      absent from {len(missing_in)}/{len(target)}: "
                  f"{truncate(', '.join(missing_in[:6]), 70)}")
    elif source_always:
        print("  none -- the target keeps everything the source contracts.")
    else:
        print("  none, but only because the source contracts nothing -- see"
              " above.")

    if added:
        print(f"\n== ADDED ({len(added)}) ==")
        print("   universal in the target and not in the source. Usually the domain,"
              "\n   sometimes a convention worth carrying back.\n")
        print("  " + ", ".join(f.split(':', 1)[1] for f in added))


def cmd_imports(args):
    sym = args.symbol_arg
    modules, subclasses = [], []
    for rec in read_index():
        if not matches(rec, args):
            continue
        if rec["k"] == "module":
            modules.append(rec)
        elif rec["k"] == "class" and any(symbol_matches(b, sym)
                                         for b in rec["bases"]):
            subclasses.append((rec["repo"], rec["path"], rec["name"]))

    # The frontier carries the repository each name came from, and `None` means
    # "any" -- which only the symbol the user typed is entitled to be.
    #
    # Every hop after the first is a *package directory name*: `models`,
    # `utils`, `controllers`. Matched across the whole index those hit every
    # codebase that happens to own a directory of the same name, and the
    # command then reports a registration chain running through repositories
    # that have never heard of each other. A wiring answer is only useful if it
    # names files you can actually edit, so a hop stays where it was found.
    frontier: set[tuple[str | None, str]] = {(None, sym)}
    seen: set[tuple[str | None, str]] = {(None, sym)}
    level = 0
    while frontier:
        hits = []
        for m in modules:
            wanted = {name for repo, name in frontier
                      if repo is None or repo == m["repo"]}
            if not wanted:
                continue
            found = _imports_any(m, wanted)
            if found:
                hits.append((m, found))
        label = ("IMPORTED BY" if level == 0
                 else "WHICH IS REACHED THROUGH ("
                      + " / ".join(sorted({n for _, n in frontier})) + ")")
        print(f"{label} ({len(hits)})"
              + ("   -- these are the files that must change for a new one "
                 "to take effect" if level == 0 else "") + "\n")
        for m, (mod, name) in hits[: args.limit]:
            stmt = f"from {mod} import {name}" if name else f"import {mod}"
            print(f"  {m['repo']}/{m['path']:<62} {stmt}")
        if len(hits) > args.limit:
            print(f"  ... {len(hits) - args.limit} more (--limit)")

        level += 1
        if not args.chain or level >= args.depth:
            break
        # A package __init__ that re-exports is not the end of the chain: the
        # thing that makes a definition take effect may be several hops up,
        # and each hop is another file that has to be edited.
        nxt = {(m["repo"], m["dir"].rsplit("/", 1)[-1]) for m, _ in hits
               if barrel_for(m) and m["path"].endswith(barrel_for(m)) and m["dir"]}
        frontier = {e for e in nxt - seen if e[1] != sym}
        seen |= frontier
        if not frontier:
            break
        print()

    if subclasses:
        print(f"\nSUBCLASSED BY ({len(subclasses)})\n")
        for repo, path, name in subclasses[: args.limit]:
            print(f"  {repo}/{path}  {name}")
        if len(subclasses) > args.limit:
            print(f"  ... {len(subclasses) - args.limit} more (--limit)")

    # For a template layer this *is* the registration chain. A page names its
    # parent directly -- there is no barrel file to re-export it -- so the hops
    # that matter go downward through inheritance: change a base template and
    # every level below it renders differently, and none of them errors.
    if args.chain and subclasses:
        classes = [r for r in read_index() if r["k"] == "class"]
        # Repository-scoped for the same reason as the barrel chain above. Two
        # codebases both holding a `base.html` is ordinary, and a chain that
        # crossed between them would report pages that no edit here can break.
        frontier = {(repo, name) for repo, _, name in subclasses}
        seen_names, level = set(frontier) | {(r, sym) for r, _, _ in subclasses}, 1
        while frontier and level < args.depth:
            nxt = {(r["repo"], r["name"]) for r in classes
                   if any((r["repo"], head(b)) in frontier for b in r["bases"])
                   and (r["repo"], r["name"]) not in seen_names}
            if not nxt:
                break
            print(f"\nWHICH IS EXTENDED BY ({len(nxt)})   -- level {level + 1}\n")
            for repo, n in sorted(nxt)[: args.limit]:
                print(f"  {repo}/{n}")
            if len(nxt) > args.limit:
                print(f"  ... {len(nxt) - args.limit} more (--limit)")
            seen_names |= nxt
            frontier = nxt
            level += 1


def cmd_deps(args):
    """What each codebase declares it depends on, and what it runs.

    An import proves a package is used somewhere; a manifest says what the
    project committed to, which is not the same fact and is the one a generated
    layer has to respect. Code that imports a package nobody declared installs
    nothing and fails at run time with a resolution error that reads as a path
    problem.

    `--on NAME` answers the other direction -- who declares this, at what
    version -- which is how you find out whether a dependency an option implies
    is already paid for.

    Exemplars and the target only, unless `--references` widens it. "Already
    paid for" is a question about who pays: a package that only a reference
    declares is a new commitment all the same, and counting it would answer
    yes on the strength of somebody else's manifest.
    """
    everything = [r for r in read_index(include_references=args.references)
                  if r["k"] == "manifest"]
    records = [r for r in everything
               if (not args.repo or r["repo"] == args.repo)
               and (not args.path or fnmatch.fnmatch(r["path"], args.path))]
    if not records:
        # Two different answers, and conflating them is how a real finding gets
        # reported as a tooling problem. A codebase that declares nothing is a
        # fact worth knowing -- its dependencies live only in whatever
        # environment happens to be active, and nothing can reproduce it.
        if not everything:
            scope = ("anywhere in this index" if args.references
                     else "in the exemplars or the target (--references widens)")
            return print(f"no manifests {scope}."
                         "\nIf the index was built before manifests were read,"
                         " rebuild it.")
        where = args.repo or args.path or "that filter"
        if (args.repo and not args.references
                and indexed_roles().get(args.repo) == "reference"):
            return print(f"{args.repo} is a reference codebase, and references"
                         " are not read here by default.\nPass --references to"
                         " see what it declares.")
        return print(f"no manifest under {where} -- it declares no dependencies."
                     f"\n{len(everything)} manifest(s) elsewhere in this index, so"
                     f" the index is not the problem."
                     f"\nWhatever it imports is satisfied by the ambient"
                     f" environment and by nothing it carries.")

    roles = indexed_roles()
    if args.on:
        want = args.on.lower()
        print(f"declares {args.on!r}\n")
        found = False
        for r in sorted(records, key=lambda x: (x["repo"], x["path"])):
            for section in ("deps", "dev_deps"):
                for name, version in (r.get(section) or {}).items():
                    if name.lower() == want:
                        role = roles.get(r["repo"], "exemplar")
                        tag = "dev" if section == "dev_deps" else "   "
                        print(f"  {role:<10} {r['repo']}/{r['path']:<44} "
                              f"{tag} {version}")
                        found = True
        if not found:
            print(f"  nothing declares it -- including it means adding it")
            if not args.references:
                print("  (references not searched -- a reference's manifest is"
                      " not the target's commitment; --references to look)")
        return

    for r in sorted(records, key=lambda x: (roles.get(x["repo"], ""), x["repo"])):
        deps, dev = r.get("deps") or {}, r.get("dev_deps") or {}
        print(f"{r['repo']}/{r['path']}   [{r.get('ecosystem', '?')}]"
              f"   {len(deps)} deps, {len(dev)} dev")
        for name, version in sorted(deps.items())[: args.limit]:
            print(f"    {name:<36} {version}")
        if len(deps) > args.limit:
            print(f"    ... {len(deps) - args.limit} more (--limit)")
        if r.get("scripts"):
            print("  SCRIPTS")
            for name, body in sorted(r["scripts"].items()):
                print(f"    {name:<16} {truncate(body, 70)}")
        print()


def _mentions(rec, tokens: set[str]) -> set[str]:
    """Which of `tokens` this record mentions, by import, call, base or decorator.

    Matching is the same shape `_imports_any` uses -- whole specifier, or last
    segment under either separator -- because a dotted split alone turns
    `admin/base.html` into `html`.
    """
    hit = set()
    for imp in rec.get("imports") or ():
        target = imp.get("mod") or ""
        for cand in (target, imp.get("name"), imp.get("as"),
                     target.split(".")[-1], target.rsplit("/", 1)[-1]):
            if cand in tokens:
                hit.add(cand)
        # A subpath of a package is a use of that package. Matching only the
        # whole specifier and its last segment missed `@mui/material/Box` for
        # `@mui/material` -- 711 modules in MUI's own demo gallery, reported as
        # 6 -- and `sqlalchemy.orm` for `sqlalchemy`. Deep imports are the norm
        # in JavaScript and common in Python, so this was not an edge case.
        #
        # The separator is required rather than a bare prefix: without it
        # `react` would claim `react-dom` and `react-router`, which are
        # different decisions and sometimes the competing options in the same
        # question.
        for tok in tokens:
            if target.startswith(tok + "/") or target.startswith(tok + "."):
                hit.add(tok)
    for name in call_names(rec.get("calls")) + call_names(rec.get("invokes")):
        bare = head(name)
        if bare in tokens:
            hit.add(bare)
        if bare.split(".")[0] in tokens:
            hit.add(bare.split(".")[0])
    for b in rec.get("bases") or ():
        if head(b) in tokens:
            hit.add(head(b))
    for d in rec.get("decorators") or ():
        if head(d) in tokens:
            hit.add(head(d))
    return hit


def cmd_practice(args):
    """How the wider world resolves a choice, against how the exemplar resolves it.

    This is the only command that reads the reference corpus unasked -- `deps`
    joins it only when passed `--references`. Everything else computes a
    contract, and a contract must come from the code being copied -- nine
    reference repositories outnumber one exemplar, so letting them in replaces
    the convention being reproduced with an average of the internet.

    What it answers is a different question: not "what is the convention here"
    but "is this convention still how anyone does it". Percentages are head to
    head -- the denominator is modules mentioning *either* option, not modules
    in the repository -- because the useful comparison is between the two
    choices, not between one choice and all the code that had no occasion to
    make it.

    Evidence, not a verdict. A corpus can be unanimous and still wrong for a
    particular target, and the exemplar disagreeing with it is a question worth
    raising rather than an error to correct.
    """
    tokens = [args.on] + list(args.versus or ())
    token_set = set(tokens)
    roles = indexed_roles()
    # Two different ways a date stops being history, marked the same in the
    # table because the reader's next move is identical -- do not weigh this
    # row's dates -- and separated in the footnote because the repairs differ.
    shallow = shallow_repos()
    undated = dates_unavailable()
    unreliable = set(shallow) | set(undated)

    # (repo, token) -> module paths; and the most recent touch per pair.
    users: dict[tuple[str, str], set[str]] = defaultdict(set)
    latest: dict[tuple[str, str], int] = defaultdict(int)
    any_use: dict[str, set[str]] = defaultdict(set)
    lang_modules: dict[str, int] = defaultdict(int)

    for rec in read_index(include_references=True):
        if args.lang and language_of(rec) != args.lang:
            continue
        if args.path and not fnmatch.fnmatch(rec.get("path", ""), args.path):
            continue
        repo, path = rec.get("repo"), rec.get("path", "")
        if rec["k"] == "module":
            lang_modules[repo] += 1
        for tok in _mentions(rec, token_set):
            users[(repo, tok)].add(path)
            any_use[repo].add(path)
            latest[(repo, tok)] = max(latest[(repo, tok)], stamp(rec))

    if not any_use:
        return print(f"nothing in the index mentions {' or '.join(tokens)}"
                     + (f" in {args.lang}" if args.lang else "")
                     + "\nCheck the spelling, or widen with --lang/--path.")

    print("practice: " + "  vs  ".join(tokens)
          + (f"          [{args.lang}]" if args.lang else ""))
    print("  modules mentioning each option, as a share of those mentioning any."
          "\n  A module using both counts under both, so the row can exceed 100%."
          "\n  Evidence, not a verdict.\n")

    width = max(max(len(r) for r in any_use), 12) + 1
    cell = 20
    print(f"    {'':<{width}}" + "".join(f"  {truncate(t, cell - 2):<{cell}}"
                                         for t in tokens) + "  any")
    order = {"exemplar": 0, "target": 1, "reference": 2}
    grouped: dict[str, list] = defaultdict(list)
    for repo in any_use:
        grouped[roles.get(repo, "exemplar")].append(repo)

    for role in sorted(grouped, key=lambda r: order.get(r, 9)):
        print(f"  {role.upper()}")
        for repo in sorted(grouped[role], key=lambda r: -len(any_use[r])):
            total = len(any_use[repo])
            cells = []
            for tok in tokens:
                n = len(users[(repo, tok)])
                cells.append(f"{n:>4} {str(pct(n, total)) + '%':>5} {when(latest[(repo, tok)]):>8}"
                             if n else f"{'--':>4} {'':>5} {'':>8}")
            # A shallow clone has one commit, so every date in its row is the
            # date it was fetched. Marked rather than hidden: the counts are
            # still evidence, and only the dates stop being history.
            label = repo + (" *" if repo in unreliable else "")
            print(f"    {label:<{width}}" + "".join(f"  {c:<{cell}}" for c in cells)
                  + f"  {total:>4}"
                  + (f"  of {lang_modules[repo]} indexed" if lang_modules.get(repo) else ""))
        print()

    # The footnote is not decoration. `MANUAL.md` tells the reader to weigh the
    # dates and not only the counts, and for a shallow repository that advice
    # is actively wrong -- the date is one clone timestamp wearing the costume
    # of a last-touched signal.
    marked_shallow = sorted(r for r in any_use if r in shallow)
    marked_undated = sorted(r for r in any_use if r in undated
                            and r not in shallow)
    if marked_shallow or marked_undated:
        print("  * dates below are not history. The counts stand; the dates"
              " cannot say whether a\n    convention is current, and AGEING"
              " cannot fire against them.")
        if marked_shallow:
            print(f"      shallow clone -- {', '.join(marked_shallow)}:"
                  " every file shares the date it was"
                  "\n        fetched. `scripts/fetch.py --deepen`, then rebuild.")
        if marked_undated:
            print(f"      no commit dates -- {', '.join(marked_undated)}:"
                  " these are file modification times."
                  "\n        The code is in git; its history was not read."
                  " See `meta` for why.")
        print()

    # The two readings worth stating, because both are easy to miss in a table.
    refs = [r for r in any_use if roles.get(r) == "reference"]
    exemplars = [r for r in any_use if roles.get(r, "exemplar") == "exemplar"]
    def leader(scores: dict[str, int]) -> tuple[str | None, str]:
        """The winner and how to say it -- `None` when nothing won.

        `max()` on a tie returns whichever key it saw first, which here is
        whatever the user typed as `--on`. That reads as a finding and is an
        artefact of argument order: measured on the real corpus, two reference
        codebases at one apiece were reported as favouring the first token.
        A tie is a result, and the honest way to report it is as a tie.
        """
        best = max(scores.values(), default=0)
        if not best:
            return None, "no evidence"
        winners = [t for t in scores if scores[t] == best]
        if len(winners) > 1:
            return None, "tied -- " + ", ".join(winners)
        return winners[0], winners[0]

    if refs and len(tokens) > 1:
        corpus = {tok: sum(len(users[(r, tok)]) for r in refs) for tok in tokens}
        favoured, favoured_label = leader(corpus)
        print(f"  corpus favours   {favoured_label}"
              f"   ({', '.join(f'{t} {corpus[t]}' for t in tokens)}"
              f" across {len(refs)} reference codebase(s))")

        # The same question, counted by codebase instead of by module. One
        # opinionated repository with a large example farm owns a module count
        # outright -- `references/corpus.md` records the case where two React
        # repositories said `useQuery` and four said `useState`. Telling the
        # reader to remember that is weaker than measuring it, so both verdicts
        # are printed and their disagreement is the finding.
        votes = Counter()
        for r in refs:
            mine = {tok: len(users[(r, tok)]) for tok in tokens}
            if any(mine.values()):
                votes[max(mine, key=mine.get)] += 1
        if votes:
            by_repo, by_repo_label = leader(votes)
            print(f"  by codebase      {by_repo_label}"
                  f"   ({', '.join(f'{t} {votes[t]}' for t in tokens if votes[t])}"
                  f" of {len(refs)} codebase(s))")
            if by_repo is None or favoured is None or by_repo != favoured:
                print(f"  SPLIT -- by module the corpus favours"
                      f" {favoured_label}, by codebase {by_repo_label}."
                      "\n    One repository's size is carrying the module"
                      " count. The corpus does not settle"
                      "\n    this; say so rather than quoting either verdict.")
            elif max(votes.values()) < len(refs):
                print(f"    not unanimous: {len(refs) - max(votes.values())}"
                      f" of {len(refs)} codebase(s) go the other way")

        for ex in exemplars:
            mine = {tok: len(users[(ex, tok)]) for tok in tokens}
            if not any(mine.values()):
                continue
            theirs, theirs_label = leader(mine)
            if theirs is None:
                verdict = f"uses both about equally ({theirs_label})"
            elif favoured is None:
                verdict = (f"uses {theirs} -- the corpus is tied, so there is"
                           " nothing here to agree or disagree with")
            elif theirs == favoured:
                verdict = "agrees"
            else:
                verdict = f"DISAGREES -- it uses {theirs}"
            print(f"  {ex} {verdict}")

    stale = [(tok, latest[(ex, tok)]) for ex in exemplars for tok in tokens
             if users.get((ex, tok)) and latest[(ex, tok)]]
    if stale:
        newest = max(t for _, t in stale)
        for tok, ts in stale:
            if newest - ts > 365 * 24 * 3600:
                print(f"  AGEING: the exemplar's {tok} has not been touched since"
                      f" {when(ts)}, while {when(newest)} is current here")


# ---------------------------------------------------------------- cli


def main(argv=None) -> int:
    # argv is a parameter so the commands can be exercised in process.
    # Nothing tested any of them while the entry point read sys.argv
    # directly, and the reference-corpus hold-out -- the invariant most
    # worth pinning -- is invisible from an extractor test.
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("config", help="which codebases and destination are configured")
    p.set_defaults(fn=cmd_config)

    p = sub.add_parser("meta", help="what this index covers")
    p.add_argument("--verify", action="store_true",
                   help="also check that each shard holds the number of files "
                        "its meta.json claims. An interrupted build could once "
                        "leave a truncated shard and a confident summary")
    p.set_defaults(fn=cmd_meta)

    p = sub.add_parser("layers", help="what parts exist")
    p.add_argument("--repo")
    p.add_argument("--depth", type=int, default=0, help="roll up to N path segments")
    p.add_argument("--path", help="glob on the file path")
    p.add_argument("--not-path", action="append", metavar="GLOB", default=[],
                   help="exclude paths matching this glob; repeatable")
    p.add_argument("--lang", help="restrict to one language, e.g. python, typescript")
    p.add_argument("--limit", type=int, default=40)
    p.set_defaults(fn=cmd_layers)

    p = sub.add_parser("find", help="definitions matching a filter")
    add_filters(p)
    p.add_argument("--files", action="store_true", help="print unique file paths only")
    p.add_argument("--functions", action="store_true", help="include module-level functions")
    p.add_argument("--tech", metavar="NAME",
                   help="restrict to modules importing this technology, e.g. react")
    p.add_argument("--limit", type=int, default=60)
    p.set_defaults(fn=cmd_find)

    p = sub.add_parser("shape", help="what is ALWAYS true vs. what VARIES")
    add_filters(p)
    add_kind_and_tech(p)
    p.add_argument("--usually", type=int, default=60,
                   help="percent above which a feature counts as usual")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(fn=cmd_shape)

    p = sub.add_parser("exemplars", help="the file to copy, and the outlier")
    add_filters(p)
    add_kind_and_tech(p)
    p.add_argument("--include-target", action="store_true",
                   help="rank the generated target's files too. Off by "
                        "default: this command says what to copy, and copying "
                        "your own output makes one mistake a convention")
    p.add_argument("-n", type=int, default=3)
    p.set_defaults(fn=cmd_exemplars)

    p = sub.add_parser("imports", help="who imports a symbol -- the wiring")
    p.add_argument("symbol_arg", metavar="SYMBOL")
    add_filters(p)
    p.add_argument("--chain", action="store_true",
                   help="follow package __init__ re-exports up the registration chain")
    p.add_argument("--depth", type=int, default=4, help="maximum hops with --chain")
    p.add_argument("--limit", type=int, default=40)
    p.set_defaults(fn=cmd_imports)

    p = sub.add_parser("calls", help="methods called on a name vs. the ones it defines")
    p.add_argument("--on", required=True, metavar="NAME",
                   help="the receiver, e.g. StandardDbCtrl")
    p.add_argument("--defined-in", metavar="GLOB",
                   help="disambiguate when the name is defined more than once")
    add_filters(p)
    p.add_argument("--limit", type=int, default=6)
    p.set_defaults(fn=cmd_calls)

    p = sub.add_parser("deps", help="what each codebase declares it depends on")
    p.add_argument("--repo", help="restrict to one repository")
    p.add_argument("--path", help="glob on the manifest path")
    p.add_argument("--on", metavar="NAME", help="who declares this package, and at what version")
    p.add_argument("--references", action="store_true",
                   help="include the reference corpus. Off by default: a "
                        "package only a reference declares is not already "
                        "paid for")
    p.add_argument("--limit", type=int, default=40)
    p.set_defaults(fn=cmd_deps)

    p = sub.add_parser("practice",
                       help="how the reference corpus resolves a choice vs. the exemplar")
    p.add_argument("--on", required=True, metavar="TOKEN",
                   help="an import, call, base or decorator, e.g. pathlib")
    p.add_argument("--versus", action="append", metavar="TOKEN", default=[],
                   help="the competing choice; repeatable")
    p.add_argument("--lang", help="restrict to one language, e.g. python, typescript")
    p.add_argument("--path", help="glob on the file path")
    p.set_defaults(fn=cmd_practice)

    p = sub.add_parser("conform", help="does the generated layer still keep the contract")
    p.add_argument("--path", required=True, help="glob selecting the source layer")
    p.add_argument("--repo", help="restrict the source side to one repository")
    p.add_argument("--target-path", required=True, help="glob selecting the generated layer")
    p.add_argument("--target-repo", help="restrict the target side to one repository")
    add_kind_and_tech(p)
    p.add_argument("--json", action="store_true",
                   help="machine-readable result and nothing else, so this can "
                        "run as a gate. `contract_empty` distinguishes 'nothing "
                        "was broken' from 'nothing was checked'")
    p.set_defaults(fn=cmd_conform)

    p = sub.add_parser("questions", help="the decisions this layer forces, ranked by cost")
    add_filters(p)
    add_kind_and_tech(p)
    p.add_argument("--usually", type=int, default=60,
                   help="percent above which an attribute counts as universal")
    p.add_argument("--target-path", metavar="GLOB",
                   help="the generated layer. Anything it is unanimous about is "
                        "already answered by the code and is not asked -- the "
                        "target outranks the source")
    p.add_argument("--target-repo",
                   help="defaults to the configured solution")
    p.add_argument("--limit", type=int,
                   default=99 if configured_questions() == "many" else 5,
                   help="how many to print. Not a budget -- `questions` in "
                        "config.json decides how eagerly to ask, and in `many` "
                        "there is no cap: a question suppressed by a count "
                        "becomes a silent guess")
    p.add_argument("--json", action="store_true",
                   help="machine-readable result and nothing else")
    p.set_defaults(fn=cmd_questions)

    p = sub.add_parser("proof", help="how a codebase proves itself -- tests, entry points")
    p.add_argument("--repo")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_proof)

    args = ap.parse_args(argv)
    args.fn(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
