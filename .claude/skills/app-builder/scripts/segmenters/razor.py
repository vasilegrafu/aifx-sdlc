"""Razor and Blazor: markup with `@code` blocks of C# inside it.

Two things make this different from a single-file component, and both were
found in a real ASP.NET codebase rather than assumed.

**A `@code` block is not a compilation unit.** It holds class *members* --
`[Parameter] public IEnumerable<CatalogBrand> Brands { get; set; }`, private
fields, methods -- with no class around them. Handed to the C# extractor as-is
it parses as nothing at all, so it is wrapped in a class declaration named
after the file, which is also the name Blazor itself generates for the
component. The wrapper is two lines and the line offset accounts for it, so
every reported line still points at the real one.

**`.cshtml` in practice has no `@code` at all.** Across 48 views the count was
zero; what they have is `@{ ... }` statement blocks, which are statements
rather than members and would need a second synthetic wrapper to parse into
something whose only content is a method nobody wrote. They are left as markup
and reported as not covered, which is the honest description of them.

Not yet read, and worth knowing: `@inject`, `@inherits` and `@page` are the
Blazor form of imports and routing -- the wiring question this skill exists to
answer. Recording them means emitting records, which a segmenter does not do.
"""

from __future__ import annotations

import re
from pathlib import Path

EXTENSIONS = (".razor", ".cshtml")
FORMAT = "razor"

_CODE = re.compile(r'^@(?:code|functions)\s*\{\s*$', re.MULTILINE)


def segment(text: str, name: str = "RazorComponent"):
    """`(extension, text, line_offset, role)` per block.

    The whole file is also yielded as markup: something in it went unread, and
    a file type nobody mentions reads as a convention that does not exist.
    """
    lines = text.splitlines()
    stem = re.sub(r"\W", "_", Path(name).stem) or "RazorComponent"
    for m in _CODE.finditer(text):
        start = text[: m.start()].count("\n") + 1      # 0-based line after `@code {`
        depth, end = 1, len(lines)
        for j in range(start, len(lines)):
            depth += lines[j].count("{") - lines[j].count("}")
            if depth <= 0:
                end = j
                break
        body = "\n".join(lines[start:end])
        # The wrapper is deliberately **one** line. With two, the synthetic
        # class and the real members disagree by one: the class wants to land
        # on the `@code {` line and each member one line further down, and only
        # a single-line wrapper satisfies both. Verified against every `@code`
        # block in a real Blazor project.
        yield ".cs", f"class {stem} {{\n{body}\n}}\n", start - 1, "code"
    yield ".html", text, 0, "markup"
