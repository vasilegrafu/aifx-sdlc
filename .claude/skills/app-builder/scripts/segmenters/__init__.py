"""The segmenter registry: extension -> the thing that splits it.

A container format is one file holding several languages -- `.vue`, `.svelte`,
`.razor`, `.ipynb`. It is not a language and gets no extractor: it is split into spans
here, and each span is read by the extractor that already handles that
language. Nothing downstream knows a container was involved.

The one thing a segmenter must get right is the **line offset**. A record
whose `line` points into a temporary span rather than at the file the reader
will open is worse than no record, because it looks correct.
"""

from __future__ import annotations

from pathlib import Path

from . import notebook, razor, svelte, vue

REGISTRY = (vue, svelte, razor, notebook)

BY_EXTENSION = {ext: m for m in REGISTRY for ext in m.EXTENSIONS}

ALL_EXTENSIONS = tuple(BY_EXTENSION)


def for_path(path) -> object | None:
    return BY_EXTENSION.get(Path(str(path)).suffix.lower())
