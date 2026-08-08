"""Check that every extractor emits the same records.

The queries downstream read the schema and never ask what produced a record. That
only holds while the extractors agree, and nothing else checks that they do --
prose in `references/languages.md` is not enforcement. Where two extractors are
deliberately near-copies of each other, this is what keeps the copy honest.

    ./.venv/Scripts/python.exe .claude/skills/app-builder/scripts/selftest.py

Every language gets a fixture exercising the same shapes: an import, a class with
a base and a typed member, a method that calls something, and a free function.
The assertion is that the required keys are present -- extras are allowed, since
a language may carry detail the others cannot.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import segmenters
from _common import INDEX_ENV, configured_repositories
from extractors import REGISTRY

REQUIRED = {
    "module": {"k", "lang", "repo", "path", "pkg", "dir", "loc", "mtime",
               "commit", "main", "exports", "imports"},
    "class": {"k", "lang", "repo", "path", "mtime", "commit", "name", "bases",
              "keywords", "decorators", "line", "end", "attrs", "assigns",
              "methods", "nested"},
    "func": {"k", "lang", "repo", "path", "mtime", "commit", "name",
             "decorators", "params", "returns", "line", "end", "async", "calls",
             "invokes"},
}
ATTR_KEYS = {"name", "ann", "call", "args", "kw"}
METHOD_KEYS = {"name", "decorators", "params", "returns", "line", "end",
               "async", "calls", "invokes"}
IMPORT_KEYS = {"mod", "name", "as"}

FIXTURES = {
    "python": ("fixture.py", '''
from collections import OrderedDict


class Widget(Base):
    size: int = 0

    def render(self, target):
        target.draw(self.size)
        return helper(self.size)


def helper(n):
    return OrderedDict(n=n)
'''),
    "typescript": ("fixture.ts", '''
import { Base } from "./base";

export class Widget extends Base {
  size: number = 0;

  render(target: Target): string {
    target.draw(this.size);
    return helper(this.size);
  }
}

export function helper(n: number): string { return String(n); }
'''),
    "javascript": ("fixture.js", '''
import { Base } from "./base";

export class Widget extends Base {
  size = 0;

  render(target) {
    target.draw(this.size);
    return helper(this.size);
  }
}

export function helper(n) { return String(n); }
'''),
    # Not code, and deliberately held to the same contract. A template family's
    # inheritance is a base class, its blocks are methods and its includes are
    # calls -- if that mapping ever stops holding, every query over a template
    # family quietly describes something else.
    "html": ("fixture.html", '''
{% extends "base.html" %}
{% load i18n %}

{% block title %}Fixture{% endblock %}

{% block content %}
  {% include "widgets/helper.html" %}
  {% blocktranslate %}not a block{% endblocktranslate %}
  <button hx-post="/save" hx-swap="outerHTML" @click="open = !open">Go</button>
  <img data-hx-get="/thumb" alt="normalised to hx-get">
  <svg><use xlink:href="#icon"/></svg>
{% endblock %}
'''),
    # A stylesheet, held to the same contract: `@extend` is a base, `@mixin` a
    # method, `@include` a call, `$var` and `--token` attributes with values.
    "css": ("fixture.scss", '''
@import "base";

$widget-size: 1rem;

%placeholder { color: red; }

@mixin widget-render($target) {
  @include helper($target);
}

.widget {
  @extend %placeholder;
  --#{$prefix}widget-size: #{$widget-size};
  @include widget-render(1);
}
'''),
    "csharp": ("Fixture.cs", '''
using System.Collections.Generic;

namespace Fixtures;

public class Widget : Base
{
    public int Size { get; set; }

    public string Render(Target target)
    {
        target.Draw(Size);
        return Helper(Size);
    }

    public static string Helper(int n) => n.ToString();
}
'''),
}


def check(language, extractor, root: Path) -> list[str]:
    problems = []
    name, source = FIXTURES.get(language, (None, None))
    if name is None:
        return [f"{language}: no fixture -- add one when adding a language"]

    path = root / name
    path.write_text(source.lstrip(), encoding="utf-8")

    records = list(extractor.extract([path], root, "selftest", {}))
    kinds = {r.get("k") for r in records}

    for rec in records:
        kind = rec.get("k")
        if kind in ("unparsed", "unreadable"):
            problems.append(f"{language}: fixture did not parse -- "
                            f"{rec.get('error', '')[:120]}")
            continue
        want = REQUIRED.get(kind)
        if want is None:
            continue
        missing = want - set(rec)
        if missing:
            problems.append(f"{language}: {kind} record missing {sorted(missing)}")
        if rec.get("lang") != language:
            problems.append(f"{language}: {kind} record says lang="
                            f"{rec.get('lang')!r}")

        for a in rec.get("attrs", []):
            if ATTR_KEYS - set(a):
                problems.append(f"{language}: attr missing {sorted(ATTR_KEYS - set(a))}")
                break
        for m in rec.get("methods", []):
            if METHOD_KEYS - set(m):
                problems.append(f"{language}: method missing "
                                f"{sorted(METHOD_KEYS - set(m))}")
                break
        for i in rec.get("imports", []):
            if IMPORT_KEYS - set(i):
                problems.append(f"{language}: import missing "
                                f"{sorted(IMPORT_KEYS - set(i))}")
                break

    # htmx and Alpine put an application's behaviour in attributes. Reading a
    # template without them describes an interactive page as static, so the
    # mapping is asserted rather than assumed: name in `attrs` for `shape`, and
    # in `calls` for `practice`, with the two spellings that are easy to get
    # wrong -- `data-hx-get` is the same convention as `hx-get`, and
    # `xlink:href` is not a binding however much it looks like one.
    if language == "html":
        cls = next((r for r in records if r.get("k") == "class"), None)
        names = {a["name"] for a in (cls or {}).get("attrs", ())}
        called = {c[0] for c in (cls or {}).get("calls", ())}
        for want in ("hx-post", "hx-swap", "@click", "hx-get"):
            if want not in names:
                problems.append(f"html: directive {want!r} not in attrs; got {sorted(names)}")
            if want not in called:
                problems.append(f"html: directive {want!r} not in calls")
        if any(n.startswith("xlink") or n == ":href" for n in names):
            problems.append("html: an XML namespace was read as a binding")
        swap = next((a["call"] for a in (cls or {}).get("attrs", ())
                     if a["name"] == "hx-swap"), None)
        if swap != "outerHTML":
            problems.append(f"html: hx-swap value not kept, got {swap!r}")

    if "module" not in kinds:
        problems.append(f"{language}: emitted no module record")
    if "class" not in kinds:
        problems.append(f"{language}: emitted no class record for a class")

    # The fixture's class calls a method on a parameter and a free function.
    # Both must be visible, because a family's conventions live in what it calls.
    cls = next((r for r in records if r.get("k") == "class"), None)
    if cls is not None:
        if not cls["bases"]:
            problems.append(f"{language}: class record lost its base")
        # Every entry is `[name, line]`. Asserting the pair shape here is the
        # point: six extractors have to agree on it, and a bare string from any
        # one of them would make `calls` report the wrong line rather than fail.
        pairs = [e for m in cls["methods"]
                 for e in (*m.get("calls", []), *m.get("invokes", []))]
        bad = [e for e in pairs
               if not (isinstance(e, list) and len(e) == 2
                       and isinstance(e[0], str) and isinstance(e[1], int))]
        if bad:
            problems.append(f"{language}: call entries are not [name, line] "
                            f"pairs, e.g. {bad[0]!r}")
        calls = {e[0] for m in cls["methods"] for e in m.get("calls", [])
                 if isinstance(e, list)}
        invokes = {e[0] for m in cls["methods"] for e in m.get("invokes", [])
                   if isinstance(e, list)}
        lines = {e[1] for e in pairs if isinstance(e, list) and len(e) == 2}
        if lines and min(lines) < 1:
            problems.append(f"{language}: a call reported line {min(lines)}")
        # `calls` is a receiver-and-method idea, and a markup language has no
        # such thing. A heuristic extractor is not held to a claim it does not
        # make -- but it is still held to recording what it *does* claim.
        if extractor.FIDELITY == "ast":
            if not any(c.endswith((".draw", ".Draw")) for c in calls):
                problems.append(f"{language}: method call not recorded, "
                                f"saw {sorted(calls)}")
        if not any("helper" in i.lower() for i in invokes):
            problems.append(f"{language}: bare call not recorded, saw {sorted(invokes)}")

    if language == "css":
        # The trap real design systems set: every token is written
        # `--#{$prefix}name`, and a pattern wanting `--[a-z]` finds almost none
        # of them. The interpolation is stripped from the name so that one
        # token groups as one across a whole system.
        attrs = {a["name"] for r in records if r.get("k") == "class"
                 for a in r["attrs"]}
        if "--widget-size" not in attrs:
            problems.append(f"css: interpolated custom property not recorded as "
                            f"`--widget-size`; got {sorted(attrs)}")
        values = {a["name"]: a["ann"] for r in records if r.get("k") == "class"
                  for a in r["attrs"]}
        if values.get("$widget-size") != "1rem":
            problems.append(f"css: variable lost its value, got "
                            f"{values.get('$widget-size')!r}")

    if language == "html":
        # The two traps real templates set, asserted rather than remembered.
        names = {m["name"] for r in records if r.get("k") == "class"
                 for m in r["methods"]}
        if any("translat" in n for n in names):
            problems.append(f"html: `blocktranslate` was read as a block "
                            f"named {sorted(n for n in names if 'translat' in n)}")
        if names != {"title", "content"}:
            problems.append(f"html: blocks were {sorted(names)}, expected "
                            f"title and content")

    return problems


def borrow_toolchains(root: Path) -> list[str]:
    """Point compiler-hungry extractors at one they can reach.

    The fixtures live in a temporary directory, so walking up for a compiler
    finds nothing. Rather than weaken the extractors, borrow one from a
    configured codebase -- which is also the answer for a checkout whose
    dependencies were never installed.
    """
    notes = []
    for extractor in REGISTRY.values():
        finder = getattr(extractor, "find_parser", None) \
            or getattr(extractor, "find_typescript", None)
        env = getattr(extractor, "ENV_OVERRIDE", None)
        if finder is None or env is None or os.environ.get(env):
            continue
        if finder(root):
            continue
        relative = getattr(extractor, "PARSER_RELATIVE_PATH", None)
        found = None
        for repo in configured_repositories():
            if not repo["exists"] or not relative:
                continue
            # Downward, not upward. A solution installs its frontend's compiler
            # below the repository root, which is exactly why `find_parser`
            # walking up cannot see it from here.
            for depth in ("", "*/", "*/*/", "*/*/*/"):
                found = next(repo["path"].glob(f"{depth}{relative}"), None)
                if found:
                    break
            if found:
                os.environ[env] = str(found)
                notes.append(f"borrowed the {extractor.LANGUAGE} parser from "
                             f"{repo['name']}")
                break
    return notes


# A container fixture per format, each carrying a definition on a line whose
# real number is known. The line offset is the thing being tested: a record
# pointing at the wrong line of the right file looks correct and is not, and no
# other check in this repository would catch it.
CONTAINERS = {
    "vue": ("fixture.vue", """<template>
  <div>
    <template v-if="x">nested, and not a top-level block</template>
  </div>
