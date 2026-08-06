"""Vue single-file components: `<template>`, `<script>`, `<style>` in one file.

A `.vue` file is not a language. It is a container holding up to three of them,
which is why it is segmented here and then read by the extractors that already
exist rather than by a parser of its own.
"""

from __future__ import annotations

from .sfc import script_extension, style_extension, top_level_blocks

EXTENSIONS = (".vue",)
FORMAT = "vue"


def segment(text: str):
    """`(extension, text, line_offset, role)` for each block worth reading.

    Note what is *not* here: a `.vue` file need not have a script block at all.
    24 of 230 real components are template and style only -- presentational
    components with no logic. They are still files, and they still have to be
    counted, so the caller records the file even when this yields nothing it
    can parse.
    """
    for block in top_level_blocks(text):
        if block.name == "script":
            yield script_extension(block.attrs), block.text, block.line, "script"
        elif block.name == "style":
            yield style_extension(block.attrs), block.text, block.line, "style"
        elif block.name == "template":
            # `functional` and `lang="pug"` both occur; anything that is not
            # plain HTML is passed through under its own extension so it is
            # reported rather than parsed as something it is not.
            lang = block.attrs.get("lang")
            ext = f".{lang}" if isinstance(lang, str) else ".html"
            yield ext, block.text, block.line, "template"
