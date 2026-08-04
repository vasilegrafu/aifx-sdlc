#!/usr/bin/env python
"""Which artifact types in a repo have a skill, and which do not.

    python coverage.py <repo-root> --skills <skills-dir> [--include src] [--json]

Stage 4's stop rule measures whether a skill is *correct*. It says nothing about
whether the skill set is *complete*, and those are different questions: a
perfect service skill in a repo that also has migrations, jobs and client SDKs
covers one quarter of what someone will ask for.

Artifact types come from the same filename-role signal `conventions.py` uses.
A type counts as covered when a skill's description or its recorded provenance
names it — the same string a person would type, which is also what has to be in
the description for the skill to fire at all.

Uncovered types are ranked by how much live code they represent, so the next
skill to build is the top row.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import emit, file_history, has_git, read_text, section, table  # noqa: E402
from conventions import collect  # noqa: E402


def skill_texts(skills_dir: Path) -> dict[str, str]:
    """name -> description + provenance sources, lowercased. What a skill claims."""
    out = {}
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        text = read_text(skill_md)
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
        front = m.group(1) if m else ""
        prov = read_text(skill_md.parent / "references" / "provenance.jsonl")
        out[skill_md.parent.name] = (front + "\n" + prov).lower()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--skills", type=Path, required=True, help="directory holding skill directories")
    ap.add_argument("--include", action="append", default=None)
    ap.add_argument("--min-files", type=int, default=3)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root, skills_dir = args.root.resolve(), args.skills.resolve()
    if not root.exists() or not skills_dir.exists():
        print("error: root or skills directory not found", file=sys.stderr)
        return 2

    slices, _, _, _, dir_shapes = collect(root, args.include, args.min_files)
    hist = file_history(root) if has_git(root) else {}
    claims = skill_texts(skills_dir)

    # nobody sits down to build an __init__.py: these are wiring, not artifacts
    NOT_ARTIFACTS = {"__init__.py", "__main__.py", "index.ts", "index.js", "index.tsx",
                     "mod.rs", "lib.rs", "main.go", "conftest.py", "setup.py"}

    rows, uncovered = [], []
    for c in sorted(slices, key=lambda c: -len(c.files)):
        s = c.stats(hist, 365)
        if s["verdict"] == "FOSSIL" or c.key in NOT_ARTIFACTS:
            continue  # a dead or structural type needs no skill
        token = c.key.strip("._-").lower()
        word = re.sub(r"\.\w+$", "", token) or token
        owners = [n for n, text in claims.items()
                  if word and (word in text or word.rstrip("s") in text)]
        row = [c.key, s["files"], s["dirs"], s["authors"], s["verdict"],
               ", ".join(owners) or "—"]
        rows.append(row)
        if not owners:
            uncovered.append(row)

    if args.json:
        emit(json.dumps({"types": rows, "uncovered": uncovered,
                         "skills": sorted(claims)}, indent=2))
        return 0

    out = [f"# Coverage — {root.name} against {skills_dir}", "",
           f"- artifact types considered: {len(rows)} (fossils excluded) · "
           f"skills present: {len(claims)}"]

    out.append(section("Uncovered — ranked by how much live code they represent"))
    out.append(table(["artifact type", "files", "dirs", "authors", "verdict", "covered by"],
                     uncovered[:15]))
    out.append("\nThe top row is the next skill to build, unless you would never ask for one. "
               "A type with many files and many authors and no skill is where generated code "
               "will look least like the team's.\n")

    out.append(section("All types"))
    out.append(table(["artifact type", "files", "dirs", "authors", "verdict", "covered by"],
                     rows[:30]))

    out.append("\n**Matching is lexical**: a type counts as covered when a skill names it. That "
               "is deliberately the same test as whether the skill will trigger — a skill that "
               "covers migrations without ever saying \"migration\" does not, in practice, "
               "cover them.\n")
    emit("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
