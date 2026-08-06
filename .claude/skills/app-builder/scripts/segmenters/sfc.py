"""Top-level block scanning for single-file components.

Shared by the Vue and Svelte segmenters because it is the same scan, and the
part that differs between those two formats is which blocks exist and what
their default language is -- not how a block is found.

The rule this implements is the one real `.vue` files enforce and a naive
parser gets wrong: **a top-level block opens at column 0.** Measured across 230
components from two real codebases, every top-level `<template>`, `<script>`
and `<style>` starts at the first column, while `<template v-if=...>` and
`<template slot-scope=...>` -- which are ordinary elements *inside* the
template, and far more numerous -- are always indented. A scanner that looks
for `<template` anywhere finds dozens of false blocks per file, and one that
closes at the first `</template>` ends the block in the middle of the markup.
"""

from __future__ import annotations

import re
from typing import NamedTuple


class Block(NamedTuple):
    name: str          # template | script | style
    attrs: dict        # the open tag's attributes; `lang` decides the extractor
    text: str          # the block's contents, without the tags
    line: int          # 0-based line number of the first line of `text`


# `<script setup lang="ts">` and `<script lang="ts" setup>` are both common --
# 19 and 58 times respectively in the sample -- so attributes are parsed, never
# matched as a fixed string.
_OPEN = re.compile(r'^<(template|script|style)(\s[^>]*)?>[ \t]*$', re.MULTILINE)
_ATTR = re.compile(r'([\w:@-]+)(?:\s*=\s*"([^"]*)"|\s*=\s*\'([^\']*)\')?')


def parse_attrs(raw: str | None) -> dict:
    if not raw:
        return {}
    return {m.group(1): (m.group(2) if m.group(2) is not None else
                         (m.group(3) if m.group(3) is not None else True))
            for m in _ATTR.finditer(raw)}


def top_level_blocks(text: str) -> list[Block]:
    """Every top-level block, in source order.

    A block runs from its open tag to the matching close tag *at column 0*.
    Anything else with the same name is markup and belongs to whichever block
    contains it.
    """
    lines = text.splitlines()
    blocks: list[Block] = []
    i = 0
    while i < len(lines):
        m = _OPEN.match(lines[i] + "\n")
        if not m:
            # `<template>` on a line with trailing markup is not a top-level
            # block; the regex above requires the tag to be alone on its line.
            i += 1
            continue
        name = m.group(1)
        close = f"</{name}>"
        start = i + 1
        end = None
        for j in range(start, len(lines)):
            if lines[j].startswith(close):
                end = j
                break
        if end is None:
            # Unterminated block: take the rest of the file rather than drop it.
            end = len(lines)
        blocks.append(Block(name=name, attrs=parse_attrs(m.group(2)),
                            text="\n".join(lines[start:end]), line=start))
        i = end + 1
    return blocks


# What `lang` means, for the two blocks that hold code. Anything not listed is
# passed through as-is: an unknown `lang` becomes an extension no extractor
# claims, which is reported as not covered rather than guessed at.
SCRIPT_LANG = {None: ".js", "js": ".js", "javascript": ".js",
               "ts": ".ts", "typescript": ".ts", "tsx": ".tsx", "jsx": ".jsx"}
STYLE_LANG = {None: ".css", "css": ".css", "scss": ".scss", "sass": ".sass",
              "less": ".less", "stylus": ".styl", "postcss": ".css"}


def script_extension(attrs: dict) -> str:
    lang = attrs.get("lang")
    return SCRIPT_LANG.get(lang if isinstance(lang, str) else None, f".{lang}")


def style_extension(attrs: dict) -> str:
    lang = attrs.get("lang")
    return STYLE_LANG.get(lang if isinstance(lang, str) else None, f".{lang}")
