"""HTML templates: Django and Jinja, plus plain pages.

A template layer has a contract like any other, and it is already expressible in
the schema everything else uses -- no new record kind, no new query:

    {% extends "admin/base.html" %}   ->  a base class
    {% block content %}              ->  a method
    {% include "widgets/x.html" %}   ->  a call
    {% load i18n %}, <script src>    ->  an import

That mapping is the point. It means `shape --base admin/base.html` reports what
every page inheriting it overrides, `exemplars` picks the page worth copying,
and `imports --chain` follows template inheritance -- which is a registration
chain exactly like a package `__init__`: add a page, forget to extend the right
base or fill the expected block, and nothing errors. The page simply renders
wrong, or empty.

**Read by regex, and `FIDELITY` says so.** There is no template parser in the
standard library, and a heuristic extractor claiming "100% of pages do this" is
a weaker statement than an AST one making the same claim. Every reader of
`shape` is entitled to know which they are looking at.

Measured on 393 real templates from Django and Flask -- 94 `extends`, 285
`block`, 107 `include` -- which is where the two traps below came from.
"""

from __future__ import annotations

import re
from pathlib import Path

from _common import rel

LANGUAGE = "html"
FIDELITY = "heuristic"
EXTENSIONS = (".html", ".htm", ".jinja", ".jinja2", ".j2", ".twig")

# `block` requires whitespace before the name. Without it this matches
# `{% blocktranslate %}`, which is not a block and occurs 25 times in the
# sample -- inventing a block named "translate" on pages that have none.
EXTENDS = re.compile(r'\{%-?\s*extends\s+["\']([^"\']+)["\']')
BLOCK = re.compile(r'\{%-?\s*block\s+([A-Za-z_][\w-]*)')
ENDBLOCK = re.compile(r'\{%-?\s*endblock\b')
INCLUDE = re.compile(r'\{%-?\s*include\s+["\']([^"\']+)["\']')
# `{% include widget.template_name %}` -- the target is a variable, decided at
# render time. Counted, never resolved: the same honesty as a C# instance call
# whose receiver is a field rather than a type.
INCLUDE_VAR = re.compile(r'\{%-?\s*include\s+(?!["\'])([\w.]+)')
LOAD = re.compile(r'\{%-?\s*load\s+([^%]+?)\s*-?%\}')
JINJA_IMPORT = re.compile(r'\{%-?\s*(?:import|from)\s+["\']([^"\']+)["\']')
SCRIPT_SRC = re.compile(r'<script[^>]*\ssrc\s*=\s*["\']([^"\']+)["\']', re.I)
LINK_HREF = re.compile(r'<link[^>]*\shref\s*=\s*["\']([^"\']+)["\']', re.I)


def available(root: Path | None = None) -> str | None:
    """Always usable: no toolchain, only the standard library."""
    return None


def template_name(relpath: str) -> str:
    """The name other templates refer to this one by.

    `{% extends "admin/base_site.html" %}` names a path relative to a templates
    root, not to the repository -- so the file at
    `django/contrib/admin/templates/admin/base_site.html` is `admin/base_site.html`
    to everything that inherits it. Resolving this is what makes `--base` and
    `imports` find anything at all. 290 of 393 real templates sit under a
    directory called `templates`; the rest keep their path.
    """
    marker = "/templates/"
    if marker in relpath:
        return relpath.rsplit(marker, 1)[1]
    if relpath.startswith("templates/"):
        return relpath[len("templates/"):]
    return relpath


def _blocks(lines: list[str]) -> list[dict]:
    """Blocks with the includes that occur inside them.

    An include is attributed to the block that contains it, because that is
    where it actually happens -- the page's `content` block pulling in a widget
    is a different statement from its `title` block doing so.
    """
    out: list[dict] = []
    stack: list[dict] = []
    for i, line in enumerate(lines, start=1):
        for m in BLOCK.finditer(line):
            block = {"name": m.group(1), "decorators": [], "params": [],
                     "returns": None, "line": i, "async": False,
                     "calls": [], "invokes": []}
            out.append(block)
            stack.append(block)
        for m in INCLUDE.finditer(line):
            target = m.group(1)
            if stack and target not in stack[-1]["invokes"]:
                stack[-1]["invokes"].append(target)
        for _ in ENDBLOCK.finditer(line):
            if stack:
                stack.pop()
    return out


def extract(files, root, repo, commits):
    for path in files:
        relpath = rel(Path(path), root)
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            yield {"k": "unreadable", "repo": repo, "path": relpath,
                   "error": str(exc)}
            continue

        lines = text.splitlines()
        try:
            mtime = int(Path(path).stat().st_mtime)
        except OSError:
            mtime = 0
        commit = commits.get(relpath, 0)

        parents = EXTENDS.findall(text)
        includes = INCLUDE.findall(text)
        unresolved = INCLUDE_VAR.findall(text)
        blocks = _blocks(lines)

        imports = []
        for mod in parents + includes + JINJA_IMPORT.findall(text):
            imports.append({"mod": mod, "name": None, "as": None})
        for raw in LOAD.findall(text):
            for lib in raw.split():
                imports.append({"mod": lib, "name": None, "as": None})
        for asset in SCRIPT_SRC.findall(text) + LINK_HREF.findall(text):
            imports.append({"mod": asset, "name": None, "as": None})

        name = template_name(relpath)
        yield {
            "k": "module", "lang": LANGUAGE, "repo": repo, "path": relpath,
            "pkg": "", "dir": relpath.rsplit("/", 1)[0] if "/" in relpath else "",
            "loc": len(lines), "mtime": mtime, "commit": commit, "main": False,
            # A template's blocks are what other templates may fill: its surface.
            "exports": [b["name"] for b in blocks],
            "imports": imports,
        }

        # A page with no directives and no assets says nothing worth a record.
        # Static markup is not a convention, and one record per marketing page
        # would drown the layer that has one.
        if not (parents or blocks or includes or imports):
            continue

        yield {
            "k": "class", "lang": LANGUAGE, "repo": repo, "path": relpath,
            "mtime": mtime, "commit": commit, "name": name,
            "bases": list(parents), "keywords": [], "decorators": [],
            "line": 1, "attrs": [], "assigns": [], "methods": blocks,
            "nested": [],
            # Not part of the shared contract, and deliberately kept: absence of
            # evidence must not read as absence of an include.
            "unresolved_includes": sorted(set(unresolved)),
        }
