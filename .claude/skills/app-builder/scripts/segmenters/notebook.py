"""Jupyter notebooks: JSON holding an ordered list of cells.

A `.ipynb` is a container in exactly the sense `.vue` is -- not a language, but a
file holding one. It is split here and the resulting spans are read by the
extractor that already handles that language, so nothing downstream learns a new
concept.

This matters more than the other containers because of *where* the code is. A
great deal of real pandas, numpy, scipy and TensorFlow usage exists only in
notebooks; a corpus indexed without them reports those technologies as barely
used, and absent evidence reads as absent convention.

Three things have to be right, and each is silent when wrong:

- **Outputs are not source.** A cell carries its last execution's output, which
  for a dataframe is text that looks a great deal like code and never ran as
  any. Only `cell.source` is read.
- **Magics and shell escapes are not Python.** `%matplotlib inline`, `!pip
  install pandas`, `?obj` are notebook syntax that `ast.parse` rejects, and one
  of them fails the whole cell -- so they are blanked, not deleted, which keeps
  every following line on the number it really has.
- **Line numbers are logical, and this is the one place they are.** Everywhere
  else `line` is a line in the file a reader would open. A `.ipynb` is JSON, so
  its file lines are `"cells": [{"cell_type": ...` -- there is no line in it that
  holds `import pandas`. What is reported instead is the line within the
  notebook's *code*, counting every cell's source and every markdown cell's
  height, which is what a notebook editor shows and the only number that means
  anything. Ordering and relative distance are exact; do not paste one into a
  text editor and expect the source.
"""

from __future__ import annotations

import json

EXTENSIONS = (".ipynb",)
FORMAT = "notebook"

# `nbformat` records the notebook's language here. A notebook is usually Python
# and is not always: R, Julia and .NET kernels all write `.ipynb`.
LANGUAGE_EXTENSION = {
    "python": ".py", "python3": ".py", "ipython": ".py", "ipython3": ".py",
    "typescript": ".ts", "javascript": ".js", "csharp": ".cs",
}


def _extension(nb: dict) -> str | None:
    meta = nb.get("metadata") or {}
    info = meta.get("language_info") or {}
    name = (info.get("name")
            or ((meta.get("kernelspec") or {}).get("language"))
            or ((meta.get("kernelspec") or {}).get("name"))
            or "python")
    return LANGUAGE_EXTENSION.get(str(name).strip().lower())


def _is_notebook_syntax(stripped: str) -> bool:
    # `%%capture` and `%%time` apply to the whole cell; the body after them is
    # ordinary code, so only the directive line goes -- same rule as `%`.
    if stripped.startswith(("%", "!", "?")):
        return True
    # `df?` and `df??` are introspection, not an expression.
    return stripped.endswith(("?", "??")) and not stripped.endswith(("'?", '"?'))


def _unclosed(text: str) -> int:
    """Bracket depth of a line, ignoring brackets inside string literals."""
    depth = 0
    quote = None
    i = 0
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        i += 1
    return depth


def _clean_cell(body: str) -> list[str]:
    """A code cell's lines, with notebook-only syntax blanked out.

    Blanked rather than dropped: deleting a line shifts every line after it, and
    a record that points one line off is harder to distrust than one that is
    plainly wrong.

    A magic can span lines -- `%timeit np.fromiter((...),` continues onto the
    next -- so blanking only the first line leaves an orphaned continuation that
    fails the whole notebook with `unexpected indent`. Found in real notebooks,
    not imagined: two of sixty-seven in one corpus. So the blanking continues
    while brackets are open or a backslash continues the line.
    """
    out: list[str] = []
    carry = 0
    for line in body.splitlines():
        stripped = line.strip()
        if carry > 0:
            out.append("")
            carry += _unclosed(line)
            if carry <= 0 and not stripped.endswith("\\"):
                carry = 0
            continue
        if _is_notebook_syntax(line.lstrip()):
            out.append("")
            depth = _unclosed(line)
            carry = depth if depth > 0 else (1 if stripped.endswith("\\") else 0)
            continue
        out.append(line)
    return out


def segment(text: str):
    """`(extension, text, line_offset, role)` -- one span for the whole notebook.

    One span rather than one per cell, deliberately. Imports live in the first
    cell and are used twenty cells later; splitting per cell would produce
    twenty modules that each appear to import nothing, and every `--tech` filter
    would then miss the notebook entirely.
    """
    try:
        nb = json.loads(text)
    except ValueError:
        return
    if not isinstance(nb, dict):
        return
    ext = _extension(nb)
    cells = nb.get("cells")
    if not isinstance(cells, list):
        return
    if ext is None:
        # A kernel nothing here reads. Reported as its own extension so the
        # index counts it as not covered rather than silently dropping it.
        yield ".unknown-kernel", "", 0, "script"
        return

    lines: list[str] = []
    for cell in cells:
        if not isinstance(cell, dict):
            continue
        source = cell.get("source")
        if isinstance(source, list):
            body = "".join(source)
        elif isinstance(source, str):
            body = source
        else:
            body = ""
        if cell.get("cell_type") == "code":
            lines.extend(_clean_cell(body))
        else:
            # Markdown and raw cells hold no code, but they hold *lines*, and
            # the line numbers of everything below them depend on it.
            lines.extend("" for _ in body.splitlines() or [""])
        # nbformat does not require a trailing newline on the last line of a
        # cell, so the boundary is one line whether or not the source had one.
        lines.append("")

    yield ext, "\n".join(lines), 0, "script"
