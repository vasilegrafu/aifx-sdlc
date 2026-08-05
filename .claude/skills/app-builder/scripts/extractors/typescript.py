"""TypeScript and JavaScript extraction, through the TypeScript compiler.

Not a regex. The parser is the one the project already installed -- if you are
reading a TypeScript codebase, TypeScript is present by definition -- and it is
found by walking up from the source for a `node_modules/typescript`.

One node process for the whole repository. A process per file would turn a
two-second index into minutes, which is why `extract` takes a list.
"""

from __future__ import annotations

import json
import shutil
import sys
import subprocess
from pathlib import Path

from _common import rel

LANGUAGE = "typescript"                       # the extractor's own name
LANGUAGES = ("typescript", "javascript")      # what it may stamp on a record
FIDELITY = "ast"
EXTENSIONS = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")

# One parser, two languages. The TypeScript compiler reads JavaScript, so a `.js`
# file is extracted at the same fidelity -- but it is reported as JavaScript,
# because `--lang javascript` returning nothing while JavaScript sits in the
# index is a lie the reader has no way to catch. Expect ATTRIBUTE DETAIL to be
# thin for it: with no annotations there is no modal form to report.

ADAPTER = Path(__file__).resolve().parents[1] / "adapters" / "ts_extract.mjs"


def find_typescript(start: Path) -> Path | None:
    """The nearest installed `typescript`, walking up from the source."""
    for directory in [start, *start.parents]:
        candidate = directory / "node_modules" / "typescript" / "lib" / "typescript.js"
        if candidate.is_file():
            return candidate
    return None


def available(root: Path | None = None) -> str | None:
    """None when usable, otherwise the reason -- which the index must report.

    Only the toolchain is checked here. Where the *compiler* lives is decided per
    file: a repository can hold several packages with their own installs, and it
    is not necessarily above the repository root -- a Python solution's frontend
    sits below it.
    """
    if shutil.which("node") is None:
        return "node is not on PATH"
    if not ADAPTER.is_file():
        return f"adapter missing: {ADAPTER}"
    return None


def _group_by_compiler(files, root: Path) -> tuple[dict, list]:
    """Files keyed by the nearest installed compiler; the orphans separately."""
    groups: dict[Path, list] = {}
    orphans = []
    cache: dict[Path, Path | None] = {}
    for path in files:
        parent = path.parent
        if parent not in cache:
            cache[parent] = find_typescript(parent) or find_typescript(root)
        module = cache[parent]
        if module is None:
            orphans.append(path)
        else:
            groups.setdefault(module, []).append(path)
    return groups, orphans


def extract(files, root: Path, repo: str, commits=None, timeout: int = 300):
    if not files:
        return
    groups, orphans = _group_by_compiler(files, root)

    if orphans:
        yield {"k": "unparsed", "lang": LANGUAGE, "repo": repo,
               "path": rel(orphans[0], root),
               "error": f"{len(orphans)} file(s) have no node_modules/typescript "
                        f"above them -- run npm install"}

    for ts_module, paths in groups.items():
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

        try:
            proc = subprocess.run(
                ["node", str(ADAPTER), str(ts_module), str(root)],
                input=json.dumps(payload), capture_output=True, text=True,
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
        # The adapter reports what it declined to read -- minified bundles, most
        # often. Swallowing that would leave the index quietly short of files it
        # was handed, which is the one thing an extractor must never do.
        for note in notes:
            print(note.rstrip(), file=sys.stderr)

        for line in proc.stdout.splitlines():
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
