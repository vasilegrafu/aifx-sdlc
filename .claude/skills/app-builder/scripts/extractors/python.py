"""Python extraction: source text in, index records out.

Python is the special case where the parser is in the standard library, so this
runs in-process. Every other language shells out to its own toolchain -- see
`references/languages.md` -- which is why `extract` takes a list of files rather
than one: a process per file turns a two-second index into minutes.
"""

from __future__ import annotations

import ast
from pathlib import Path

from _common import rel, truncate


# What this extractor reads, and how well. Both are stamped on every record: a
# heuristic extractor's "100% of classes do this" is a weaker claim than an AST
# one's, and `shape` output can only be trusted if it says which it is. A second
# language becomes a second module with these two constants and an `extract`.
LANGUAGE = "python"
FIDELITY = "ast"
EXTENSIONS = (".py", ".pyi")


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


def _call_root(node) -> str | None:
    """`StandardDbCtrl` from `StandardDbCtrl(session).select(X).filter(Y)`.

    Walks down the receiver chain to whatever it started as -- a name, or a call
    on a name. Anything more elaborate is left alone rather than guessed at.
    """
    while True:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Call):
            node = node.func
        elif isinstance(node, ast.Attribute):
            node = node.value
        else:
            return None


def _calls(fn) -> tuple[list, list]:
    """`(calls, invokes)`: method calls as `root.attr`, and bare function calls.

    Each entry is `[name, line]`. The line is the call's own, not the enclosing
    function's, which is the difference between being pointed at a call site and
    being pointed at a forty-line method and told to look.

    What a family *calls* is not visible anywhere else in the index, and it is
    where a method that does not exist hides: the definition is perfect, the
    file imports, and the call raises only when something finally runs it.

    The two are kept apart rather than merged, because a name with no receiver
    is a different question from a member on one -- and in some languages the
    bare calls carry most of the convention. A React component is defined far
    more by which hooks it calls than by anything it declares.
    """
    calls, invokes = [], []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            root = _call_root(node.func.value)
            if root:
                entry = [f"{root}.{node.func.attr}", node.func.value.lineno]
                if entry not in calls:
                    calls.append(entry)
        elif isinstance(node.func, ast.Name):
            entry = [node.func.id, node.func.lineno]
            if entry not in invokes:
                invokes.append(entry)
    return calls, invokes


def _method(fn) -> dict:
    calls, invokes = _calls(fn)
    return {
        "name": fn.name,
        "decorators": [_name(d) for d in fn.decorator_list],
        "params": _params(fn),
        "returns": _name(fn.returns) if fn.returns else None,
        "line": fn.lineno,
        "end": getattr(fn, "end_lineno", None) or fn.lineno,
        "async": isinstance(fn, ast.AsyncFunctionDef),
        "calls": calls,
        "invokes": invokes,
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
        "lang": mod["lang"],
        "repo": mod["repo"],
        "path": mod["path"],
        "mtime": mod["mtime"],
        "commit": mod["commit"],
        "name": node.name,
        "bases": [_name(b) for b in node.bases],
        "keywords": [f"{k.arg}={_name(k.value)}" for k in node.keywords if k.arg],
        "decorators": [_name(d) for d in node.decorator_list],
        "line": node.lineno,
        "end": getattr(node, "end_lineno", None) or node.lineno,
        "attrs": attrs,
        "assigns": assigns,
        "methods": methods,
        "nested": nested,
    }


def _exports(tree: ast.Module) -> list[str]:
    """What the module offers to importers.

    `__all__` when it is declared, otherwise the public top-level names. This is
    how a re-export chain is followed -- a package `__init__` here, an `index.ts`
    barrel elsewhere -- and how you tell a definition that is reachable from one
    that merely exists.
    """
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "__all__":
                    try:
                        value = ast.literal_eval(node.value)
                        return [str(v) for v in value]
                    except (ValueError, TypeError):
                        pass
    out = []
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                out.append(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                name = a.asname or a.name.split(".")[0]
                if name != "*" and not name.startswith("_"):
                    out.append(name)
    return out


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
        yield {"k": "unparsed", "lang": LANGUAGE, "repo": repo, "path": relpath,
               "error": str(exc)[:200]}
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
        "lang": LANGUAGE,
        "repo": repo,
        "path": relpath,
        "exports": _exports(tree),
        "pkg": pkg,
        "dir": relpath.rsplit("/", 1)[0] if "/" in relpath else "",
        "loc": source.count("\n") + 1,
        "mtime": mtime,
        "commit": (commits or {}).get(relpath),
        "main": "__main__" in source,
        "imports": _imports(tree),
    }
    yield mod

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            yield _class(node, mod)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            rec = _method(node)
            rec.update({"k": "func", "lang": LANGUAGE, "repo": repo, "path": relpath,
                        "mtime": mod["mtime"], "commit": mod["commit"]})
            yield rec



def available(root: Path | None = None) -> str | None:
    """Always usable: the parser is in the standard library. That is the whole
    reason this skill has no dependencies and can be copied anywhere."""
    return None


def extract(files, root: Path, repo: str, commits=None):
    """Yield records for every file. Never raises on one bad file."""
    for path in files:
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            yield {"k": "unreadable", "lang": LANGUAGE, "repo": repo,
                   "path": rel(path, root), "error": str(exc)[:200]}
            continue
        yield from index_file(path, root, repo, source, commits)
