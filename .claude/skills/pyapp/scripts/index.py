"""Build a structural index of one or more Python codebases.

Emits one JSON record per module, class and module-level function -- signatures,
bases, decorators, annotated attributes, imports. Not source. The point is that
a codebase of any size collapses into something a query can filter, so that only
a handful of files are ever opened and read.

With no roots it indexes every repository in `config.json`, which is where the
codebases available to this skill are declared:

    ./.venv/Scripts/python.exe .claude/skills/pyapp/scripts/index.py --name atlas

Explicit roots still work and override the config, keeping each root's directory
name as its repo identity:

    ./.venv/Scripts/python.exe .claude/skills/pyapp/scripts/index.py \
        --name scratch D:/code/solution.atlas D:/code/other-repo

Re-running rebuilds from scratch -- indexing is cheap, staleness is not.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
import time
from pathlib import Path

from _common import (SKIP_DIRS, configured_repositories, index_path, iter_py_files,
                     load_config, rel, truncate, workspace)


def git_last_commit(root: Path, timeout: int = 180) -> dict[str, int]:
    """`{relative path: epoch of the last commit that touched it}`.

    One `git log` for the whole repository, not one per file. Empty when the
    root is not a working tree -- and empty for anything reached through a
    symlink out of it, which then falls back to mtime.

    This is the only thing in the index that can tell a live convention from a
    fossil. Without it `shape` counts files, and a pattern being abandoned still
    wins on count.
    """
    def run(*args) -> str | None:
        try:
            proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                                  text=True, timeout=timeout, errors="replace")
        except (OSError, subprocess.TimeoutExpired):
            return None
        return proc.stdout if proc.returncode == 0 else None

    # git reports paths from the top of the working tree, which is not always
    # the directory being indexed -- a solution can sit one level down inside a
    # larger repository. Without stripping that prefix nothing ever matches and
    # every file silently falls back to mtime.
    top = run("rev-parse", "--show-toplevel")
    if top is None:
        return {}
    prefix = ""
    try:
        inside = root.resolve().relative_to(Path(top.strip()).resolve()).as_posix()
        prefix = "" if inside == "." else inside + "/"
    except ValueError:
        prefix = ""

    out = run("log", "--no-merges", "--format=%ct", "--name-only")
    if out is None:
        return {}

    dates: dict[str, int] = {}
    stamp = None
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if len(line) == 10 and line.isdigit():
            stamp = int(line)
        elif stamp is not None:
            if prefix:
                if not line.startswith(prefix):
                    continue
                line = line[len(prefix):]
            # log is newest-first, so the first sighting is the latest commit
            dates.setdefault(line, stamp)
    return dates


def linked_dirs(root: Path) -> list[Path]:
    """Top-level directories that are junctions or symlinks out of the tree."""
    out = []
    try:
        children = list(root.iterdir())
    except OSError:
        return out
    for child in children:
        if child.name in SKIP_DIRS or child.name.startswith("."):
            continue
        try:
            if child.is_dir() and (child.is_symlink() or child.resolve() != child):
                out.append(child)
        except OSError:
            continue
    return out


def _summary(doc: str | None) -> str | None:
    """First line of a docstring, or None. Docstrings may be empty or blank."""
    lines = (doc or "").strip().splitlines()
    return truncate(lines[0], 200) if lines else None


def _name(node) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return "?"


def _params(fn: ast.AST) -> list[str]:
    a = fn.args
    out = [p.arg for p in (*a.posonlyargs, *a.args)]
    if a.vararg:
        out.append("*" + a.vararg.arg)
    out += [p.arg for p in a.kwonlyargs]
    if a.kwarg:
        out.append("**" + a.kwarg.arg)
    return out


def _method(fn) -> dict:
    return {
        "name": fn.name,
        "decorators": [_name(d) for d in fn.decorator_list],
        "params": _params(fn),
        "returns": _name(fn.returns) if fn.returns else None,
        "line": fn.lineno,
        "async": isinstance(fn, ast.AsyncFunctionDef),
    }


def _attr_from_annassign(node: ast.AnnAssign) -> dict | None:
    if not isinstance(node.target, ast.Name):
        return None
    rec = {"name": node.target.id, "ann": _name(node.annotation), "call": None,
           "args": [], "kw": []}
    if isinstance(node.value, ast.Call):
        rec["call"] = _name(node.value.func)
        rec["args"] = [truncate(_name(a), 60) for a in node.value.args]
        rec["kw"] = [k.arg for k in node.value.keywords if k.arg]
    elif node.value is not None:
        rec["args"] = [truncate(_name(node.value), 60)]
    return rec


def _class(node: ast.ClassDef, mod: dict) -> dict:
    attrs, assigns, methods, nested = [], [], [], []
    for item in node.body:
        if isinstance(item, ast.AnnAssign):
            a = _attr_from_annassign(item)
            if a:
                attrs.append(a)
        elif isinstance(item, ast.Assign):
            for t in item.targets:
                if isinstance(t, ast.Name):
                    assigns.append({"name": t.id,
                                    "value": truncate(_name(item.value), 240)})
        elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(_method(item))
        elif isinstance(item, ast.ClassDef):
            nested.append(item.name)
    return {
        "k": "class",
        "repo": mod["repo"],
        "path": mod["path"],
        "mtime": mod["mtime"],
        "commit": mod["commit"],
        "name": node.name,
        "bases": [_name(b) for b in node.bases],
        "keywords": [f"{k.arg}={_name(k.value)}" for k in node.keywords if k.arg],
        "decorators": [_name(d) for d in node.decorator_list],
        "line": node.lineno,
        "attrs": attrs,
        "assigns": assigns,
        "methods": methods,
        "nested": nested,
        "doc": _summary(ast.get_docstring(node)),
    }


def _imports(tree: ast.Module) -> list[dict]:
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.append({"mod": a.name, "name": None, "as": a.asname})
        elif isinstance(node, ast.ImportFrom):
            mod = "." * (node.level or 0) + (node.module or "")
            for a in node.names:
                out.append({"mod": mod, "name": a.name, "as": a.asname})
    return out


def index_file(path: Path, root: Path, repo: str, source: str,
               commits: dict[str, int] | None = None):
    """Yield the records for one file. Never raises on bad syntax."""
    relpath = rel(path, root)
    try:
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, ValueError) as exc:
        yield {"k": "unparsed", "repo": repo, "path": relpath, "error": str(exc)[:200]}
        return

    pkg = relpath[:-3].replace("/", ".")
    if pkg.endswith(".__init__"):
        pkg = pkg[: -len(".__init__")]

    try:
        mtime = int(path.stat().st_mtime)
    except OSError:
        mtime = 0

    mod = {
        "k": "module",
        "repo": repo,
        "path": relpath,
        "pkg": pkg,
        "dir": relpath.rsplit("/", 1)[0] if "/" in relpath else "",
        "loc": source.count("\n") + 1,
        "mtime": mtime,
        "commit": (commits or {}).get(relpath),
        "main": "__main__" in source,
        "imports": _imports(tree),
        "doc": _summary(ast.get_docstring(tree)),
    }
    yield mod

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            yield _class(node, mod)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            rec = _method(node)
            rec.update({"k": "func", "repo": repo, "path": relpath,
                        "mtime": mod["mtime"], "commit": mod["commit"]})
            yield rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("roots", nargs="*",
                    help="codebase roots to index (default: every repository "
                         "in config.json)")
    ap.add_argument("--name", default="default",
                    help="index name (workspace <skill>/.data/<name>/)")
    ap.add_argument("--max-bytes", type=int, default=2_000_000,
                    help="skip files larger than this")
    ap.add_argument("--no-git", action="store_true",
                    help="skip last-commit dates; mtime alone decides recency")
    args = ap.parse_args()

    if args.roots:
        targets = [{"name": Path(r).resolve().name, "path": Path(r).resolve(),
                    "exclude": ()} for r in args.roots]
    else:
        targets = [t for t in configured_repositories()]
        if not targets:
            sys.exit("no roots given and no repositories in config"
                     f" ({load_config()['_file']}).\n"
                     'Add them under "pyapp": {"repositories": '
                     '[{"name": ..., "path": ...}]}')
        gone = [t for t in targets if not t["exists"]]
        if gone:
            print("configured but not found on this machine:", file=sys.stderr)
            for t in gone:
                print(f"  {t['name']}: {t['path']}", file=sys.stderr)
            targets = [t for t in targets if t["exists"]]
            if not targets:
                sys.exit("nothing left to index")

    ws = workspace(args.name)
    ws.mkdir(parents=True, exist_ok=True)
    out_path = index_path(args.name)

    started = time.time()
    files = classes = funcs = unparsed = dated = 0
    repos = []

    with out_path.open("w", encoding="utf-8", newline="\n") as fh:
        for target in targets:
            root, repo = target["path"], target["name"]
            if not root.is_dir():
                print(f"not a directory, skipped: {root}", file=sys.stderr)
                continue
            repos.append(repo)
            n_before = files
            commits = {} if args.no_git else git_last_commit(root)
            if not args.no_git:
                # A linked-in directory belongs to the solution but is tracked in
                # its own repository, so the root's log says nothing about it.
                # Ask its repository too, and key the answers by the name the
                # solution knows it under.
                for child in linked_dirs(root):
                    for path, stamp in git_last_commit(child).items():
                        commits.setdefault(f"{child.name}/{path}", stamp)
            dated += len(commits)
            for path in iter_py_files(root, args.max_bytes,
                                      target.get("exclude", ())):
                try:
                    source = path.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    print(f"unreadable, skipped: {path}: {exc}", file=sys.stderr)
                    continue
                files += 1
                for rec in index_file(path, root, repo, source, commits):
                    if rec["k"] == "class":
                        classes += 1
                    elif rec["k"] == "func":
                        funcs += 1
                    elif rec["k"] == "unparsed":
                        unparsed += 1
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"  {repo}: {files - n_before} files  <- {root}")

    meta = {
        "name": args.name,
        "roots": {t["name"]: str(t["path"]) for t in targets},
        "source": "command line" if args.roots else load_config()["_file"],
        "repos": repos, "files": files, "classes": classes, "funcs": funcs,
        "unparsed": unparsed, "git_dated": dated,
        "built": time.strftime("%Y-%m-%d %H:%M:%S"),
        "seconds": round(time.time() - started, 1),
    }
    (ws / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    size_mb = out_path.stat().st_size / 1e6
    print(f"\nindexed {files} files -> {classes} classes, {funcs} functions"
          f"{f', {unparsed} unparsed' if unparsed else ''}")
    print(f"{out_path}  ({size_mb:.1f} MB, {meta['seconds']}s)")
    print("\nDo not read this file. Query it:")
    print(f"  scripts/query.py layers --name {args.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