</template>

<script>
export function widgetHelper(n) {
  return n;
}
</script>

<style scoped>
.a { color: red; }
</style>
""", "widgetHelper", 8),
    "svelte": ("fixture.svelte", """<script>
  export function widgetHelper(n) {
    return n;
  }
</script>

<div>markup</div>

<style>
  .a { color: red; }
</style>
""", "widgetHelper", 2),
    "razor": ("fixture.razor", """@page "/x"
<h1>markup</h1>

@code {
    private string Name { get; set; }

    private void Go()
    {
    }
}
""", "Go", 7),
}


# Built rather than written out, because a notebook fixture is JSON containing
# escaped source and hand-writing one is how you get a test that passes for the
# wrong reason. The layout is deliberate: a markdown cell contributes height but
# no code, a magic and a shell escape must be blanked rather than removed, and
# an output that looks like an import must not be read. `summarise` then sits on
# a line that only holds if all four are handled.
def _notebook_fixture() -> tuple[str, int]:
    import json as _json
    nl = "\n"
    nb = {
        "metadata": {"language_info": {"name": "python"}},
        "cells": [
            {"cell_type": "markdown",
             "source": ["# Title" + nl, "prose" + nl]},
            {"cell_type": "code",
             "source": ["%matplotlib inline" + nl,
                        "import pandas as pd" + nl,
                        "import numpy as np" + nl],
             "outputs": [{"text": ["import must_not_be_read" + nl]}]},
            {"cell_type": "code",
             "source": ["!pip install scipy" + nl,
                        "df = pd.DataFrame()" + nl,
                        "df.head?" + nl,
                        "def summarise(frame):" + nl,
                        "    return frame.describe()" + nl]},
        ],
    }
    #  1 markdown   2 markdown   3 boundary
    #  4 %magic     5 import     6 import     7 boundary
    #  8 !shell     9 df=       10 df.head?  11 def summarise
    return _json.dumps(nb), 11


CONTAINERS["notebook"] = ("fixture.ipynb", _notebook_fixture()[0],
                          "summarise", _notebook_fixture()[1])


def check_container(fmt: str, root: Path) -> list[str]:
    """Segment a fixture, extract it, and assert the line survives the trip."""
    import index as index_module

    filename, text, want_name, want_line = CONTAINERS[fmt]
    path = root / filename
    path.write_text(text, encoding="utf-8")
    segmenter = segmenters.for_path(path)
    if segmenter is None:
        return [f"{fmt}: no segmenter claims {filename}"]

    problems, uncovered, skipped = [], {}, []
    records = list(index_module.extract_containers([path], root, "selftest", {},
                                                   uncovered, skipped))
    if skipped:
        return []          # toolchain missing; reported by the caller
    # A definition is a record in some languages and a member of a class record
    # in others -- Razor wraps its `@code` block in one. Both must land on the
    # right line, so both are searched.
    named = [r for r in records if r.get("name") == want_name]
    named += [m for r in records for m in (r.get("methods") or ())
              if m.get("name") == want_name]
    nested = [r for r in records
              if r.get("k") == "module" and r["path"] != filename]
    if nested:
        problems.append(f"{fmt}: records escaped onto {nested[0]['path']!r}, "
                        f"not the container file")
    if not named:
        found = sorted({r.get("name") for r in records if r.get("name")})
        problems.append(f"{fmt}: {want_name!r} not found; got {found}")
    else:
        got = named[0].get("line")
        if got != want_line:
            problems.append(f"{fmt}: {want_name!r} reported at line {got}, "
                            f"but it is on line {want_line} of the file")
    modules = [r for r in records if r.get("k") == "module"]
    if len(modules) > 1:
        problems.append(f"{fmt}: {len(modules)} module records for one file -- "
                        f"it would count as {len(modules)} files")
    return problems


# ---------------------------------------------------------------- queries


def _module(repo, path, imports, when):
    return {"k": "module", "lang": "python", "repo": repo, "path": path,
            "pkg": "", "dir": path.rsplit("/", 1)[0] if "/" in path else "",
            "loc": 10, "mtime": when, "commit": when, "main": False,
            "exports": [], "imports": [{"mod": m, "name": None, "as": None}
                                       for m in imports]}


def _func(repo, path, name, when, invokes=(), params=()):
    """A module-level function record -- a component, a hook, a handler.

    Its conventions live in what it *calls*, which is why `invokes` is the
    interesting field and why a family of these has a contract at all.
    """
    return {"k": "func", "lang": "typescript", "repo": repo, "path": path,
            "mtime": when, "commit": when, "name": name, "decorators": [],
            "params": list(params), "returns": None, "line": 1, "end": 9,
            "async": False, "calls": [],
            "invokes": [[i, 2] for i in invokes]}


def _class(repo, path, name, when, ann="int", methods=(), bases=("Base",)):
    return {"k": "class", "lang": "python", "repo": repo, "path": path,
            "mtime": when, "commit": when, "name": name, "bases": list(bases),
            "keywords": [], "decorators": [], "line": 1, "end": 9,
            "attrs": [{"name": "id", "ann": ann, "call": "", "args": [], "kw": []}],
            "assigns": [],
            "methods": [{"name": m, "decorators": [], "params": [],
                         "returns": None, "line": 2, "end": 3, "async": False,
                         "calls": [], "invokes": []} for m in methods],
            "nested": []}


def build_query_fixture() -> Path:
    """A tiny index with all three roles, written straight into a scratch tree.

    Synthetic rather than derived from a real codebase on purpose: these checks
    are about *invariants that must hold whatever is indexed*, and a fixture
    that can be reasoned about completely is the only way to assert them
    exactly. `ex` is the exemplar, `ref` the reference, `tgt` the target.

    Isolated by `APP_BUILDER_INDEX`, which the caller sets before this runs.
    That isolation is not a convenience: there is one index location now, so a
    fixture written without it would overwrite the real index -- a selftest
    that destroys the thing it is testing.

    The roles are expressed the only way they can be, by which directory each
    repository is written into. There is no roles map to write, which is
    itself the property under test: a fixture *cannot* construct the
    disagreement between an index and its metadata that used to be possible.

    Dates are chosen so `practice` has a fossil to find: `ex` last touched
    `oldlib` well over a year before it last touched `newlib`, which is the
    condition its AGEING branch tests for and which nothing else exercises.
    """
    import json
    import time

    from _common import index_file, index_meta, index_path, index_root, rollup_path

    now = int(time.time())
    two_years = now - 2 * 365 * 24 * 3600

    records = [
        # exemplar: uses both, but its oldlib modules are ancient -- and it
        # genuinely favours oldlib rather than tying, so `DISAGREES` below is a
        # measurement and not an artefact of which token was typed first.
        _module("ex", "app/a.py", ["oldlib"], two_years),
        _module("ex", "app/b.py", ["oldlib"], two_years),
        _module("ex", "app/f.py", ["oldlib"], two_years),
        _module("ex", "app/c.py", ["newlib"], now),
        # deep import, and a near-miss that must not be claimed by it
        _module("ex", "app/d.py", ["newlib/sub/thing"], now),
        _module("ex", "app/e.py", ["newlib-other"], now),
        # exemplar models: `touch` is a two-of-three convention and `id` has
        # one minority form, so `questions` gets a candidate the target
        # settles (attrdetail-id) and one it leaves live (method-touch).
        _class("ex", "app/models/One.py", "One", now, ann="UUID",
               methods=("touch",)),
        _class("ex", "app/models/Sibling.py", "Sibling", now, ann="UUID",
               methods=("touch",)),
        _class("ex", "app/models/Third.py", "Third", now, ann="str"),
        # A near-miss base and a generic one. `--base Base` must find the
        # generic and must NOT find `BaseModel`, which substring matching
        # blended into the same family for a long time.
        #
        # Deliberately outside `app/models/`: these exist to test matching, and
        # putting them in the family the other fixtures measure changed its
        # ratios and silently retired an assertion elsewhere.
        _class("ex", "app/other/Generic.py", "Generic", now,
               bases=("Base[Student]",)),
        _class("ex", "app/other/Decoy.py", "Decoy", now, bases=("BaseModel",)),
        # reference: unanimously the new way, and far larger
        _module("ref", "src/x.py", ["newlib"], now),
        _module("ref", "src/y.py", ["newlib"], now),
        _module("ref", "src/z.py", ["newlib"], now),
        _class("ref", "src/models/Ref1.py", "Ref1", now),
        _class("ref", "src/models/Ref2.py", "Ref2", now),
        _class("ref", "src/models/Ref3.py", "Ref3", now),
        # A second reference, going the other way. One codebase each is a tie by
        # codebase while the module count still favours newlib 3 to 1 -- which
        # is the SPLIT case, and the case where naming a winner would be an
        # artefact of argument order rather than a measurement.
        _module("ref2", "src/legacy.py", ["oldlib"], now),
        # A registration chain, and a decoy for it. Two repositories own a
        # directory called `models`, which is entirely ordinary -- and the hop
        # after a barrel is a bare directory name, so an unscoped chain claims
        # the other codebase's file as part of this one's wiring.
        _module("ex", "app/models/__init__.py", ["Widget"], now),
        _module("ex", "app/registry.py", ["models"], now),
        _module("ex2", "app/wiring.py", ["models"], now),
        # A function family on the source side -- components, whose contract is
        # what they call. Every one calls `useConfig` and `useState`; the
        # generated pair on disk keeps `useState` and drops `useConfig`, which
        # is the silent departure `conform` exists to name.
        _module("ex", "ui/a.py", [], now),
        _module("ex", "ui/b.py", [], now),
        _func("ex", "ui/a.py", "Alpha", now, invokes=("useState", "useConfig")),
        _func("ex", "ui/b.py", "Beta", now, invokes=("useState", "useConfig")),
        # Two functions with nothing whatever in common, so their intersection
        # is empty and there is no contract to check. `conform` used to call
        # that "the target keeps everything the source contracts", which is
        # true, worthless, and indistinguishable from a clean pass.
        _module("ex", "misc/p.tsx", [], now),
        _module("ex", "misc/q.tsx", [], now),
        _func("ex", "misc/p.tsx", "P", now, invokes=("alpha",)),
        _func("ex", "misc/q.tsx", "Q", now, invokes=("beta",)),
        # The called-but-not-defined check, which is the thing this skill found
        # four dead call sites with and which nothing tested. `Ctrl` defines
        # `select` and not `where`; a caller uses both. That one dead line
        # imports cleanly, passes every linter, and raises only when it runs.
        _class("ex", "lib/ctrl.py", "Ctrl", now, methods=("select",)),
        {"k": "func", "lang": "python", "repo": "ex", "path": "app/uses.py",
         "mtime": now, "commit": now, "name": "run", "decorators": [],
         "params": [], "returns": None, "line": 1, "end": 9, "async": False,
         "calls": [["Ctrl.select", 3], ["Ctrl.where", 4]],
         "invokes": [["helper", 5]]},
        # Defined, and nothing calls or invokes it -- the other silent failure.
        _func("ex", "app/dead.py", "orphaned_helper", now),
        # manifests: one the exemplar declares, one only a reference declares.
        # The second must stay out of `deps` unless --references asks.
        {"k": "manifest", "repo": "ex", "path": "package.json", "mtime": now,
         "commit": 0, "ecosystem": "npm", "deps": {"leftpad": "^1.0.0"},
         "dev_deps": {}, "scripts": {"build": "tsc"}},
        {"k": "manifest", "repo": "ref", "path": "package.json", "mtime": now,
         "commit": 0, "ecosystem": "npm", "deps": {"refpkg": "^2.0.0"},
         "dev_deps": {}, "scripts": {}},
    ]
    # No target. The generated application is not indexed any more -- it lives
    # on disk and is read fresh -- so a fixture that put one in the index would
    # be testing an arrangement that no longer exists. `build_target_tree`
    # writes the real files.
    roles = {"ex": "exemplar", "ex2": "exemplar", "ref": "reference",
             "ref2": "reference"}
    for repo, role in roles.items():
        mine = [r for r in records if r["repo"] == repo]
        index_path(role, repo).mkdir(parents=True, exist_ok=True)
        index_file(role, repo).write_text(
            "".join(json.dumps(r) + "\n" for r in mine), encoding="utf-8")
        index_meta(role, repo).write_text(json.dumps({
            "repo": repo, "role": role, "shallow": False,
            "files": sum(1 for r in mine if r["k"] == "module"),
            "classes": sum(1 for r in mine if r["k"] == "class"),
        }) + "\n", encoding="utf-8")
    # `ref` is recorded shallow, and `ex` deliberately is not. A shallow row's
    # dates are the moment it was fetched, and `practice` presented them as
    # last-touched signals for a long time -- while the manual told the reader
    # to weigh exactly those dates. Marked here so the marking cannot quietly
    # go away, and kept off `ex` because its row is asserted positionally.
    rollup_path().write_text(json.dumps({
        "repos": sorted(roles), "target": None, "roles": roles,
        "shallow": ["ref"],
    }) + "\n", encoding="utf-8")
    return index_root()


def build_target_tree() -> Path:
    """The generated application, as real files on disk.

    Not in the index, because the real one is not either. `conform` and
    `questions --target-path` read the target by walking and parsing it at the
    moment they are asked, so a fixture that handed them prepared records would
    exercise a path that no longer exists.

    Two families, each shaped to make one thing fail loudly if it regresses:
    the models agree on the form of `id` and disagree about `touch`, so one
    candidate is settled by the code and one stays a live question; and the
    components keep `useState` while dropping the `useConfig` that every source
    component calls.
    """
    root = Path(tempfile.mkdtemp(prefix="ab-target-"))
    (root / "app" / "models").mkdir(parents=True)
    (root / "ui").mkdir(parents=True)
    (root / "app" / "models" / "two.py").write_text(
        "class Two(Base):\n"
        "    id: UUID = mapped_column(Uuid, primary_key=True)\n"
        "\n"
        "    def touch(self):\n"
        "        return None\n", encoding="utf-8")
    (root / "app" / "models" / "four.py").write_text(
        "class Four(Base):\n"
        "    id: UUID = mapped_column(Uuid, primary_key=True)\n", encoding="utf-8")
    (root / "ui" / "c.py").write_text(
        "def Gamma():\n"
        "    useState()\n"
        "    useToast()\n", encoding="utf-8")
    (root / "ui" / "d.py").write_text(
        "def Delta():\n"
        "    useState()\n"
        "    useToast()\n", encoding="utf-8")
    return root


def run_query(*argv) -> str:
    import io
    import contextlib
    import query

    buf = io.StringIO()
    argv = list(argv)
    try:
        with contextlib.redirect_stdout(buf):
            query.main(argv)
    except SystemExit as exc:
        # argparse exits 2 on a usage error and prints to stderr, so the check
        # above it would otherwise see empty output and report a wrong verdict
        # rather than a broken call.
        if exc.code not in (0, None):
            return f"{buf.getvalue()}\n<command failed: {' '.join(argv)}>"
    return buf.getvalue()


def check_staleness() -> list[str]:
    """An index older than the code it describes must say so.

    The skill documents staleness as the expensive failure and then relies on
    the reader to remember: a contract computed from last week's index is
    wrong in the worst way, because it is plausible and specific and describes
    code that has since moved. Worth a test of its own since the detection is
    the only thing standing between that and silence.
    """
    import json
    import time

    import query
    from _common import index_meta

    bad = []
    tmp = Path(tempfile.mkdtemp(prefix="ab-stale-"))
    try:
        (tmp / "app").mkdir()
        source = tmp / "app" / "thing.py"
        source.write_text("class Thing: pass\n", encoding="utf-8")

        # A shard built *after* the source is current; one built before is not.
        for built, expect_stale in ((time.time() + 60, False),
                                    (time.time() - 3600, True)):
            stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(built))
            record = {"name": "probe", "path": tmp, "exists": True,
                      "exclude": (), "include": (), "is_target": False}
            meta = index_meta("exemplar", "probe")
            meta.parent.mkdir(parents=True, exist_ok=True)
            meta.write_text(json.dumps({"repo": "probe", "built": stamp}),
                            encoding="utf-8")
            # Exercised through the real entry point, with only the repository
            # list stubbed: what matters is what a query would actually print.
            query._STALE_CACHE = None
            original = query.configured_repositories
            query.configured_repositories = lambda: [record]
            try:
                stale = query.stale_repositories()
            finally:
                query.configured_repositories = original
                query._STALE_CACHE = None
            if expect_stale and "probe" not in stale:
                bad.append("staleness: a source newer than its shard was not "
                           "reported -- the index can silently describe code "
                           "that has moved")
            if not expect_stale and "probe" in stale:
                bad.append("staleness: an up-to-date index was reported stale, "
                           "which trains the reader to ignore the warning")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return bad


def check_corpus_guard() -> list[str]:
    """The corpus must not be walkable from a codebase that contains it.

    It lives inside the skill, so anything that walks the skill -- or the
    checkout above it -- passes right by twenty-three other people's
    repositories. `_is_skipped_dir` prunes it today only because the name
    starts with a dot, which is a naming coincidence rather than a rule, so
    this test removes the dot and asserts the guard still holds.

    Worth testing rather than reasoning about, because the failure is not an
    error. A reference swept in as an exemplar votes: it outnumbers the one
    codebase whose conventions were supposed to be the contract, and the output
    stays perfectly plausible while describing nobody's code.
    """
    import _common
    bad = []
    tmp = Path(tempfile.mkdtemp(prefix="ab-corpus-guard-"))
    corpus_dir, skill_root = _common.CORPUS_DIR, _common.skill_root
    try:
        (tmp / "mine").mkdir()
        (tmp / "mine" / "app.py").write_text("x = 1", encoding="utf-8")
        fake = tmp / "reference_corpus"
        (fake / "django" / "django").mkdir(parents=True)
        (fake / "django" / "django" / "models.py").write_text(
            "class Model: pass", encoding="utf-8")

        _common.CORPUS_DIR = "reference_corpus"   # the dot deliberately gone
        _common.skill_root = lambda: tmp
        if _common._is_skipped_dir("reference_corpus"):
            bad.append("corpus guard: fixture is not testing anything --"
                       " the name is still pruned by _is_skipped_dir")

        names = lambda root: sorted(
            p.name for p in _common.iter_source_files(root, 400_000,
                                                      extensions=(".py",)))
        outside = names(tmp)
        if "models.py" in outside:
            bad.append("corpus guard: walking a tree that CONTAINS the corpus"
                       f" reached a reference codebase -- got {outside}")
        if "app.py" not in outside:
            bad.append(f"corpus guard: the containing tree's own code was lost:"
                       f" {outside}")
        # One-directional: indexing a reference means the root is already
        # inside the corpus, and a guard that fired here would report every
        # reference as empty -- which `practice` would then read as evidence.
        inside = names(fake / "django")
        if "models.py" not in inside:
            bad.append("corpus guard: a reference indexed on its own came back"
                       f" empty -- the guard fires in both directions: {inside}")
    finally:
        _common.CORPUS_DIR, _common.skill_root = corpus_dir, skill_root
        shutil.rmtree(tmp, ignore_errors=True)
    return bad


def check_queries() -> list[str]:
    """The invariants no extractor test can reach.

    The first two matter most. A reference codebase leaking into a contract
    computation is silent, plausible-looking, and wrong in exactly the way this
    whole skill exists to prevent -- and it is one keyword argument away at all
    times.
    """
    import json as _json

    import query as _query

    bad = []
    # The generated application, on disk. Pointed at through the same call the
    # real commands use, so `read_target_fresh` walks a real tree.
    target_root = build_target_tree()
    _real_solution = _query.configured_solution
    _query.configured_solution = lambda: {
        "name": "tgt", "path": target_root, "exists": True,
        "exclude": (), "include": (), "repo": "", "rev": "",
        "role": "target", "is_target": True}
    _query._FRESH_CACHE.clear()
    try:
        return _check_queries(bad, _json)
    finally:
        _query.configured_solution = _real_solution
        _query._FRESH_CACHE.clear()
        shutil.rmtree(target_root, ignore_errors=True)


def _check_queries(bad, _json):

    # A repository's role is the directory it sits in, and this is the proof:
    # move the directory, change nothing else, and what the contract commands
    # can see changes with it.
    #
    # Worth a test of its own because it is the property that replaced the
    # roles map, and it is the reason that map could go. A map can disagree
    # with the index it describes -- be absent, be stale, name a repository
    # that is no longer there -- and when it did, every reference was silently
    # promoted to exemplar and the answers stayed plausible. A directory
    # cannot disagree about where it is.
    from _common import index_path, read_index

    seen = {r["repo"] for r in read_index()}
    if seen != {"ex", "ex2"}:
        bad.append(f"roles: contract commands should see the exemplars and"
                   f" nothing else, saw {sorted(seen)}")
    moved_from, moved_to = index_path("exemplar", "ex"), index_path("reference", "ex")
    shutil.move(str(moved_from), str(moved_to))
    try:
        seen = {r["repo"] for r in read_index()}
        if "ex" in seen:
            bad.append("roles: a repository moved into reference_corpus/ still"
                       " reached a contract computation -- the role is not the"
                       f" location, saw {sorted(seen)}")
        if "ex" not in {r["repo"] for r in read_index(include_references=True)}:
            bad.append("roles: a repository moved into reference_corpus/ became"
                       " invisible to `practice` too -- it should be evidence,"
                       " not gone")
    finally:
        shutil.move(str(moved_to), str(moved_from))

    out = run_query("shape", "--path", "*/models/*")
    if "ref" in out or "Ref1" in out:
        bad.append("shape: a reference repository reached a contract computation")
    if "One" not in out and "2 classes" not in out and "ex" not in out:
        bad.append(f"shape: expected the exemplar's classes, got:\n{out}")

    out = run_query("families")
    if "ref/" in out:
        bad.append("families: a reference repository was listed as a family")

    out = run_query("families", "--lang", "python")
    if "app" not in out:
        bad.append("families --lang: filtered everything out")

    out = run_query("practice", "--on", "oldlib", "--versus", "newlib")
    if "ref" not in out:
        bad.append("practice: did not read the reference corpus, which is its whole job")
    # A shallow row's dates are the date it was fetched. Presenting them as
    # last-touched, unmarked, is the failure -- the counts stay usable.
    if "ref *" not in out:
        bad.append(f"practice: a shallow repository's dates were shown as "
                   f"history, unmarked:\n{out}")
    if "shallow clone -- ref" not in out:
        bad.append(f"practice: nothing explained the mark:\n{out}")
    # Counted by codebase as well as by module, because one large repository
    # owns a module count outright.
    if "by codebase" not in out:
        bad.append(f"practice: no per-codebase verdict:\n{out}")
    # A tie is a result. `max()` breaks one by argument order, which reads as a
    # finding and is really an artefact of what the user typed first -- so a
    # tied count must say so rather than crowning whichever token came first.
    # Two reference codebases, one apiece, is exactly that.
    if "by codebase      tied" not in out:
        bad.append(f"practice: one codebase each was reported as a winner "
                   f"rather than a tie:\n{out}")
    # And the two ways of counting disagree, which is the whole reason the
    # second one exists.
    if "SPLIT" not in out:
        bad.append(f"practice: module count and codebase count disagree and it "
                   f"was not said:\n{out}")
    if "corpus favours   newlib" not in out:
        bad.append(f"practice: wrong corpus verdict:\n{out}")
    if "DISAGREES" not in out:
        bad.append(f"practice: exemplar disagrees with the corpus and it was not said:\n{out}")
    if "AGEING" not in out:
        bad.append(f"practice: a two-year-old convention did not trigger AGEING:\n{out}")

    # app/c.py imports `newlib` directly and app/d.py imports `newlib/sub/thing`.
    # Both are uses of the package: matching only whole specifiers reported
    # MUI's own demo gallery as 6 modules when it was 745. app/e.py imports
    # `newlib-other`, a different package, which the prefix must not claim --
    # without the separator, `react` would swallow `react-dom`.
    out = run_query("practice", "--on", "newlib")
    hits = [ln for ln in out.splitlines() if ln.strip().startswith("ex ")]
    if not hits or hits[0].split()[1] != "2":
        bad.append("practice: expected 2 modules for newlib (one direct, one "
                   f"subpath), got:{chr(10)}{out}")

    out = run_query("deps", "--on", "leftpad")
    if "^1.0.0" not in out:
        bad.append(f"deps --on: did not find a declared package:\n{out}")

    out = run_query("deps", "--repo", "tgt")
    if "declares no dependencies" not in out:
        bad.append(f"deps: a repo with no manifest should say so, not blame the index:\n{out}")

    # References are not who pays. A package only a reference declares must
    # read as "adding it" by default, and be visible on request.
    out = run_query("deps", "--on", "refpkg")
    if "nothing declares it" not in out:
        bad.append("deps: a package only a reference declares reached the "
                   f"default scope -- 'already paid for' would lie:\n{out}")
    out = run_query("deps", "--on", "refpkg", "--references")
    if "^2.0.0" not in out:
        bad.append(f"deps --references: the reference's manifest was not read:\n{out}")

    # One candidate the target settles, one it leaves live. The settled one is
    # read back exactly once -- it printed twice for a while, which reads as
    # twice the diligence and is the same information.
    out = run_query("questions", "--path", "*/models/*",
                    "--target-path", "app/models/*", "--target-repo", "tgt")
    if out.count("answered by the code already") != 1:
        bad.append("questions: the answered-by-code block must print exactly "
                   f"once:\n{out}")
    if "attrdetail-id" not in out:
        bad.append(f"questions: a form the target settled was not read back:\n{out}")
    if "method-touch" not in out:
        bad.append(f"questions: the live fork was not asked:\n{out}")

    # `exemplars` says "copy the structure of these", so the generated target
    # must not be among them unless asked for. Ranking your own output most
    # typical is how one mistake becomes the convention.
    # The generated app cannot reach this command at all now -- it is not in
    # the index -- but the exemplar's own files still must.
    out = run_query("exemplars", "--path", "app/models/*")
    if "tgt/" in out:
        bad.append(f"exemplars: the generated target was offered as a model "
                   f"to copy:\n{out}")
    if "ex/" not in out:
        bad.append(f"exemplars: the exemplar's own files were held out too:\n{out}")

    # Exact on the root, not a substring: `Base` is `Base` and `Base[Student]`,
    # and is not `BaseModel`.
    out = run_query("find", "--base", "Base")
    if "Generic" not in out:
        bad.append(f"--base: a generic base `Base[Student]` was not matched:\n{out}")
    if "Decoy" in out:
        bad.append(f"--base: `Base` matched `BaseModel` -- substring matching "
                   f"blends two families into one:\n{out}")
    out = run_query("find", "--base", "Base*")
    if "Decoy" not in out:
        bad.append(f"--base: an explicit wildcard did not match:\n{out}")

    # The called-but-not-defined check. This is the one that found four live
    # call sites for a method that never existed, and it had no test at all --
    # so a regression in it would have been invisible until it silently stopped
    # finding anything, which looks exactly like a clean codebase.
    out = run_query("calls", "--on", "Ctrl")
    if "where" not in out or "MISSING" not in out:
        bad.append(f"calls: a method called on Ctrl that Ctrl does not define "
                   f"was not reported:\n{out}")
    if "ex/app/uses.py:4" not in out:
        bad.append(f"calls: the dead call site was not located -- the line is "
                   f"the difference between a pointer and a search:\n{out}")
    if "ok       select" not in out:
        bad.append(f"calls: a method that does exist was not confirmed:\n{out}")

    # A name invoked directly has no member list to check against, and saying
    # "nothing calls anything on it" would read as dead code.
    out = run_query("calls", "--on", "helper")
    if "invoked directly" not in out:
        bad.append(f"calls: a directly-invoked name was not recognised as one:\n{out}")

    # Defined and never reached. Worth reporting, and worth the caveat it
    # prints: absence of a caller in this index is not absence of a caller.
    out = run_query("calls", "--on", "orphaned_helper")
    if "nothing in this index calls or invokes it" not in out:
        bad.append(f"calls: a definition nothing reaches was not reported:\n{out}")
    if "absence of a caller" not in out:
        bad.append(f"calls: reported dead code without the caveat that a public "
                   f"symbol is called from outside the index:\n{out}")

    # A schema stamp is only worth having if a disagreement is noticed. Both
    # directions matter: an index predating the field must not be reported as
    # broken -- that would fire on every existing index the day it shipped --
    # and one written by a different `index.py` must be.
    from _common import INDEX_SCHEMA, index_meta, index_schema_warning

    if index_schema_warning() is not None:
        bad.append("schema: an index with no stamp was reported as a mismatch; "
                   "unstamped means 'written before the field existed'")
    meta_file = index_meta("exemplar", "ex")
    original = meta_file.read_text(encoding="utf-8")
    try:
        claim = _json.loads(original)
        claim["schema"] = INDEX_SCHEMA + 99
        meta_file.write_text(_json.dumps(claim), encoding="utf-8")
        said = index_schema_warning()
        if not said or str(INDEX_SCHEMA + 99) not in said:
            bad.append(f"schema: an index written by a different index.py was "
                       f"not reported: {said!r}")
    finally:
        meta_file.write_text(original, encoding="utf-8")

    # Why a set has no dates, said correctly. Three causes reach the same
    # symptom -- not in git, indexed with --no-git, and a history git could not
    # read in time -- and the third was reported as the first, which sends the
    # reader to fix something that is not wrong. Asserted directly because it
    # only reproduces on a repository large enough to time out.
    import query as _query

    undated = [{"repo": "big", "commit": 0, "mtime": 1}]
    said = _query.date_provenance(undated, frozenset(),
                                  {"big": "`git log` did not finish in 900s"})
    if not said or "did not finish" not in said:
        bad.append(f"date_provenance: a recorded reason was discarded: {said!r}")
    if said and "nothing here is in git" in said:
        bad.append(f"date_provenance: blamed git for a repository that is in "
                   f"git: {said!r}")
    said = _query.date_provenance(undated, frozenset(), {})
    if not said or "nothing here is in git" not in said:
        bad.append(f"date_provenance: lost the ordinary no-git message: {said!r}")

    # A function family has a contract too, and until `--kind func` existed this
    # command could not see one -- every React, hook and handler family the skill
    # can generate had no step-8 check at all.
    out = run_query("conform", "--kind", "func", "--repo", "ex",
                    "--path", "ui/*", "--target-repo", "tgt",
                    "--target-path", "ui/*")
    if "useConfig" not in out:
        bad.append(f"conform --kind func: a call every source function makes "
                   f"and no generated one makes was not reported:\n{out}")
    if "DROPPED (0)" in out:
        bad.append(f"conform --kind func: reported nothing dropped when a "
                   f"contract call was dropped:\n{out}")
    if "useToast" not in out:
        bad.append(f"conform --kind func: a call universal in the target and "
                   f"absent from the source was not reported as ADDED:\n{out}")
    # The default is still classes, and asking for the wrong one says so
    # instead of reporting an empty family.
    out = run_query("conform", "--kind", "class", "--repo", "ex",
                    "--path", "ui/*", "--target-repo", "tgt",
                    "--target-path", "ui/*")
    if "--kind func" not in out:
        bad.append(f"conform: a filter matching only functions did not point "
                   f"at --kind func:\n{out}")
    # An empty intersection is not a pass. "The target keeps everything the
    # source contracts" is true and worthless when the source contracts
    # nothing, and it reads exactly like a clean result.
    out = run_query("conform", "--kind", "func", "--repo", "ex",
                    "--path", "misc/*", "--target-repo", "tgt",
                    "--target-path", "ui/*")
    if "NOTHING TO CHECK" not in out:
        bad.append(f"conform: a source with no common feature was checked as "
                   f"though it had a contract:\n{out}")
    if "keeps everything the source contracts" in out:
        bad.append(f"conform: a vacuous check was worded as a clean pass:\n{out}")
    # ...and a genuinely conforming target still reads as one.
    out = run_query("conform", "--repo", "ex", "--path", "app/models/*",
                    "--target-repo", "tgt", "--target-path", "app/models/*")
    if "keeps everything the source contracts" not in out:
        bad.append(f"conform: a real clean pass stopped saying so:\n{out}")

    # `--json` is a contract with a machine, so it is worth pinning as one:
    # parseable, nothing but JSON on stdout, and the one field a caller cannot
    # reconstruct. An empty `dropped` means "nothing was broken" or "nothing
    # was checked" depending on `contract_empty`, and a gate that confuses them
    # reports a green build for a check that never ran.
    raw = run_query("conform", "--kind", "func", "--repo", "ex",
                    "--path", "misc/*", "--target-repo", "tgt",
                    "--target-path", "ui/*", "--json")
    try:
        payload = _json.loads(raw)
    except ValueError:
        payload = None
        bad.append(f"conform --json: stdout was not parseable JSON:\n{raw}")
    if payload is not None:
        if not payload.get("contract_empty"):
            bad.append("conform --json: a vacuous check reported "
                       "contract_empty false -- a gate would read it as a pass")
        if payload.get("dropped"):
            bad.append(f"conform --json: dropped rows from an empty contract: "
                       f"{payload['dropped']}")

    raw = run_query("conform", "--kind", "func", "--repo", "ex",
                    "--path", "ui/*", "--target-repo", "tgt",
                    "--target-path", "ui/*", "--json")
    try:
        payload = _json.loads(raw)
    except ValueError:
        payload = None
        bad.append(f"conform --json: stdout was not parseable JSON:\n{raw}")
    if payload is not None:
        if payload.get("contract_empty"):
            bad.append("conform --json: a real contract reported as empty")
        items = {d["item"] for d in payload.get("dropped") or ()}
        if "useConfig" not in items:
            bad.append(f"conform --json: the dropped contract call is missing "
                       f"from the machine-readable result: {sorted(items)}")

    raw = run_query("questions", "--path", "app/models/*",
                    "--target-path", "app/models/*", "--target-repo", "tgt",
                    "--json")
    try:
        payload = _json.loads(raw)
    except ValueError:
        payload = None
        bad.append(f"questions --json: stdout was not parseable JSON:\n{raw}")
    if payload is not None and not payload.get("settled_by_code"):
        bad.append("questions --json: what the target already answers was not "
                   "reported, so a consumer would ask it again")

    # A filter matching nothing is a result too, and it has to be parseable --
    # a mistyped path must not reach a gate as prose, and must not read as
    # "no drops, therefore pass".
    for cmd, key in ((("conform", "--repo", "ex", "--path", "nowhere/*",
                       "--target-repo", "tgt", "--target-path", "ui/*",
                       "--json"), "contract_empty"),
                     (("questions", "--path", "nowhere/*", "--json"), None)):
        raw = run_query(*cmd)
        try:
            got = _json.loads(raw)
        except ValueError:
            bad.append(f"{cmd[0]} --json: a filter that matched nothing printed "
                       f"prose to a machine-readable stream:\n{raw}")
            continue
        if not got.get("error"):
            bad.append(f"{cmd[0]} --json: an empty result did not say why")
        if key and not got.get(key):
            bad.append(f"{cmd[0]} --json: a typo'd path would read as a clean "
                       f"pass -- {key} was not set")

    # `--json` has to stay pure JSON when something *wants* to warn. The
    # staleness notice is printed above the answer for a person, and printing
    # it above a payload would break every parser precisely when the index is
    # stale -- the moment a gate most needs a usable answer. Forced, because
    # the fixture is never stale and so never exercises the branch.
    import query as _q

    original = _q.stale_repositories
    _q.stale_repositories = lambda *a, **k: ["ex"]
    try:
        for cmd in (("conform", "--kind", "func", "--repo", "ex",
                     "--path", "ui/*", "--target-repo", "tgt",
                     "--target-path", "ui/*", "--json"),
                    ("questions", "--path", "app/models/*", "--json")):
            raw = run_query(*cmd)
            try:
                got = _json.loads(raw)
            except ValueError:
                bad.append(f"{cmd[0]} --json: a stale index put text on stdout, "
                           f"so the payload no longer parses:\n{raw}")
                continue
            if got.get("stale") != ["ex"]:
                bad.append(f"{cmd[0]} --json: staleness was not carried inside "
                           f"the document: {got.get('stale')!r}")
    finally:
        _q.stale_repositories = original

    # The generated app is not indexed, and its absence produces findings
    # rather than gaps: a symbol defined only there comes back as IMPORTED BY
    # (0), which reads as "nothing registers this" -- the exact conclusion the
    # command exists to deliver, reached because it cannot see the app.
    for cmd in (("imports", "Gamma"), ("calls", "--on", "Gamma")):
        out = run_query(*cmd)
        if "not indexed" not in out:
            bad.append(f"{cmd[0]}: reported on a symbol from the generated app "
                       f"without saying the app is not in the index -- a zero "
                       f"there reads as a finding:\n{out}")

    # A hop after a barrel is a bare directory name. Both repositories own one
    # called `models`, and only this repository's is part of this chain.
    out = run_query("imports", "Widget", "--chain")
    if "ex/app/registry.py" not in out:
        bad.append(f"imports --chain: the barrel hop was lost:\n{out}")
    if "tgt/app/wiring.py" in out:
        bad.append(f"imports --chain: a hop crossed into another repository -- "
                   f"it names files no edit here can reach:\n{out}")

    return bad


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="app-builder-selftest-"))
    failures, skipped = [], []
    try:
        for note in borrow_toolchains(root):
            print(f"  note {note}")
        for language, extractor in sorted(REGISTRY.items()):
            reason = extractor.available(root)
            if reason:
                skipped.append(f"{language}: {reason}")
                continue
            problems = check(language, extractor, root)
            status = "FAIL" if problems else "ok  "
            print(f"  {status} {language:<12} {extractor.FIDELITY}  "
                  f"{' '.join(extractor.EXTENSIONS)}")
            for p in problems:
                print(f"       {p}")
            failures += problems

        for fmt in sorted(CONTAINERS):
            problems = check_container(fmt, root)
            exts = " ".join(e for e, m in segmenters.BY_EXTENSION.items()
                            if m.FORMAT == fmt)
            print(f"  {'FAIL' if problems else 'ok  '} {fmt:<12} split {exts}")
            for p in problems:
                print(f"       {p}")
            failures += problems
        problems = check_corpus_guard()
        print(f"  {'FAIL' if problems else 'ok  '} {'corpus':<12} "
              f"not walkable from a codebase that contains it")
        for p in problems:
            print(f"       {p}")
        failures += problems

        # Pointed somewhere disposable *before* the fixture is built. There is
        # one index location now, so a fixture written without this would
        # overwrite whatever the user has actually indexed -- and it would
        # happen on a run whose whole purpose is to prove nothing is broken.
        ws = Path(tempfile.mkdtemp(prefix="ab-selftest-index-"))
        was = os.environ.get(INDEX_ENV)
        os.environ[INDEX_ENV] = str(ws)
        try:
            build_query_fixture()
            problems = check_queries()
            print(f"  {'FAIL' if problems else 'ok  '} {'queries':<12} "
                  f"roles, practice, deps, questions, exemplars, conform,"
                  f" --base, chain scope")
            for p in problems:
                print(f"       {p}")
            failures += problems

            # Inside the isolated index deliberately: it writes a probe shard,
            # and outside this block that lands in whatever the user has
            # actually indexed.
            problems = check_staleness()
            print(f"  {'FAIL' if problems else 'ok  '} {'staleness':<12} "
                  f"an index older than its source says so")
            for p in problems:
                print(f"       {p}")
            failures += problems
        finally:
            if was is None:
                os.environ.pop(INDEX_ENV, None)
            else:
                os.environ[INDEX_ENV] = was
            shutil.rmtree(ws, ignore_errors=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    for s in skipped:
        print(f"  skip {s}")
    print(f"\n{'FAILED' if failures else 'PASSED'} -- "
          f"{len(failures)} problem(s), {len(skipped)} extractor(s) unavailable")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
