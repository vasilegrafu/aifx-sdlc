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
              "keywords", "decorators", "line", "attrs", "assigns", "methods",
              "nested"},
    "func": {"k", "lang", "repo", "path", "mtime", "commit", "name",
             "decorators", "params", "returns", "line", "async", "calls",
             "invokes"},
}
ATTR_KEYS = {"name", "ann", "call", "args", "kw"}
METHOD_KEYS = {"name", "decorators", "params", "returns", "line", "async",
               "calls", "invokes"}
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
        calls = {c for m in cls["methods"] for c in m.get("calls", [])}
        invokes = {i for m in cls["methods"] for i in m.get("invokes", [])}
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
    finally:
        shutil.rmtree(root, ignore_errors=True)

    for s in skipped:
        print(f"  skip {s}")
    print(f"\n{'FAILED' if failures else 'PASSED'} -- "
          f"{len(failures)} problem(s), {len(skipped)} extractor(s) unavailable")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
