"""Svelte components: script and style blocks, and markup that is the remainder.

Close enough to Vue to share the block scanner, different enough to be its own
segmenter: a Svelte file has no `<template>` wrapper. Its markup is whatever is
left once the script and style blocks are removed, which means the markup's
line numbers are not one contiguous range and there is nothing to be gained by
pretending otherwise -- so the markup is reported, not carved up.
"""

from __future__ import annotations

from .sfc import script_extension, style_extension, top_level_blocks

EXTENSIONS = (".svelte",)
FORMAT = "svelte"


def segment(text: str):
    """`(extension, text, line_offset, role)` for each block worth reading.

    `<script context="module">` and the instance script are both scripts and
    both yielded: they are separate scopes in Svelte, but they are the same
    language, and the index records definitions rather than scopes.
    """
    for block in top_level_blocks(text):
        if block.name == "script":
            yield script_extension(block.attrs), block.text, block.line, "script"
        elif block.name == "style":
            yield style_extension(block.attrs), block.text, block.line, "style"
