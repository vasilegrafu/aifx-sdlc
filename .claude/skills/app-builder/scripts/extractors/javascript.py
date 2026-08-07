"""JavaScript extraction, through acorn.

Separate from the TypeScript extractor on purpose. A JavaScript project is not
obliged to have TypeScript installed, and until this existed such a codebase
could not be indexed at all -- the compiler lookup simply failed. acorn is the
parser inside eslint, vite, webpack and rollup, so it is present in essentially
any real JavaScript project.

The two extractors emit the same records and `selftest.py` enforces that. What
is not shared is what genuinely differs: CommonJS and JSDoc live here, types and
interfaces live there.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from _common import rel

LANGUAGE = "javascript"
FIDELITY = "ast"
EXTENSIONS = (".js", ".jsx", ".mjs", ".cjs")

ADAPTER = Path(__file__).resolve().parents[1] / "adapters" / "js_extract.mjs"

ENV_OVERRIDE = "APP_BUILDER_ACORN"
PARSER_RELATIVE_PATH = "node_modules/acorn/dist/acorn.mjs"
JSX_RELATIVE_PATH = "node_modules/acorn-jsx/index.js"

# The skill's own install, declared in its package.json and the last place
# looked. Reading a codebase must not require having built it: the Python
# extractor parses with the standard library and needs no virtualenv, and
# requiring `npm install` in the *indexed* repository made JS and TS the only
# languages this skill could not read from a fresh checkout. The failure was
# silent and total -- every file in a repository without node_modules collapsed
# into one `unparsed` record, so a corpus of nine JavaScript projects reported
# almost no JavaScript, and absent evidence read as absent convention.
#
# A repository's own acorn still wins when it has one: matching the parser the
# project itself uses is worth more than consistency across repositories.
SKILL_PARSER_ROOT = Path(__file__).resolve().parents[2]


def _find(start: Path, relative: str) -> Path | None:
    for directory in [start, *start.parents, SKILL_PARSER_ROOT]:
        candidate = directory.joinpath(*relative.split("/"))
        if candidate.is_file():
            return candidate
    return None


def find_parser(start: Path) -> Path | None:
    """The nearest installed acorn, walking up from the source.

    `APP_BUILDER_ACORN` overrides the search, for a checkout whose dependencies
    were never installed or a fixture in a temporary directory.
    """
    override = os.environ.get(ENV_OVERRIDE)
    if override and Path(override).is_file():
        return Path(override)
    return _find(start, PARSER_RELATIVE_PATH)


def find_jsx(start: Path) -> Path | None:
    """acorn-jsx, needed only for `.jsx`. Its absence is not fatal."""
    return _find(start, JSX_RELATIVE_PATH)


def available(root: Path | None = None) -> str | None:
    """None when usable, otherwise the reason -- which the index must report.

    Only the toolchain is checked here. Where the parser lives is decided per
    file: a repository can hold several packages with their own installs, and it
    is not necessarily above the repository root.
    """
    if shutil.which("node") is None:
        return "node is not on PATH"
    if not ADAPTER.is_file():
        return f"adapter missing: {ADAPTER}"
    # A missing parser used to be reported per file, inside an `unparsed`
    # record, which is the one place nothing looks -- the index says "do not
    # read this file". So a fresh checkout that had not run `npm install`
    # indexed a JavaScript project as having almost no JavaScript, with the
    # explanation sitting where no one would see it. Saying it here routes it
    # through the same skip-and-report path as a missing toolchain, which is
    # what it is.
    if find_parser(SKILL_PARSER_ROOT) is None and (root is None
                                                   or find_parser(root) is None):
        return (f"acorn not found -- run `npm install` in {SKILL_PARSER_ROOT}, "
                f"or set {ENV_OVERRIDE}")
    return None


def _group_by_parser(files, root: Path) -> tuple[dict, list]:
    """Files keyed by the nearest installed parser; the orphans separately."""
    groups: dict[Path, list] = {}
    orphans = []
    cache: dict[Path, Path | None] = {}
    for path in files:
        parent = path.parent
        if parent not in cache:
            cache[parent] = find_parser(parent) or find_parser(root)
        parser = cache[parent]
        if parser is None:
            orphans.append(path)
        else:
            groups.setdefault(parser, []).append(path)
    return groups, orphans


def extract(files, root: Path, repo: str, commits=None, timeout: int = 300):
    if not files:
        return
    groups, orphans = _group_by_parser(files, root)

    if orphans:
        yield {"k": "unparsed", "lang": LANGUAGE, "repo": repo,
               "path": rel(orphans[0], root),
               "error": f"{len(orphans)} file(s) have no node_modules/acorn above "
                        f"them -- run npm install, or set {ENV_OVERRIDE}"}

    for parser, paths in groups.items():
        jsx = find_jsx(paths[0].parent) or find_jsx(root)
        payload = {"repo": repo, "files": []}
        for path in paths:
            try:
                mtime = int(path.stat().st_mtime)
            except OSError:
                mtime = 0
            payload["files"].append({
                "path": str(path),
                "mtime": mtime,
                "commit": (commits or {}).get(rel(path, root)),
            })

        command = ["node", str(ADAPTER), str(parser), str(root)]
        if jsx:
            command.append(str(jsx))
        try:
            proc = subprocess.run(
                command, input=json.dumps(payload), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            yield {"k": "unparsed", "lang": LANGUAGE, "repo": repo, "path": "",
                   "error": f"adapter failed: {exc}"[:200]}
            continue

        notes = [ln for ln in (proc.stderr or "").splitlines() if ln.strip()]
        if proc.returncode != 0:
            yield {"k": "unparsed", "lang": LANGUAGE, "repo": repo, "path": "",
                   "error": f"adapter exited {proc.returncode}: "
                            f"{notes[-1] if notes else 'no output'}"[:200]}
            continue
        for note in notes:
            print(note.rstrip(), file=sys.stderr)

        for line in proc.stdout.splitlines():
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
