"""HTML templates: Django and Jinja, plus plain pages.

A template family has a contract like any other, and it is already expressible in
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

# Behaviour written as markup. For htmx and Alpine this is not decoration around
# the logic -- it *is* the logic, and reading a template without it describes a
# page as static when every interaction on it lives in these attributes.
#
# Four spellings, and the leading boundary matters in each: requiring whitespace
# or `<` before the name stops `xlink:href` and `xmlns:x` matching the `:`
# shorthand, which would file every SVG in the project as a component with
# bindings.
#
#   hx-get, hx-target      htmx
#   x-data, x-show         Alpine
#   @click, @submit.prevent  event shorthand (Alpine, Vue)
#   :class, :value         binding shorthand
#
# `data-hx-*` is htmx's HTML-valid spelling of the same thing and is normalised
# to the short form, or the same convention would be reported as two.
DIRECTIVE = re.compile(
    r'(?:^|[\s<])(data-)?((?:hx|x)-[A-Za-z][\w:.-]*|[@:][A-Za-z][\w:.-]*)'
    r'\s*=\s*(["\'])(.*?)\3',
    re.S)

# Values worth recording. An endpoint differs on every page and would make every
# directive VARIES; a swap strategy or a trigger is drawn from a small set and is
# a real convention. So the value is kept only when it is short and has no path
# or template expression in it.
VALUE_MAX = 24


def _directives(text: str) -> list[dict]:
    """Behaviour attributes, as `{name, value, line}`, first occurrence each.

    Deduplicated by name on purpose. A table with forty rows carrying `@click`
    is one convention used forty times, and counting it forty times would make a
    single busy page outweigh every other template in the family -- the same
    reason a module is counted once however many classes it holds.
    """
    seen: dict[str, dict] = {}
    for m in DIRECTIVE.finditer(text):
        name = m.group(2)
        value = (m.group(4) or "").strip()
        if name in seen:
            continue
        keep = (value if value and len(value) <= VALUE_MAX
                and not any(c in value for c in "/{}<>\n") else "")
        seen[name] = {"name": name, "value": keep,
                      "line": text.count("\n", 0, m.start(2)) + 1}
    return list(seen.values())


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
                     "returns": None, "line": i, "end": i, "async": False,
                     "calls": [], "invokes": []}
            out.append(block)
            stack.append(block)
        for m in INCLUDE.finditer(line):
            entry = [m.group(1), i]
            if stack and entry not in stack[-1]["invokes"]:
                stack[-1]["invokes"].append(entry)
        for _ in ENDBLOCK.finditer(line):
            if stack:
                stack.pop()["end"] = i
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
        directives = _directives(text)

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
        # would drown the family that has one. A page carrying htmx or Alpine
        # behaviour counts even when it inherits nothing and includes nothing --
        # that behaviour is the reason it exists.
        if not (parents or blocks or includes or imports or directives):
            continue

        yield {
            "k": "class", "lang": LANGUAGE, "repo": repo, "path": relpath,
            "mtime": mtime, "commit": commit, "name": name,
            "bases": list(parents), "keywords": [], "decorators": [],
            "line": 1, "end": len(lines) or 1,
            # Two fields, and the split is deliberate rather than redundant.
            # `features()` reads `attrs` for a class and `calls` only for a
            # function, so `shape` sees each directive exactly once -- while
            # `practice` and `_mentions`, which read `calls`, can answer "does
            # anyone still use hx-boost". Recording it in one place would cost
            # one of those two.
            "attrs": [{"name": d["name"], "ann": None, "call": d["value"],
                       "args": [], "kw": []} for d in directives],
            "calls": [[d["name"], d["line"]] for d in directives],
            "assigns": [],
            "methods": blocks, "nested": [],
            # Not part of the shared contract, and deliberately kept: absence of
            # evidence must not read as absence of an include.
            "unresolved_includes": sorted(set(unresolved)),
        }
