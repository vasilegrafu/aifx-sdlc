"""Query a structural index built by index.py.

Every subcommand answers a question with a few hundred lines at most, so that a
codebase of any size can be understood without reading it.

    config      which codebases and which destination are configured
    proof       how a codebase proves itself: tests, entry points, interpreter
    layers      what parts exist, and which is the one you were asked about
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

from _common import (configured_repositories, load_config, pct, read_index,
                     skill_root, solution_dir, truncate, workspace)

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


def matches(rec, args) -> bool:
    if args.repo and rec["repo"] != args.repo:
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
    return [r for r in read_index(args.name) if r["k"] in kinds and matches(r, args)]


# ---------------------------------------------------------------- features


def features(cls) -> set[str]:
    f = {f"base:{head(b)}" for b in cls["bases"]}
    f |= {f"classdec:{head(d)}" for d in cls["decorators"]}
    f |= {f"assign:{a['name']}" for a in cls["assigns"]}
    f |= {f"attr:{a['name']}" for a in cls["attrs"]}
    f |= {f"attrcall:{a['call']}" for a in cls["attrs"] if a["call"]}
    f |= {f"method:{m['name']}" for m in cls["methods"]}
    for m in cls["methods"]:
        f |= {f"methoddec:{head(d)}" for d in m["decorators"]}
    return f


LABELS = {
    "base": "base classes", "classdec": "class decorators",
    "assign": "class-level assignments", "attr": "attributes",
    "attrcall": "attribute constructors", "method": "methods",
    "methoddec": "method decorators",
}

# ---------------------------------------------------------------- commands


def cmd_config(args):
    """What this skill has been pointed at, and whether it is actually there."""
    cfg = load_config()
    print(f"config  {cfg['_file']}"
          f"{'' if cfg['_exists'] else '   (does not exist)'}\n")

    repos = configured_repositories()
    if not repos:
        print("REPOSITORIES  none configured. Add them to the config file:\n")
        print('  "pyapp": {\n'
              '    "repositories": [{"name": "atlas", "path": "D:/code/atlas"}],\n'
              '    "solution": "solution"\n'
              '  }')
    else:
        print("REPOSITORIES")
        for r in repos:
            print(f"  {'ok ' if r['exists'] else 'MISSING'}  {r['name']:<20} {r['path']}")

    sol = solution_dir()
    print(f"\nSOLUTION      {sol}"
          f"{'' if sol.is_dir() else '   (does not exist yet)'}")

    data = skill_root() / ".data"
    built = sorted(p.name for p in data.iterdir() if p.is_dir()) if data.is_dir() else []
    print(f"\nINDEXES BUILT {', '.join(built) if built else 'none -- run index.py'}")


PROOF_FILES = ("pytest.ini", "tox.ini", "setup.cfg", "pyproject.toml", "noxfile.py",
               "Makefile", "manage.py", "conftest.py", "alembic.ini", "requirements.txt")


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

    test_dirs, entries = Counter(), []
    for rec in read_index(args.name):
        if args.repo and rec["repo"] != args.repo:
            continue
        if rec["k"] != "module":
            continue
        top = rec["path"].split("/")[0]
        if "test" in top.lower():
            test_dirs[f"{rec['repo']}/{top}"] += 1
        if rec.get("main"):
            entries.append(f"{rec['repo']}/{rec['path']}")

    print("\n  TESTS       " + (", ".join(f"{d} ({n} files)"
                                          for d, n in test_dirs.most_common())
                                if test_dirs else "no test directories in the index"))
    print("  ENTRY POINTS")
    for e in entries[: args.limit]:
        print(f"      {e}")
    if not entries:
        print("      none -- no module guards on __main__")
    elif len(entries) > args.limit:
        print(f"      ... {len(entries) - args.limit} more")


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
    recs = collect(args)
    if not recs:
        return print("nothing matched -- widen --path or drop --base")
    total = len(recs)
    per_repo = Counter(r["repo"] for r in recs)

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

    print(f"{total} classes"
          + (f"  ({', '.join(f'{k} {v}' for k, v in per_repo.items())})"
             if len(per_repo) > 1 else f"  in {next(iter(per_repo))}")
          + f"   touched {when(set_oldest)} .. {when(set_newest)}")

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
        for a in r["attrs"]:
            by_attr[a["name"]].append(a)
    detailed = [(n, a) for n, a in by_attr.items()
                if pct(len(a), total) >= args.usually]
    if detailed:
        print(f"\n== ATTRIBUTE DETAIL ==   (present in >= {args.usually}% of classes)")
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
        print("\n== DISAGREEMENTS ==")
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
                print(f"  {LABELS.get(kind, kind)}: {item}")
                for r, c, n in hi + lo:
                    print(f"      {r:<24} {c}/{n} ({pct(c, n)}%)")
        if not found:
            print("  none -- the repositories agree on every feature of this set.")


def cmd_exemplars(args):
    recs = collect(args)
    if not recs:
        return print("nothing matched -- widen --path or drop --base")
    total = len(recs)
    counts = Counter()
    for r in recs:
        counts.update(features(r))
    modal = {f for f, n in counts.items() if pct(n, total) >= 50}

    scored = []
    for r in recs:
        f = features(r)
        # reward the shared shape, penalise what nothing else has
        rare = sum(1 for x in f - modal if counts[x] <= max(1, total * 0.1))
        size = len(r["attrs"]) + len(r["methods"])
        # most modal features wins; then fewest oddities; then the fuller class,
        # because an empty class is a poor thing to copy even when it is typical
        scored.append((-(len(f & modal) - rare), rare, -size, r))
    scored.sort(key=lambda t: t[:3])

    print("MOST TYPICAL -- copy the structure of these\n")
    for negscore, _, _, r in scored[: args.n]:
        print(f"  {r['repo']}/{r['path']}:{r['line']}  {r['name']}"
              f"  [{len(r['attrs'])} attrs, {len(r['methods'])} methods,"
              f" score {-negscore}]")

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

    print(f"\n{total} classes considered. Read the typical one in full before "
          f"generating; read the atypical one to see what is optional.")


def _imports_any(mod, names: set[str]) -> tuple[str, str] | None:
    for imp in mod["imports"]:
        if imp.get("name") in names or imp["mod"].split(".")[-1] in names \
                or imp.get("as") in names:
            return imp["mod"], imp.get("name")
    return None


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
               if m["path"].endswith("__init__.py") and m["dir"]}
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
    p.add_argument("--limit", type=int, default=60)
    p.set_defaults(fn=cmd_find)

    p = sub.add_parser("shape", help="what is ALWAYS true vs. what VARIES")
    add_filters(p)
    p.add_argument("--usually", type=int, default=60,
                   help="percent above which a feature counts as usual")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(fn=cmd_shape)

    p = sub.add_parser("exemplars", help="the file to copy, and the outlier")
    add_filters(p)
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
