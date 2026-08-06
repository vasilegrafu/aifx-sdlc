"""The extractor registry: extension -> the thing that reads it.

Everything downstream of the index reads records and never asks what produced
them, so a language is added here and nowhere else. See
`references/languages.md` for the mapping each extractor must honour.
"""

from __future__ import annotations

from pathlib import Path

from . import csharp, css, html, javascript, python, typescript

REGISTRY = {m.LANGUAGE: m for m in (python, typescript, javascript, csharp,
                                    html, css)}

BY_EXTENSION = {ext: m for m in REGISTRY.values() for ext in m.EXTENSIONS}

ALL_EXTENSIONS = tuple(BY_EXTENSION)


def for_path(path) -> object | None:
    return BY_EXTENSION.get(Path(str(path)).suffix.lower())
