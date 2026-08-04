#!/usr/bin/env python
"""Stage 1, step 5: the two conventions that live between files, not inside one.

    python graph.py <root> [--include src] [--depth 2] [--top 15] [--json]

  LAYERING  who may import whom. Direction is one of the highest-value
            conventions in any codebase and it is invisible to any per-file
            signal: every file looks fine on its own. Reported as dominant
            direction per directory pair, plus the minority edges — which are
            either sanctioned exceptions or the migration in progress.

  WIRING    the registries a new artifact must be added to: barrels, route
            tables, module indexes, DI containers. This is the centre of the
            non-obvious/silent quadrant — a generated file that is perfect and
            unreachable compiles, reviews clean, and does nothing.

Import extraction is regex per language, deliberately shallow. It resolves
relative imports properly and matches absolute ones by path suffix; unresolved
imports are reported as external rather than guessed at.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import emit, is_code, read_text, rel, section, table, walk  # noqa: E402

IMPORT_RES = [
    re.compile(r"""^\s*(?:import|export)\s+(?:[^'"]*?\s+from\s+)?['"]([^'"]+)['"]""", re.M),
    re.compile(r"""\brequire\(\s*['"]([^'"]+)['"]\s*\)"""),
    re.compile(r"""^\s*from\s+([\w.]+)\s+import\b""", re.M),
    re.compile(r"""^\s*import\s+([\w.]+)""", re.M),
    re.compile(r"""^\s*use\s+([\w:]+)""", re.M),          # rust
    re.compile(r"""^\s*using\s+([\w.]+)\s*;""", re.M),    # c#
    re.compile(r"""^\s*#include\s+[<"]([^>"]+)[>"]""", re.M),
    re.compile(r"""^\s*require(?:_relative)?\s+['"]([^'"]+)['"]""", re.M),  # ruby
]

REGISTRY_NAMES = {
    "index", "__init__", "mod", "main", "app", "routes", "router", "urls",
    "registry", "container", "module", "modules", "barrel", "exports", "wire",
    "providers", "schema", "root", "setup", "bootstrap", "plugins", "handlers",
}


def imports_of(text: str) -> list[str]:
    out: list[str] = []
    for rx in IMPORT_RES:
        out += [m if isinstance(m, str) else m[0] for m in rx.findall(text)]
    return out


def resolve(spec: str, source: str, known: dict[str, str],
            dirs_exact: dict[str, str], dirs_suffix: dict[str, str]) -> str | None:
    """Map an import spec to something inside the repo.

    Relative paths resolve exactly; package-style specs (`devfx.core`,
    `com.acme.http`) match by directory suffix, because a monorepo's import
    root is almost never the repo root. Returns None only for imports that
    match nothing here — reporting those as external beats guessing.
    """
    srcdir = source.rsplit("/", 1)[0] if "/" in source else ""

    def hit(cand: str) -> str | None:
        for key in (cand, cand + "/index", cand + "/__init__", cand + "/mod"):
            if key in known:
                return known[key]
        return dirs_exact.get(cand)

    if spec.startswith("."):
        if spec.startswith("./") or spec.startswith("../"):
            stack: list[str] = []
            for p in (srcdir + "/" + spec).split("/"):
                if p in ("", "."):
                    continue
                if p == "..":
                    if stack:
                        stack.pop()
                else:
                    stack.append(p)
            return hit("/".join(stack))
        # python-style `from . import x` / `from ..pkg import y`
        up = len(spec) - len(spec.lstrip("."))
        base = srcdir.split("/") if srcdir else []
        if up > 1:
            base = base[: max(0, len(base) - (up - 1))]
        tail = [p for p in spec.strip(".").split(".") if p]
        return hit("/".join([p for p in base if p] + tail))

    cand = spec.replace(":", "/").replace(".", "/").strip("/")
    found = hit(cand)
    if found:
        return found
    # Longest matching directory suffix: `devfx/core` -> `solution.devfx/devfx/core`.
    # Never for a single segment — a bare `import numpy` would otherwise bind to
    # any directory in the repo that happens to be called numpy, and one sample
    # fixture is enough to invent 80 dependency edges that do not exist.
    parts = cand.split("/")
    if len(parts) < 2:
        return None
    for start in range(len(parts) - 1):
        suffix = "/".join(parts[start:])
        if suffix in dirs_suffix:
            return dirs_suffix[suffix]
    return None


def bucket(path: str, depth: int) -> str:
    parts = path.split("/")
    return "/".join(parts[:depth]) if len(parts) > depth else "/".join(parts[:-1]) or "."


def build(root: Path, includes, depth: int):
    files: list[str] = []
    text_of: dict[str, str] = {}
    for p in walk(root, includes):
        if not is_code(p):
            continue
        r = rel(root, p)
        files.append(r)
        text_of[r] = read_text(p)

    # lookup keyed by extension-less path, so `./user.service` finds the file
    known: dict[str, str] = {}
    dir_set: set[str] = set()
    for r in files:
        stem = r.rsplit(".", 1)[0] if "." in r.rsplit("/", 1)[-1] else r
        known.setdefault(stem, r)
        parts = r.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            dir_set.add("/".join(parts[:i]))

    # every suffix of every directory, so a package import whose root is not the
    # repo root still lands: `devfx/core` -> `solution.devfx/devfx/core`
    # An ambiguous suffix (two directories both ending `/core`) resolves to
    # neither: a fabricated edge is worse than a missing one, because it
    # invents a dependency direction the team never had.
    candidates: dict[str, set[str]] = defaultdict(set)
    dirs_exact: dict[str, str] = {}
    for d in dir_set:
        node = known.get(d + "/__init__") or known.get(d + "/index") or (d + "/")
        dirs_exact[d] = node
        parts = d.split("/")
        for start in range(1, len(parts)):
            candidates["/".join(parts[start:])].add(node)
    dirs_suffix: dict[str, str] = {k: next(iter(v)) for k, v in candidates.items() if len(v) == 1}

    edges: list[tuple[str, str]] = []
    external: Counter = Counter()
    referenced_by: dict[str, set[str]] = defaultdict(set)
    for src in files:
        for spec in imports_of(text_of[src]):
            dst = resolve(spec, src, known, dirs_exact, dirs_suffix)
            if dst is None:
                external[spec.split("/")[0]] += 1
                continue
            if dst != src:
                edges.append((src, dst))
                referenced_by[dst].add(src)

    pairs: Counter = Counter()
    for src, dst in edges:
        a, b = bucket(src, depth), bucket(dst, depth)
        if a != b:
            pairs[(a, b)] += 1
    return files, text_of, known, edges, pairs, external, referenced_by


