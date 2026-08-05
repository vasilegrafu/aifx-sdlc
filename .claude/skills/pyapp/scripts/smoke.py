"""Prove generated code is wired in, not merely well-formed.

Two checks, in order of how quietly they fail:

  1. IMPORTS   -- does the module actually import, in the project it belongs to
  2. REACHABLE -- does anything import what it defines

The second is the one worth having. A class nothing imports is syntactically
perfect, passes every linter, and never takes effect: the table is not created,
the route is not registered, the handler never runs. Nothing errors. It surfaces
much later, against a system that looks healthy.

    ./.venv/Scripts/python.exe .claude/skills/pyapp/scripts/smoke.py \
        --app myapp --python solution/myapp/.venv/Scripts/python.exe \
        database/reference_data/models/stock_instrument.py

`--app` resolves under the solution directory named in the config. Use `--root`
instead for a project that lives somewhere else.
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from pathlib import Path

from _common import iter_py_files, rel, solution_dir


def dotted(path: Path, root: Path) -> str:
    mod = rel(path, root)[:-3].replace("/", ".")
    return mod[: -len(".__init__")] if mod.endswith(".__init__") else mod


def defined_names(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, ValueError) as exc:
        return [f"!{exc}"]
    return [n.name for n in tree.body
            if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]


def is_entry_point(path: Path) -> bool:
    """Does the module guard on `__main__`?

    What such a module defines is *called*, not imported, so nothing importing
    it is the normal state rather than a missing registration. Reporting a
    generator's own `generate()` as unwired trains the reader to ignore this
    check, which is the one failure it exists to catch.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, ValueError):
        return False
    for node in tree.body:
        if isinstance(node, ast.If) and "__main__" in ast.dump(node.test):
            return True
    return False


def importers_of(root: Path, targets: set[str], exclude: set[Path]) -> dict[str, list[str]]:
    """Which files import each target name. Scans the project, not the world."""
    found: dict[str, list[str]] = {t: [] for t in targets}
    for path in iter_py_files(root, max_bytes=2_000_000):
        if path.resolve() in exclude:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, ValueError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for a in node.names:
                    if a.name in found:
                        found[a.name].append(rel(path, root))
                    elif a.name == "*":
                        # a star import re-exports whatever the module defines
                        found.setdefault("*", []).append(rel(path, root))
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="generated files, relative to the root or absolute")
    ap.add_argument("--app", help="application subdirectory of the configured solution "
                                  "directory; omit when the solution directory is itself "
                                  "the application root")
    ap.add_argument("--root", help="the project the files belong to (overrides --app)")
    ap.add_argument("--python", help="interpreter for the import check "
                                     "(default: skip, structure check only)")
    ap.add_argument("--timeout", type=int, default=60)
    args = ap.parse_args()

    if args.root:
        root = Path(args.root).resolve()
    elif args.app:
        root = solution_dir() / args.app
    else:
        # The destination may hold one application at its root, or several in
        # named subdirectories. With no --app, it is the former.
        root = solution_dir()
    if not root.is_dir():
        sys.exit(f"not a directory: {root}")
    files = [(root / f).resolve() if not Path(f).is_absolute() else Path(f).resolve()
             for f in args.files]
    missing = [f for f in files if not f.exists()]
    if missing:
        sys.exit("no such file(s): " + ", ".join(str(m) for m in missing))

    failures = 0

    print("== IMPORTS ==")
    if not args.python:
        print("  skipped -- pass --python <interpreter> to actually import")
    else:
        for f in files:
            mod = dotted(f, root)
            proc = subprocess.run([args.python, "-c", f"import {mod}"], cwd=root,
                                  capture_output=True, text=True, timeout=args.timeout)
            if proc.returncode == 0:
                print(f"  ok    {mod}")
            else:
                failures += 1
                last = [ln for ln in proc.stderr.strip().splitlines() if ln.strip()]
                print(f"  FAIL  {mod}\n        {last[-1] if last else 'no output'}")

    print("\n== REACHABLE ==")
    targets: dict[str, Path] = {}
    entry_points = []
    for f in files:
        entry = is_entry_point(f)
        for name in defined_names(f):
            if name.startswith("!"):
                print(f"  FAIL  {rel(f, root)} does not parse: {name[1:]}")
                failures += 1
            elif name.startswith("_"):
                continue
            elif entry:
                entry_points.append((name, rel(f, root)))
            else:
                targets[name] = f

    found = importers_of(root, set(targets), exclude={f.resolve() for f in files})
    for name, src in sorted(targets.items()):
        by = found.get(name, [])
        if by:
            print(f"  ok    {name:<32} imported by {by[0]}"
                  + (f" (+{len(by) - 1})" if len(by) > 1 else ""))
        else:
            failures += 1
            pkg_init = rel(src.parent / "__init__.py", root)
            print(f"  UNWIRED  {name:<29} nothing in the project imports it.")
            print(f"           This will not fail loudly. Add it to {pkg_init}"
                  f" -- or say why it needs no registration.")

    for name, where in entry_points:
        print(f"  entry {name:<32} called from __main__ in {where}, not imported")

    star = found.get("*", [])
    if star:
        print(f"\n  note: {len(star)} star-import(s) in the project "
              f"({star[0]}...) may re-export names this check cannot see.")

    print(f"\n{'FAILED' if failures else 'PASSED'} -- {failures} problem(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
