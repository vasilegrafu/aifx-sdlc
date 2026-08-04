#!/usr/bin/env python
"""Stage 1, step 3: candidate conventions, ranked by spread and recency.

    python conventions.py <root> [--include src] [--min-files 3] [--recent-days 365]
                          [--contradictions] [--json]

Three language-agnostic signals:

  SLICE     filename suffix tokens that co-occur in a directory
            (`*.service.ts` + `*.repo.ts` + `*.test.ts`) — the skeleton of the
            vertical slice, and usually the exemplar set.
  PROLOGUE  recurring opening lines of files of one type — imports, logger
            construction, headers. A generated file with the wrong prologue
            reads as foreign immediately.
  IDIOM     normalised lines recurring across many files AND many directories.
            Spread across directories is what separates an idiom from one
            author's habit.

LIVE / MIXED / FOSSIL is a recency verdict, not a deliberateness verdict. It
says what to investigate, not what to encode: run every survivor through the
four evidence classes in SKILL.md before it reaches the ledger.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (age_days, emit, first_touch_map, has_git, is_code,  # noqa: E402
                     last_touch_map, read_text, rel, section, table, walk)

MAX_LINES_PER_FILE = 800
PROLOGUE_LINES = 15
MIN_IDIOM_CHARS = 14
COMMENT_PREFIXES = ("#", "//", "*", "/*", "--", "<!--", '"""', "'''", ";")
STRING_RE = re.compile(r"""(["'`])(?:\\.|(?!\1).)*\1""")
NUM_RE = re.compile(r"\b\d+(\.\d+)?\b")
WS_RE = re.compile(r"\s+")
CAMEL_TAIL_RE = re.compile(r"([A-Z][a-z0-9]+)$")


def shape_token(path: Path) -> str:
    """A filename's role marker, across naming cultures.

    user.service.ts -> .service.ts | user_service.py -> _service.py
    UserService.java -> Service.java | anything else -> the extension
    """
    name, ext = path.name, path.suffix.lower()
    stem = name[: -len(ext)] if ext else name
    if stem.startswith("__") and stem.endswith("__"):
        return name  # __init__.py, __main__.py: the whole name is the role
    if "." in stem:
        return "." + stem.split(".", 1)[1] + ext
    if "_" in stem:
        return "_" + stem.rsplit("_", 1)[1] + ext
    m = CAMEL_TAIL_RE.search(stem)
    if m and len(stem) > len(m.group(1)):
        return m.group(1) + ext
    return ext or "(no ext)"


def normalise(line: str) -> str:
    s = line.strip()
    if not s or s.startswith(COMMENT_PREFIXES):
        return ""
    s = STRING_RE.sub('"S"', s)
    s = NUM_RE.sub("N", s)
    s = WS_RE.sub(" ", s)
    if len(s) < MIN_IDIOM_CHARS or not any(c.isalpha() for c in s):
        return ""
    return s


