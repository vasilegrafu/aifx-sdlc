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
from _common import configured_repositories
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
    # Not code, and deliberately held to the same contract. A template layer's
    # inheritance is a base class, its blocks are methods and its includes are
    # calls -- if that mapping ever stops holding, every query over a template
    # layer quietly describes something else.
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
    # Both must be visible, because a layer's conventions live in what it calls.
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


QUERY_INDEX = "_selftest"


def _module(repo, path, imports, when):
    return {"k": "module", "lang": "python", "repo": repo, "path": path,
            "pkg": "", "dir": path.rsplit("/", 1)[0] if "/" in path else "",
            "loc": 10, "mtime": when, "commit": when, "main": False,
            "exports": [], "imports": [{"mod": m, "name": None, "as": None}
                                       for m in imports]}


def _class(repo, path, name, when):
    return {"k": "class", "lang": "python", "repo": repo, "path": path,
            "mtime": when, "commit": when, "name": name, "bases": ["Base"],
            "keywords": [], "decorators": [], "line": 1, "end": 9,
            "attrs": [{"name": "id", "ann": "int", "call": "", "args": [], "kw": []}],
            "assigns": [], "methods": [], "nested": []}


def build_query_fixture() -> Path:
    """A tiny index with all three roles, written straight to the workspace.

    Synthetic rather than derived from a real codebase on purpose: these checks
    are about *invariants that must hold whatever is indexed*, and a fixture
    that can be reasoned about completely is the only way to assert them
    exactly. `ex` is the exemplar, `ref` the reference, `tgt` the target.

    Dates are chosen so `practice` has a fossil to find: `ex` last touched
    `oldlib` well over a year before it last touched `newlib`, which is the
    condition its AGEING branch tests for and which nothing else exercises.
    """
    import json
    import time

    from _common import workspace

    now = int(time.time())
    two_years = now - 2 * 365 * 24 * 3600
    ws = workspace(QUERY_INDEX)
    ws.mkdir(parents=True, exist_ok=True)

    records = [
        # exemplar: uses both, but its oldlib modules are ancient
        _module("ex", "app/a.py", ["oldlib"], two_years),
        _module("ex", "app/b.py", ["oldlib"], two_years),
        _module("ex", "app/c.py", ["newlib"], now),
        # deep import, and a near-miss that must not be claimed by it
        _module("ex", "app/d.py", ["newlib/sub/thing"], now),
        _module("ex", "app/e.py", ["newlib-other"], now),
        _class("ex", "app/models/One.py", "One", now),
        # reference: unanimously the new way, and far larger
        _module("ref", "src/x.py", ["newlib"], now),
        _module("ref", "src/y.py", ["newlib"], now),
        _module("ref", "src/z.py", ["newlib"], now),
        _class("ref", "src/models/Ref1.py", "Ref1", now),
        _class("ref", "src/models/Ref2.py", "Ref2", now),
        _class("ref", "src/models/Ref3.py", "Ref3", now),
        # target
        _class("tgt", "app/models/Two.py", "Two", now),
        # manifests
        {"k": "manifest", "repo": "ex", "path": "package.json", "mtime": now,
         "commit": 0, "ecosystem": "npm", "deps": {"leftpad": "^1.0.0"},
         "dev_deps": {}, "scripts": {"build": "tsc"}},
    ]
    (ws / "index.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    (ws / "meta.json").write_text(json.dumps({
        "name": QUERY_INDEX, "roles": {"ex": "exemplar", "ref": "reference",
                                       "tgt": "target"},
        "repos": ["ex", "ref", "tgt"], "target": "tgt", "shallow": [],
    }) + "\n", encoding="utf-8")
    return ws


def run_query(*argv) -> str:
    import io
    import contextlib
    import query

    buf = io.StringIO()
    # `--name` belongs to each subcommand, not to the parser, so the command
    # has to come first.
    argv = [argv[0], "--name", QUERY_INDEX, *argv[1:]]
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


def check_queries() -> list[str]:
    """The invariants no extractor test can reach.

    The first two matter most. A reference codebase leaking into a contract
    computation is silent, plausible-looking, and wrong in exactly the way this
    whole skill exists to prevent -- and it is one keyword argument away at all
    times.
    """
    bad = []

    out = run_query("shape", "--path", "*/models/*")
    if "ref" in out or "Ref1" in out:
        bad.append("shape: a reference repository reached a contract computation")
    if "One" not in out and "2 classes" not in out and "ex" not in out:
        bad.append(f"shape: expected the exemplar's classes, got:\n{out}")

    out = run_query("layers")
    if "ref/" in out:
        bad.append("layers: a reference repository was listed as a layer")

    out = run_query("layers", "--lang", "python")
    if "app" not in out:
        bad.append("layers --lang: filtered everything out")

    out = run_query("practice", "--on", "oldlib", "--versus", "newlib")
    if "ref" not in out:
        bad.append("practice: did not read the reference corpus, which is its whole job")
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
        ws = None
        try:
            ws = build_query_fixture()
            problems = check_queries()
            print(f"  {'FAIL' if problems else 'ok  '} {'queries':<12} "
                  f"roles, practice, deps, layers --lang")
            for p in problems:
                print(f"       {p}")
            failures += problems
        finally:
            if ws is not None:
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
