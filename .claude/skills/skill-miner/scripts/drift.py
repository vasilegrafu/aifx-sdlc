#!/usr/bin/env python
"""Re-check a skill against the codebase it was mined from.

    python drift.py <skill-dir> --source <repo-root> [--stale-days 365] [--json]

Skills rot silently. The exemplar was copied from a file that has since been
rewritten; the ADR behind a rule was superseded; the pattern the skill teaches
is no longer what new files do. None of that shows up when you read the skill —
it reads exactly as convincing as the day it was written.

Reads the skill's references/provenance.jsonl and, for every knowledge item,
checks what can be checked deterministically:

  GONE        the source file no longer exists
  DRIFTED     the source file changed materially since it was mined
  EVIDENCE?   the cited commit is missing, or was itself reverted
  STALE       a Confirmed item older than --stale-days: ask the person again
  OK          nothing detectable changed

Exit code 1 if anything is GONE or DRIFTED, so this can gate a scheduled run.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import age_days, emit, git, has_git, read_text, section, table  # noqa: E402

DRIFT_RATIO = 0.90  # below this, the source no longer matches what was copied


def load_items(skill_dir: Path) -> tuple[list[dict], list[str]]:
    path = skill_dir / "references" / "provenance.jsonl"
    if not path.is_file():
        return [], [f"no {path.relative_to(skill_dir).as_posix()} — nothing in this skill can be "
                    f"re-checked, and every rule in it is now folklore"]
    items, problems = [], []
    for n, line in enumerate(read_text(path).splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(f"line {n} is not valid JSON: {exc}")
            continue
        if "_schema" in obj or "_comment" in obj:
            continue
        if not obj.get("id") or not obj.get("claim"):
            problems.append(f"line {n} has no id or no claim")
            continue
        items.append(obj)
    return items, problems


SHA_RE = re.compile(r"^[0-9a-f]{7,40}$", re.I)


def commit_alive(root: Path, sha: str) -> str:
    """Is the cited commit still reachable, and was it reverted since?

    Only hex-looking pointers are treated as commits. A `Reasoned` pointer is
    just as often an ADR path or a quoted comment, and running those through
    `cat-file` reports every one of them as missing evidence — a false alarm
    that trains the reader to ignore the column.
    """
    if not sha or not SHA_RE.match(sha):
        return "not a sha"
    if git(root, "cat-file", "-e", f"{sha}^{{commit}}") is None:
        return "missing"
    log = git(root, "log", "--format=%s%n%b", f"{sha}..HEAD", "--grep", sha[:8]) or ""
    if "revert" in log.lower():
        return "reverted"
    return "alive"


def exemplar_drift(skill_dir: Path, item: dict, source_root: Path) -> tuple[str, str]:
    """Compare the copied exemplar against the file it came from, today."""
    src_rel = (item.get("source") or {}).get("path")
    if not src_rel:
        return "", "no source path recorded"
    src = source_root / src_rel
    if not src.exists():
        return "GONE", f"{src_rel} no longer exists"

    where = item.get("where", "")
    local = skill_dir / where.split("#")[0]
    if not where or not local.is_file() or local.suffix.lower() in {".md", ""}:
        return "", "not a copied file — check by reading"

    a, b = read_text(local), read_text(src)
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    if ratio < DRIFT_RATIO:
        return "DRIFTED", f"exemplar is {round(ratio * 100)}% of the current {src_rel}"
    return "OK", f"{round(ratio * 100)}% match"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("skill_dir", type=Path)
    ap.add_argument("--source", type=Path, required=True, help="the repo the skill was mined from")
    ap.add_argument("--stale-days", type=int, default=365,
                    help="a Confirmed item older than this needs asking again")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    skill_dir, source = args.skill_dir.resolve(), args.source.resolve()
    if not (skill_dir / "SKILL.md").is_file():
        print(f"error: {skill_dir} is not a skill directory", file=sys.stderr)
        return 2
    if not source.exists():
        print(f"error: source repo {source} not found", file=sys.stderr)
        return 2

    items, problems = load_items(skill_dir)
    gitable = has_git(source)
    rows, bad = [], 0

    for item in items:
        status, detail = exemplar_drift(skill_dir, item, source)

        notes = []
        if gitable:
            for ev in item.get("evidence", []):
                pointer = str(ev.get("pointer", ""))
                if ev.get("class") in {"Repaired", "Reasoned"} and pointer:
                    sha = pointer.split()[0].strip("#")
                    state = commit_alive(source, sha)
                    if state in {"missing", "reverted"}:
                        notes.append(f"evidence {sha[:8]} {state}")
                        status = status or "EVIDENCE?"

        for ev in item.get("evidence", []):
            if ev.get("class") == "Confirmed":
                on = item.get("confirmed_on", "")
                try:
                    import datetime as dt
                    ts = dt.datetime.strptime(on, "%Y-%m-%d").timestamp()
                    if age_days(int(ts)) > args.stale_days:
                        notes.append(f"confirmed {on} by {item.get('confirmed_by', '?')}")
                        status = status or "STALE"
                except (ValueError, TypeError):
                    notes.append("Confirmed with no usable confirmed_on date")
                    status = status or "STALE"

        status = status or "OK"
        if status in {"GONE", "DRIFTED"}:
            bad += 1
        rows.append([item["id"], status, item.get("where", ""), detail, "; ".join(notes)])

    if args.json:
        emit(json.dumps({"skill": skill_dir.name, "items": len(items), "problems": problems,
                         "rows": rows}, indent=2))
        return 1 if bad else 0

    out = [f"# Drift — {skill_dir.name} against {source.name}", "",
           f"- knowledge items: {len(items)} · source dated: {'git' if gitable else 'no git'}"]
    for p in problems:
        out.append(f"\n**{p}**")
    out.append(section("Items"))
    out.append(table(["id", "status", "where", "detail", "notes"], rows))
    out.append("\n**GONE** — the source is deleted: the rule may have been retired with it. "
               "**DRIFTED** — re-copy the exemplar, then re-run Stage 4; the divergence you get "
               "is the codebase moving, not the skill being wrong. **EVIDENCE?** — the argument "
               "behind the rule was reverted or rewritten; re-check whether the rule still holds. "
               "**STALE** — a human confirmed this and the confirmation has aged out; ask again.\n")
    out.append(f"\n{bad} item(s) need action.\n")
    emit("\n".join(out))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