class Candidate:
    __slots__ = ("kind", "key", "files", "dirs")

    def __init__(self, kind: str, key: str):
        self.kind, self.key = kind, key
        self.files: set[str] = set()
        self.dirs: set[str] = set()

    def add(self, relpath: str) -> None:
        self.files.add(relpath)
        self.dirs.add(relpath.rsplit("/", 1)[0] if "/" in relpath else ".")

    def stats(self, last: dict[str, int], recent_days: int) -> dict:
        ages = [age_days(last[f]) for f in self.files if f in last]
        ages = [a for a in ages if a != float("inf")]
        ages.sort()
        median = ages[len(ages) // 2] if ages else None
        pct_recent = (sum(1 for a in ages if a <= recent_days) / len(ages) * 100) if ages else None
        newest = ages[0] if ages else None
        if pct_recent is None:
            verdict = "UNDATED"
        elif pct_recent >= 50 or (newest is not None and newest <= 90 and pct_recent >= 10):
            # a single recent file must not flip a large stale population to LIVE
            verdict = "LIVE"
        elif pct_recent < 15 and median is not None and median > 540:
            verdict = "FOSSIL"
        else:
            verdict = "MIXED"
        return {"files": len(self.files), "dirs": len(self.dirs),
                "median_age": None if median is None else round(median),
                "newest_age": None if newest is None else round(newest),
                "pct_recent": None if pct_recent is None else round(pct_recent),
                "verdict": verdict}


def collect(root: Path, includes, min_files: int):
    slices: dict[str, Candidate] = {}
    prologue: dict[str, Candidate] = {}
    idiom: dict[str, Candidate] = {}
    dir_shapes: dict[str, set[str]] = defaultdict(set)

    for path in walk(root, includes):
        if not is_code(path):
            continue
        r = rel(root, path)
        d = r.rsplit("/", 1)[0] if "/" in r else "."
        tok = shape_token(path)
        slices.setdefault(tok, Candidate("SLICE", tok)).add(r)
        dir_shapes[d].add(tok)

        text = read_text(path)
        if not text:
            continue
        lines = text.splitlines()[:MAX_LINES_PER_FILE]
        seen_here: set[str] = set()
        for i, raw in enumerate(lines):
            n = normalise(raw)
            if not n:
                continue
            if i < PROLOGUE_LINES:
                key = f"{path.suffix.lower()} :: {n}"
                prologue.setdefault(key, Candidate("PROLOGUE", key)).add(r)
            if n in seen_here:
                continue
            seen_here.add(n)
            idiom.setdefault(n, Candidate("IDIOM", n)).add(r)

    def keep(d: dict[str, Candidate], min_dirs: int) -> list[Candidate]:
        return [c for c in d.values() if len(c.files) >= min_files and len(c.dirs) >= min_dirs]

    return keep(slices, 1), keep(prologue, 1), keep(idiom, 2), dir_shapes


ASSIGN_RE = re.compile(r"^([\w.\[\]\"'$@ ]{2,40}?)\s*(?::=|=|<-)\s*(.+)$")
ALIAS_RE = re.compile(r"^(?:import|from|using|require)\b.*\bas\s+([\w.]+)\s*[;)]?$")


def role_key(key: str) -> str | None:
    """The job a line does, so two ways of doing it land in the same group.

    Same left-hand side, different right-hand side is the signature of a
    migration: `logger = getLogger(...)` beside `logger = structlog.get(...)`.
    Same import alias, different module is the same thing one level up.
    """
    m = ALIAS_RE.match(key)
    if m:
        return f"alias {m.group(1)}"
    m = ASSIGN_RE.match(key)
    if m and not m.group(1).strip().startswith(("if", "while", "return", "#")):
        return f"assigns {m.group(1).strip()}"
    return None


def contradictions(idiom: list[Candidate], slices: list[Candidate],
                   last: dict[str, int], recent_days: int):
    """Two ways of doing one job: same role, different implementation, disjoint files."""
    groups: dict[str, list[Candidate]] = defaultdict(list)
    for c in idiom:
        k = role_key(c.key)
        if k:
            groups[k].append(c)

    out = []
    for k, members in groups.items():
        members.sort(key=lambda c: -len(c.files))
        for i, a in enumerate(members[:6]):
            for b in members[i + 1:6]:
                if a.files & b.files:
                    continue
                sa, sb = a.stats(last, recent_days), b.stats(last, recent_days)
                if sa["verdict"] == sb["verdict"] == "FOSSIL":
                    continue
                out.append((k, a, sa, b, sb))

    # filename roles: only when the recency verdicts straddle the live/dead line,
    # which is what a half-finished rename looks like from the outside
    def role_stem(key: str) -> str:
        ext = Path(key).suffix
        return key[: -len(ext)].strip("._-") if ext else key.strip("._-")

    by_ext: dict[str, list[Candidate]] = defaultdict(list)
    for c in slices:
        if role_stem(c.key):  # the bare extension is "everything else", not a role
            by_ext[Path(c.key).suffix or c.key].append(c)
    for ext, members in by_ext.items():
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                sa, sb = a.stats(last, recent_days), b.stats(last, recent_days)
                if {sa["verdict"], sb["verdict"]} != {"LIVE", "FOSSIL"}:
                    continue
                ra, rb = role_stem(a.key), role_stem(b.key)
                # compare the role words only: shared punctuation and a shared
                # extension make every pair in a language look alike
                if min(len(ra), len(rb)) < 4 or difflib.SequenceMatcher(None, ra, rb).ratio() < 0.65:
                    continue
                out.append((f"filename role in {ext}", a, sa, b, sb))

    out.sort(key=lambda t: -(len(t[1].files) + len(t[3].files)))
    return out[:25]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--include", action="append", default=None)
    ap.add_argument("--min-files", type=int, default=3)
    ap.add_argument("--recent-days", type=int, default=365)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--contradictions", action="store_true",
                    help="also report near-variant pairs with disjoint file sets")
    ap.add_argument("--md", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = args.root.resolve()
    if not root.exists():
        print(f"error: {root} does not exist", file=sys.stderr)
        return 2

    slices, prologue, idiom, dir_shapes = collect(root, args.include, args.min_files)
    last = last_touch_map(root) if has_git(root) else {}
    first = first_touch_map(root) if (has_git(root) and args.contradictions) else {}

    def rank(c: list[Candidate]):
        scored = [(x, x.stats(last, args.recent_days)) for x in c]
        scored.sort(key=lambda t: (-(t[1]["pct_recent"] or 0) * 0.01 * len(t[0].files),
                                   -len(t[0].files)))
        return scored

    if args.json:
        emit(json.dumps({
            k: [{"key": c.key, **s, "example": sorted(c.files)[0]} for c, s in rank(v)[:args.top]]
            for k, v in (("slice", slices), ("prologue", prologue), ("idiom", idiom))
        }, indent=2))
        return 0

    out = [f"# Convention candidates — {root}", "",
           f"- min files: {args.min_files} · recent window: {args.recent_days}d · "
           f"dating: {'git' if last else 'unavailable'}",
           "",
           "**LIVE / MIXED / FOSSIL is a recency verdict, not a deliberateness verdict.** "
           "Every survivor still needs two of Enforced / Repaired / Reasoned / Recent."]

    out.append(section("SLICE — filename roles"))
    out.append(table(["token", "files", "dirs", "% recent", "median age", "verdict", "example"],
                     [[c.key, s["files"], s["dirs"], s["pct_recent"], s["median_age"],
                       s["verdict"], sorted(c.files)[0]] for c, s in rank(slices)[:args.top]]))

    combos: dict[tuple, int] = defaultdict(int)
    for d, toks in dir_shapes.items():
        if len(toks) >= 2:
            combos[tuple(sorted(toks))] += 1
    combo_rows = [[" + ".join(k), v] for k, v in sorted(combos.items(), key=lambda kv: -kv[1])[:10]
                  if v >= 2]
    out.append("\n**Co-occurring in one directory** — this is the vertical slice; the top row "
               "is your exemplar set.\n")
    out.append(table(["files that appear together", "directories"], combo_rows))

    out.append(section("PROLOGUE — how files of a type open"))
    out.append(table(["ext :: line", "files", "dirs", "% recent", "verdict", "example"],
                     [[c.key[:110], s["files"], s["dirs"], s["pct_recent"], s["verdict"],
                       sorted(c.files)[0]] for c, s in rank(prologue)[:args.top]]))

    out.append(section("IDIOM — lines recurring across directories"))
    out.append(table(["normalised line", "files", "dirs", "% recent", "median age", "verdict"],
                     [[c.key[:110], s["files"], s["dirs"], s["pct_recent"], s["median_age"],
                       s["verdict"]] for c, s in rank(idiom)[:args.top]]))

    if args.contradictions:
        out.append(section("CONTRADICTIONS — one role, two implementations"))
        out.append("Two ways of doing one job. Date both sides, then: encode the destination and "
                   "tripwire the origin; or, if both are live with no reasoning, encode neither "
                   "and raise it with the user.\n")
        rows = []
        for role, a, sa, b, sb in contradictions(idiom, slices, last, args.recent_days):
            def newest_intro(c: Candidate) -> int:
                ts = [first[f] for f in c.files if f in first]
                return round(min((age_days(t) for t in ts if t), default=0))
            rows.append([
                role[:40],
                a.key[:55], f"{sa['files']}f {sa['pct_recent']}% {sa['verdict']}", newest_intro(a),
                b.key[:55], f"{sb['files']}f {sb['pct_recent']}% {sb['verdict']}", newest_intro(b),
            ])
        out.append(table(["role", "side A", "A profile", "A newest file (d)",
                          "side B", "B profile", "B newest file (d)"], rows))
        out.append("\n'newest file' is the age of the most recently *introduced* file using that "
                   "side: the side still being adopted is the destination.\n")

    out.append("\n---\nNext: `history.py` — the code holds outcomes, the history holds reasons.\n")
    emit("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
