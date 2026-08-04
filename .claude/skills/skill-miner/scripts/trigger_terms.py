#!/usr/bin/env python
"""Mine the words that make a skill fire, from the repo it was mined from.

    python trigger_terms.py <repo-root> [--include src] [--skill <skill-dir>]

Under-triggering is the dominant failure mode of skills: the body can be perfect
and never load. The description is the trigger, and the highest-precision terms
in it are not adjectives — they are the codebase's own nouns. People paste
directory names, file suffixes, framework names and internal jargon, because
that is what is on their screen.

This lists those nouns, ranked. With --skill it also reports which ones the
skill's description already contains, which is the cheap half of the trigger
check. The other half is the Stage 4 firing test, which is the only real proof.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import emit, is_code, read_text, rel, section, table, walk  # noqa: E402

GENERIC = {"src", "lib", "app", "test", "tests", "spec", "specs", "main", "index",
           "util", "utils", "common", "core", "internal", "pkg", "cmd", "docs",
           "node_modules", "dist", "build", "public", "static", "assets", "types"}

MANIFEST_DEPS = {
    "package.json": r'"([@\w\-/.]+)"\s*:\s*"[\^~>=<\d*]',
    "requirements.txt": r"^([A-Za-z][\w\-.]+)",
    "pyproject.toml": r'^\s*"?([A-Za-z][\w\-.]+)"?\s*[=><~]',
    "go.mod": r"^\s+([\w./\-]+)\s+v\d",
    "Cargo.toml": r'^([A-Za-z][\w\-]+)\s*=',
    "Gemfile": r'^\s*gem\s+["\']([\w\-]+)',
    "composer.json": r'"([\w\-/]+)"\s*:\s*"[\^~>=<\d*]',
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--include", action="append", default=None)
    ap.add_argument("--skill", type=Path, default=None, help="check this skill's description")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = args.root.resolve()
    if not root.exists():
        print(f"error: {root} does not exist", file=sys.stderr)
        return 2

    dirs: Counter = Counter()
    suffixes: Counter = Counter()
    for p in walk(root, args.include):
        r = rel(root, p)
        for seg in r.split("/")[:-1]:
            if seg.lower() not in GENERIC and not seg.startswith("."):
                dirs[seg] += 1
        if is_code(p):
            stem = p.name[: -len(p.suffix)] if p.suffix else p.name
            for tok in (stem.split(".", 1)[1] if "." in stem else "",
                        stem.rsplit("_", 1)[1] if "_" in stem else ""):
                if tok and tok.lower() not in GENERIC:
                    suffixes[tok + p.suffix] += 1

    deps: Counter = Counter()
    for name, pattern in MANIFEST_DEPS.items():
        for p in list(root.glob(name)) + list(root.glob("*/" + name)):
            for m in re.finditer(pattern, read_text(p), re.M):
                dep = m.group(1)
                if not dep.startswith("@types") and dep.lower() not in GENERIC:
                    deps[dep] += 1

    terms = ([d for d, _ in dirs.most_common(15)] +
             [s for s, _ in suffixes.most_common(12)] +
             [d for d, _ in deps.most_common(12)])

    covered, missing = [], []
    if args.skill:
        skill_md = args.skill / "SKILL.md"
        text = read_text(skill_md)
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
        desc = (m.group(1) if m else "").lower()
        for t in terms:
            (covered if t.lower().strip(".") in desc else missing).append(t)

    if args.json:
        emit(json.dumps({"dirs": dirs.most_common(15), "suffixes": suffixes.most_common(12),
                         "deps": deps.most_common(12), "covered": covered,
                         "missing": missing}, indent=2))
        return 0

    out = [f"# Trigger terms — {root.name}", "",
           "Put the ones a person would actually type into the description. Not all of them: a "
           "description stuffed with every noun in the repo triggers on everything, which is its "
           "own failure."]

    out.append(section("Directory names"))
    out.append(table(["name", "files"], [[k, v] for k, v in dirs.most_common(15)]))
    out.append(section("Filename roles"))
    out.append(table(["suffix", "files"], [[k, v] for k, v in suffixes.most_common(12)]))
    out.append(section("Declared dependencies"))
    out.append(table(["package", "declarations"], [[k, v] for k, v in deps.most_common(12)]))
    out.append("\nFrameworks are worth including even when obvious: \"add a Django view\" is a "
               "phrasing someone types, and \"view\" alone is not distinctive enough to fire on.\n")

    if args.skill:
        out.append(section(f"Against {args.skill.name}'s description"))
        out.append(f"**Already named ({len(covered)})**: " + (", ".join(f"`{c}`" for c in covered) or "_none_"))
        out.append(f"\n**Not named ({len(missing)})**: " + (", ".join(f"`{c}`" for c in missing) or "_none_"))
        out.append("\nMissing is not automatically wrong — only add a term someone would plausibly "
                   "type when they want *this* skill. Adding the rest costs precision, and a skill "
                   "that fires on everything gets turned off.\n")

    emit("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
