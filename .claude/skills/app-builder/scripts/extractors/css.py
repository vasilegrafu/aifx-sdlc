"""Stylesheets: CSS, SCSS and Less.

A stylesheet family has a contract, and it is the same shape as any other once
you stop thinking of it as presentation:

    @import "mixins/banner"     ->  an import, and a chain like any other
    @mixin button-variant(...)  ->  a method
    @include button-variant(…)  ->  a call
    $card-spacer-y: 1rem        ->  an attribute, with its value
    --#{$prefix}card-bg: …      ->  an attribute -- the design token family

The two failures worth catching are the familiar ones wearing different
clothes. **A partial nobody imports does nothing** — no error, no style, and
the page simply looks wrong. And **a mixin defined but never included is dead**:
measured on Bootstrap, 80 mixins are defined and 62 distinct ones are ever
included, which `calls --on` finds mechanically.

**Read by regex, and `FIDELITY` says so.** A brace scanner is not a CSS parser.

`.sass` is deliberately absent: it is indentation-based rather than braced, so
this scanner would read it wrongly rather than not at all. It is reported as
not covered, which is the honest answer.
"""

from __future__ import annotations

import re
from pathlib import Path

from _common import rel

LANGUAGE = "css"
FIDELITY = "heuristic"
EXTENSIONS = (".css", ".scss", ".less")

IMPORT = re.compile(r'@(?:import|use|forward)\s+["\']([^"\']+)["\']')
MIXIN = re.compile(r'@(mixin|function)\s+([A-Za-z_][\w-]*)')
INCLUDE = re.compile(r'@include\s+([A-Za-z_][\w-]*)')
EXTEND = re.compile(r'@extend\s+([.%#][\w-]+)')
# `$card-spacer-y: 1rem;` -- a declaration at the start of a line, not the
# `$foo` inside someone else's value.
VARIABLE = re.compile(r'^\s*(\$[A-Za-z_][\w-]*)\s*:\s*([^;]+);', re.MULTILINE)
# Bootstrap writes every design token as `--#{$prefix}card-spacer-y`. A pattern
# wanting `--[a-z]` finds 15 of them where there are 548, and reports a token
# family that does not exist. The interpolation is part of the name.
CUSTOM_PROP = re.compile(r'^\s*(--[\w-]*(?:#\{[^}]*\}[\w-]*)*)\s*:\s*([^;]+);',
                         re.MULTILINE)
INTERPOLATION = re.compile(r'#\{[^}]*\}')
COMMENT_LINE = re.compile(r'//.*$', re.MULTILINE)
COMMENT_BLOCK = re.compile(r'/\*.*?\*/', re.DOTALL)


def available(root: Path | None = None) -> str | None:
    """Always usable: no toolchain, only the standard library."""
    return None


def stylesheet_name(relpath: str) -> str:
    """The name other stylesheets import this one by.

    `@import "mixins/banner"` names the file `scss/mixins/_banner.scss` -- no
    leading underscore, no extension. Recording the bare name is what lets
    `imports` match it, since a specifier's last segment is compared too.
    """
    stem = Path(relpath).stem
    return stem[1:] if stem.startswith("_") else stem


def _strip_comments(text: str) -> str:
    return COMMENT_LINE.sub("", COMMENT_BLOCK.sub("", text))


def _named_blocks(text: str) -> tuple[list[dict], list[str]]:
    """`@mixin`/`@function` definitions, and the includes made outside them.

    Includes are attributed to the mixin that contains them when there is one,
    because that is where the call happens. Everything else belongs to the
    stylesheet body, which is returned separately.
    """
    methods: list[dict] = []
    body: list[str] = []
    open_mixins: list[tuple[dict, int]] = []
    depth = 0
    line_no = 1
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\n":
            line_no += 1
            i += 1
            continue
        if ch == "{":
            depth += 1
            i += 1
            continue
        if ch == "}":
            depth -= 1
            while open_mixins and open_mixins[-1][1] > depth:
                open_mixins.pop()[0]["end"] = line_no
            i += 1
            continue
        m = MIXIN.match(text, i)
        if m:
            method = {"name": m.group(2), "decorators": [], "params": [],
                      "returns": None, "line": line_no, "end": line_no,
                      "async": False, "calls": [], "invokes": []}
            methods.append(method)
            open_mixins.append((method, depth))
            i = m.end()
            continue
        inc = INCLUDE.match(text, i)
        if inc:
            entry = [inc.group(1), line_no]
            if open_mixins:
                if entry not in open_mixins[-1][0]["invokes"]:
                    open_mixins[-1][0]["invokes"].append(entry)
            elif entry not in body:
                body.append(entry)
            i = inc.end()
            continue
        i += 1
    return methods, body


def extract(files, root, repo, commits):
    for path in files:
        relpath = rel(Path(path), root)
        try:
            raw = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            yield {"k": "unreadable", "repo": repo, "path": relpath,
                   "error": str(exc)}
            continue

        text = _strip_comments(raw)
        total_lines = raw.count("\n") + 1
        try:
            mtime = int(Path(path).stat().st_mtime)
        except OSError:
            mtime = 0
        commit = commits.get(relpath, 0)

        methods, body_includes = _named_blocks(text)
        imports = [{"mod": t, "name": None, "as": None}
                   for t in IMPORT.findall(text)]
        attrs = []
        for name, value in VARIABLE.findall(text):
            attrs.append({"name": name, "ann": value.strip()[:80],
                          "call": None, "args": [], "kw": []})
        for name, value in CUSTOM_PROP.findall(text):
            # The interpolation is dropped from the *name* only: `$prefix` is
            # one variable across a whole design system, so `--#{$prefix}card-bg`
            # and `--card-bg` are the same token and should group as one.
            attrs.append({"name": INTERPOLATION.sub("", name),
                          "ann": value.strip()[:80],
                          "call": None, "args": [], "kw": []})

        name = stylesheet_name(relpath)
        yield {
            "k": "module", "lang": LANGUAGE, "repo": repo, "path": relpath,
            "pkg": "", "dir": relpath.rsplit("/", 1)[0] if "/" in relpath else "",
            "loc": raw.count("\n") + 1, "mtime": mtime, "commit": commit,
            "main": False,
            "exports": [m["name"] for m in methods] + [a["name"] for a in attrs],
            "imports": imports,
        }

        if not (methods or attrs or imports or body_includes):
            continue

        yield {
            "k": "class", "lang": LANGUAGE, "repo": repo, "path": relpath,
            "mtime": mtime, "commit": commit, "name": name,
            "bases": sorted(set(EXTEND.findall(text))), "keywords": [],
            "decorators": [], "line": 1, "end": total_lines,
            "attrs": attrs, "assigns": [], "methods": methods, "nested": [],
        }

        if body_includes:
            # The stylesheet's own body: what it calls outside any mixin, which
            # on a real design system is most of the calls. A `func` record is
            # where `shape` looks for a family's vocabulary.
            yield {
                "k": "func", "lang": LANGUAGE, "repo": repo, "path": relpath,
                "mtime": mtime, "commit": commit, "name": name,
                "decorators": [], "params": [], "returns": None, "line": 1,
                "end": total_lines, "async": False,
                "calls": [], "invokes": body_includes,
            }
