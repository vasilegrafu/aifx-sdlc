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
    meta        what this index covers and when it was built

`shape` is the one that matters. What is always true is contract: reproduce it.
What varies is the axis of choice: decide it, deliberately. What one repository
always does and another never does is a disagreement: ask, do not average.
"""

from __future__ import annotations

import argparse
import datetime
import fnmatch
import json
import re
from collections import Counter, defaultdict

from _common import (configured_repositories, configured_solution,
                     decisions_path, load_config, pct, read_index,
                     skill_root, truncate, workspace)

# ---------------------------------------------------------------- filtering


def head(expr: str) -> str:
    """`session_injector` from `session_injector(x)`; `app.route` from `app.route(...)`."""
    return expr.split("(", 1)[0].strip()


def add_filters(ap):
    ap.add_argument("--name", default="default", help="index name")
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
        if rec["k"] != "class" or not any(args.base == head(b) or args.base in b
                                          for b in rec["bases"]):
            return False
    if args.decorator:
        if not any(args.decorator == head(d) or args.decorator in d
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
    for r in read_index(args.name):
        if r["k"] == "module":
            found = technologies_of(r.get("imports"))
            if found:
                tech[(r["repo"], r["path"])] = found
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
        f |= {f"invoke:{i}" for i in rec.get("invokes", ())}
        f |= {f"call:{c}" for c in rec.get("calls", ())}
        return f

    f = {f"base:{head(b)}" for b in rec["bases"]}
    f |= {f"classdec:{head(d)}" for d in rec["decorators"]}
    f |= {f"assign:{a['name']}" for a in rec["assigns"]}
    f |= {f"attr:{a['name']}" for a in rec["attrs"]}
    f |= {f"attrcall:{a['call']}" for a in rec["attrs"] if a["call"]}
    f |= {f"method:{m['name']}" for m in rec["methods"]}
    for m in rec["methods"]:
        f |= {f"methoddec:{head(d)}" for d in m["decorators"]}
        f |= {f"invoke:{i}" for i in m.get("invokes", ())}
        f |= {f"call:{c}" for c in m.get("calls", ())}
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
    "sqlalchemy": ("sqlalchemy",),
    "django": ("django",),
    "flask": ("flask",),
    "fastapi": ("fastapi", "starlette"),
    "pydantic": ("pydantic",),
    "pandas": ("pandas", "numpy"),
    "pytest": ("pytest", "unittest"),
    "aspnet": ("Microsoft.AspNetCore",),
    "efcore": ("Microsoft.EntityFrameworkCore",),
    "xunit": ("Xunit", "NUnit", "Moq"),
    "blazor": ("Microsoft.AspNetCore.Components",),
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

# ---------------------------------------------------------------- commands


def cmd_config(args):
    """What this skill has been pointed at, and whether it is actually there."""
    cfg = load_config()
    print(f"config  {cfg['_file']}"
          f"{'' if cfg['_exists'] else '   (does not exist)'}\n")

    repos = configured_repositories()
    if not repos:
        print("REPOSITORIES  none configured. Add them to the config file:\n")
        print('  "app-builder": {\n'
              '    "repositories": [{"name": "atlas", "path": "D:/code/atlas"}],\n'
              '    "solution": "solution"\n'
              '  }')
    else:
        print("REPOSITORIES")
        for r in repos:
            print(f"  {'ok ' if r['exists'] else 'MISSING'}  {r['name']:<20} {r['path']}")

    target = configured_solution()
    print(f"\nTARGET        {'ok ' if target['exists'] else 'not built yet'}  "
          f"{target['name']:<20} {target['path']}")
    print("              indexed with the sources; where it has already diverged,"
          "\n              it is the later decision and it wins")

    data = skill_root() / ".data"
    built = sorted(p.name for p in data.iterdir() if p.is_dir()) if data.is_dir() else []
    print(f"\nINDEXES BUILT {', '.join(built) if built else 'none -- run index.py'}")


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
    },
    "typescript": {
        "proof_files": ("package.json", "tsconfig.json", "vitest.config.ts",
                        "jest.config.js", "playwright.config.ts", "vite.config.ts"),
        "barrel": "index.ts",
        "entry": "a script in package.json",
    },
    "javascript": {
        "proof_files": ("package.json", "jest.config.js", "vitest.config.js",
                        "playwright.config.js", "eslint.config.js"),
        "barrel": "index.js",
        "entry": "a script in package.json",
    },
    "csharp": {
        "proof_files": ("Directory.Build.props", "global.json", "nuget.config"),
        # C# has no re-export file: a namespace is visible without one, and the
        # analogue of an unimported class is a service never registered.
        "barrel": None,
        "entry": "a Main method or a host builder",
    },
}

PROOF_FILES = tuple(dict.fromkeys(f for lang in LANGUAGES.values()
                                  for f in lang["proof_files"]))


def language_of(rec) -> str:
    return rec.get("lang") or "python"


def barrel_for(rec) -> str | None:
    return LANGUAGES.get(language_of(rec), LANGUAGES["python"])["barrel"]


def cmd_proof(args):
    """What the codebase itself uses as proof -- step 8 needs this, and asking
    the user for it is asking them something their repository already says."""
    for repo in configured_repositories():
        if args.repo and repo["name"] != args.repo:
            continue
        print(f"== {repo['name']} ==   {repo['path']}\n")
        if not repo["exists"]:
            print("  path does not exist on this machine\n")
            continue
        found = [f for f in PROOF_FILES if (repo["path"] / f).is_file()]
        print("  CONFIG      " + (", ".join(found) if found else "none found"))
        venv = next((v for v in (".venv", "venv", "env")
                     if (repo["path"] / v / "Scripts" / "python.exe").is_file()
                     or (repo["path"] / v / "bin" / "python").is_file()), None)
        print(f"  INTERPRETER {repo['path'] / venv if venv else 'none in the tree'}")

    test_dirs, entries, langs = Counter(), [], Counter()
    for rec in read_index(args.name):
        if args.repo and rec["repo"] != args.repo:
            continue
        if rec["k"] != "module":
            continue
        langs[language_of(rec)] += 1
        top = rec["path"].split("/")[0]
        if "test" in top.lower() or "spec" in top.lower():
            test_dirs[f"{rec['repo']}/{top}"] += 1
        if rec.get("main"):
            entries.append(f"{rec['repo']}/{rec['path']}")

    print("\n  LANGUAGES   " + ", ".join(f"{k} ({v} files)"
                                         for k, v in langs.most_common()))
    print("  TESTS       " + (", ".join(f"{d} ({n} files)"
                                        for d, n in test_dirs.most_common())
                              if test_dirs else "no test directories in the index"))
    print("  ENTRY POINTS")
    for e in entries[: args.limit]:
        print(f"      {e}")
    if not entries:
        print("      none -- no module guards on __main__")
    elif len(entries) > args.limit:
        print(f"      ... {len(entries) - args.limit} more")


HEADER = ("# Decisions\n\n"
          "Answers to disagreements between the indexed codebases. Read before\n"
          "asking. An answer here is a standing instruction: apply it silently,\n"
          "unless the request contradicts it, in which case the request wins and\n"
          "the row is updated.\n\n"
          "| id | decision | answer | asked |\n"
          "|----|----------|--------|-------|\n")


def read_decisions(name: str) -> list[dict]:
    path = decisions_path(name)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 4 or cells[0] in ("id", "") or set(cells[0]) <= {"-", ":"}:
            continue
        rows.append(dict(zip(("id", "decision", "answer", "asked"), cells)))
    return rows


def cmd_decisions(args):
    """What has already been settled, so it is not asked again."""
    rows = read_decisions(args.name)
    path = decisions_path(args.name)
    if not rows:
        return print(f"no decisions recorded for {args.name!r}\n  {path}\n\n"
                     "Record one after asking:\n"
                     "  query.py decide --name X --id primary-key-type \\\n"
                     "      --decision 'atlas: Uuid surrogate. other: natural key.' \\\n"
                     "      --answer Uuid")
    print(f"{len(rows)} decision(s)   {path}\n")
    width = max(len(r["id"]) for r in rows)
    for r in rows:
        print(f"  {r['id']:<{width}}  {r['answer']}     ({r['asked']})")
        print(f"  {'':<{width}}  {r['decision']}")


def cmd_decide(args):
    """Record an answer. Updating an id replaces it -- the later word wins."""
    path = decisions_path(args.name)
    rows = read_decisions(args.name)
    asked = args.asked or datetime.date.today().isoformat()
    new = {"id": args.id, "decision": args.decision or "", "answer": args.answer,
           "asked": asked}
    existing = next((r for r in rows if r["id"] == args.id), None)
    if existing:
        if not args.decision:
            new["decision"] = existing["decision"]
        rows[rows.index(existing)] = new
        verb = "updated"
    else:
        rows.append(new)
        verb = "recorded"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(f"| {r['id']} | {r['decision']} | {r['answer']} | {r['asked']} |\n"
                   for r in rows)
    path.write_text(HEADER + body, encoding="utf-8")
    print(f"{verb} {args.id!r} -> {args.answer!r}\n  {path}")


def cmd_meta(args):
    path = workspace(args.name) / "meta.json"
    if not path.exists():
        return print(f"no index named {args.name!r}")
    meta = json.loads(path.read_text(encoding="utf-8"))
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
    for rec in read_index(args.name):
        if args.repo and rec["repo"] != args.repo:
            continue
        if args.path and not fnmatch.fnmatch(rec["path"], args.path):
            continue
        if any(fnmatch.fnmatch(rec["path"], g) for g in args.not_path or ()):
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


def cmd_shape(args):
    recs = collect(args, kinds=kinds_for(args))
    if not recs:
        return print("nothing matched -- widen --path, drop --base,"
                     " or try --kind func")
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

    print(f"{total} {noun}"
          + (f"  ({', '.join(f'{k} {v}' for k, v in per_repo.items())})"
             if len(per_repo) > 1 else f"  in {next(iter(per_repo))}")
          + f"   touched {when(set_oldest)} .. {when(set_newest)}")

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
        settled = read_decisions(args.name)
        if settled:
            print("   already settled -- apply these silently, do not ask again:")
            for d in settled:
                print(f"     {d['id']}: {d['answer']}   ({d['asked']})")
            print()
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
    recs = collect(args, kinds=kinds_for(args))
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
        if imp.get("name") in names or imp["mod"].split(".")[-1] in names \
                or imp.get("as") in names:
            return imp["mod"], imp.get("name")
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

    for rec in read_index(args.name):
        if rec["k"] == "class":
            if rec["name"] == on and (not args.defined_in
                                      or fnmatch.fnmatch(rec["path"], args.defined_in)):
                found_class = rec
                defined |= {m["name"] for m in rec["methods"]}
                defined |= {a["name"] for a in rec["attrs"]}
                defined |= {a["name"] for a in rec["assigns"]}
            for m in rec["methods"]:
                for call in m.get("calls", ()):
                    root, _, attr = call.partition(".")
                    if root == on and matches(rec, args):
                        called[attr].append(f"{rec['repo']}/{rec['path']}:{m['line']}")
        elif rec["k"] == "func":
            for call in rec.get("calls", ()):
                root, _, attr = call.partition(".")
                if root == on and matches(rec, args):
                    called[attr].append(f"{rec['repo']}/{rec['path']}:{rec['line']}")

    if not called:
        return print(f"nothing calls anything on {on!r}")

    print(f"{len(called)} distinct methods called on {on}"
          f"  ({sum(len(v) for v in called.values())} call sites)\n")

    if found_class is None:
        print(f"  {on} is not defined in this index, so nothing can be checked "
              f"against it.\n  Calls found:\n")
        for attr, sites in sorted(called.items(), key=lambda kv: -len(kv[1])):
            print(f"    {attr:<28} {len(sites)}")
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


def cmd_conform(args):
    """Does the generated layer still satisfy the contract that produced it?

    `shape` says what is ALWAYS true of the source. Nothing else checks that the
    output kept it. This does: same measure, both sides, difference reported.
    """
    source = [r for r in read_index(args.name) if r["k"] == "class"
              and fnmatch.fnmatch(r["path"], args.path)
              and (not args.repo or r["repo"] == args.repo)]
    target = [r for r in read_index(args.name) if r["k"] == "class"
              and fnmatch.fnmatch(r["path"], args.target_path)
              and (not args.target_repo or r["repo"] == args.target_repo)]

    if not source:
        return print("no source classes matched --path/--repo")
    if not target:
        return print("no target classes matched --target-path/--target-repo")

    source_always = set.intersection(*(features(r) for r in source))
    target_always = set.intersection(*(features(r) for r in target))

    print(f"source {len(source)} classes  ->  target {len(target)} classes\n")

    kept = sorted(source_always & target_always)
    dropped = sorted(source_always - target_always)
    added = sorted(target_always - source_always)

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
    else:
        print("  none -- the target keeps everything the source contracts.")

    if added:
        print(f"\n== ADDED ({len(added)}) ==")
        print("   universal in the target and not in the source. Usually the domain,"
              "\n   sometimes a convention worth carrying back.\n")
        print("  " + ", ".join(f.split(':', 1)[1] for f in added))


def cmd_imports(args):
    sym = args.symbol_arg
    modules, subclasses = [], []
    for rec in read_index(args.name):
        if not matches(rec, args):
            continue
        if rec["k"] == "module":
            modules.append(rec)
        elif rec["k"] == "class" and any(head(b) == sym for b in rec["bases"]):
            subclasses.append((rec["repo"], rec["path"], rec["name"]))

    frontier, seen, level = {sym}, {sym}, 0
    while frontier:
        hits = [(m, _imports_any(m, frontier)) for m in modules]
        hits = [(m, i) for m, i in hits if i]
        label = ("IMPORTED BY" if level == 0
                 else f"WHICH IS REACHED THROUGH ({' / '.join(sorted(frontier))})")
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
        nxt = {m["dir"].rsplit("/", 1)[-1] for m, _ in hits
               if barrel_for(m) and m["path"].endswith(barrel_for(m)) and m["dir"]}
        frontier = nxt - seen
        seen |= frontier
        if not frontier:
            break
        print()

    if subclasses:
        print(f"\nSUBCLASSED BY ({len(subclasses)})\n")
        for repo, path, name in subclasses[: args.limit]:
            print(f"  {repo}/{path}  {name}")


# ---------------------------------------------------------------- cli


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("config", help="which codebases and destination are configured")
    p.set_defaults(fn=cmd_config)

    p = sub.add_parser("meta", help="what this index covers")
    p.add_argument("--name", default="default")
    p.set_defaults(fn=cmd_meta)

    p = sub.add_parser("layers", help="what parts exist")
    p.add_argument("--name", default="default")
    p.add_argument("--repo")
    p.add_argument("--depth", type=int, default=0, help="roll up to N path segments")
    p.add_argument("--path", help="glob on the file path")
    p.add_argument("--not-path", action="append", metavar="GLOB", default=[],
                   help="exclude paths matching this glob; repeatable")
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

    p = sub.add_parser("conform", help="does the generated layer still keep the contract")
    p.add_argument("--name", default="default")
    p.add_argument("--path", required=True, help="glob selecting the source layer")
    p.add_argument("--repo", help="restrict the source side to one repository")
    p.add_argument("--target-path", required=True, help="glob selecting the generated layer")
    p.add_argument("--target-repo", help="restrict the target side to one repository")
    p.set_defaults(fn=cmd_conform)

    p = sub.add_parser("decisions", help="answers already given, so they are not asked twice")
    p.add_argument("--name", default="default")
    p.set_defaults(fn=cmd_decisions)

    p = sub.add_parser("decide", help="record the answer to a disagreement")
    p.add_argument("--name", default="default")
    p.add_argument("--id", required=True, metavar="KEBAB-CASE",
                   help="stable, never reused -- it is what makes 'already asked' answerable")
    p.add_argument("--answer", required=True, help="the user's words, not a paraphrase")
    p.add_argument("--decision", help="what each codebase actually does, with its name")
    p.add_argument("--asked", help="ISO date; today if omitted")
    p.set_defaults(fn=cmd_decide)

    p = sub.add_parser("proof", help="how a codebase proves itself -- tests, entry points")
    p.add_argument("--name", default="default")
    p.add_argument("--repo")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_proof)

    args = ap.parse_args()
    args.fn(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