def layering(pairs: Counter, top: int):
    seen, rows = set(), []
    for (a, b), n in pairs.most_common():
        if (b, a) in seen or (a, b) in seen:
            continue
        seen.add((a, b))
        back = pairs.get((b, a), 0)
        if n + back < 3:
            continue
        if back == 0:
            verdict, note = "ONE WAY", "clean direction — encode it"
        elif back <= max(1, n // 8):
            verdict, note = "DOMINANT", f"{back} edge(s) against the grain — exception or migration"
        else:
            verdict, note = "TANGLED", "no direction to encode; do not invent one"
        rows.append([f"{a} → {b}", n, back, verdict, note])
        if len(rows) >= top:
            break
    return rows


def violations(edges, pairs, depth: int, limit: int = 12):
    out = []
    for src, dst in edges:
        a, b = bucket(src, depth), bucket(dst, depth)
        if a == b:
            continue
        fwd, back = pairs.get((a, b), 0), pairs.get((b, a), 0)
        if back > fwd and fwd <= max(1, back // 8):
            out.append([f"{a} → {b}", src, dst])
    return out[:limit]


def wiring(files, text_of, known, referenced_by, top: int):
    """A registry is a file that names many of its siblings. Adding a new
    sibling means editing it, and nothing in the new file says so."""
    rows = []
    by_dir: dict[str, list[str]] = defaultdict(list)
    for r in files:
        by_dir[r.rsplit("/", 1)[0] if "/" in r else "."].append(r)

    for r in files:
        d = r.rsplit("/", 1)[0] if "/" in r else "."
        stem = r.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        siblings = [s for s in by_dir[d] if s != r]
        # a directory's own registry, plus registries one level up that name
        # the child directories
        below = len(d.split("/"))
        child_dirs = {k.split("/")[below] for k in known
                      if k.startswith(d + "/") and "/" in k[len(d) + 1:]} if d != "." else set()
        text = text_of[r]
        hits = sum(1 for s in siblings
                   if re.search(r"\b" + re.escape(s.rsplit("/", 1)[-1].rsplit(".", 1)[0]) + r"\b", text))
        child_hits = sum(1 for c in child_dirs if re.search(r"\b" + re.escape(c) + r"\b", text))
        score = hits + child_hits
        if score < 3:
            continue
        looks_like = stem.lower() in REGISTRY_NAMES
        rows.append([r, score, len(siblings), "yes" if looks_like else "—",
                     len(referenced_by.get(r, ()))])
    rows.sort(key=lambda x: (-x[1], -x[4]))
    return rows[:top]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--include", action="append", default=None)
    ap.add_argument("--depth", type=int, default=2, help="directory rollup depth for layering")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--md", action="store_true", help="markdown report (the default)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = args.root.resolve()
    if not root.exists():
        print(f"error: {root} does not exist", file=sys.stderr)
        return 2

    files, text_of, known, edges, pairs, external, referenced_by = build(root, args.include, args.depth)
    lay = layering(pairs, args.top)
    viol = violations(edges, pairs, args.depth)
    wir = wiring(files, text_of, known, referenced_by, args.top)

    if args.json:
        emit(json.dumps({"files": len(files), "internal_edges": len(edges),
                         "layering": lay, "violations": viol, "wiring": wir,
                         "external": external.most_common(20)}, indent=2))
        return 0

    out = [f"# Graph — {root}", "",
           f"- {len(files)} code files · {len(edges)} internal import edges · "
           f"{sum(external.values())} external imports"]

    out.append(section("LAYERING — who imports whom"))
    out.append(table(["direction", "edges", "against", "verdict", "read as"], lay))
    out.append("\nONE WAY and DOMINANT are encodable as a rule. TANGLED is not: if the codebase "
               "has no direction here, a skill that invents one will be argued with.\n")

    out.append("\n**Edges against the grain** — each is a sanctioned exception (name it in the "
               "skill) or the migration in progress (encode the destination).\n")
    out.append(table(["direction", "importer", "imported"], viol))

    out.append(section("WIRING — what a new file must be added to"))
    out.append("Highest score = the file that names the most of its siblings. If generating a new "
               "artifact requires editing one of these, say so in the skill body and point at the "
               "exact file: this failure is silent.\n")
    out.append(table(["registry file", "siblings named", "siblings", "name looks like a registry",
                      "imported by"], wir))

    out.append(section("Top external dependencies"))
    out.append(table(["package", "imports"], [[k, v] for k, v in external.most_common(15)]))
    out.append("\nA package in the manifest but absent here is either dead or newly arriving. A "
               "package everywhere here but absent from recent files is on its way out.\n")

    emit("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
