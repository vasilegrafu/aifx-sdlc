#!/usr/bin/env python
"""Stage 1, step 4: mine git history for reasoning, not outcomes.

    python history.py <root> [--include src] [--months 24] [--top 15] [--json]

The code records what was decided. Only the history records what was tried and
abandoned, and the abandoned branch is usually the more valuable one.

Reports:
  REVERTS          hypotheses the team tested and rejected — negative knowledge,
                   the densest value per token in the whole pipeline
  ALIGNMENTS       wide-and-shallow commits ("standardise", "align", "migrate"):
                   the moment someone decided a pattern mattered. This is
                   Repaired evidence, the hardest kind to find by reading code
  FIX DENSITY      files that keep breaking — load-bearing, or chronically
                   broken; read three commits to tell which
  REASONED COMMITS long commit bodies: where a team without ADRs writes its ADRs
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import emit, git, has_git, section, table  # noqa: E402

FIX_RE = re.compile(r"\b(fix|fixes|fixed|bug|bugfix|hotfix|regress\w*|patch|broken)\b", re.I)
REVERT_RE = re.compile(r"^\s*revert\b|\brevert(s|ed|ing)?\b", re.I)
ALIGN_RE = re.compile(
    r"\b(align|consistent\w*|standardi[sz]\w*|unif\w+|normali[sz]\w*|conform|"
    r"cleanup|clean up|tidy|rename|migrat\w+|refactor)\b", re.I)
REC = "\x01"   # start of a commit record
END = "\x03"   # end of the commit message, before the --name-only file list


def parse_log(root: Path, months: int, max_commits: int):
    """[(sha, ts, author, subject, body, [files])] newest first.

    Explicit terminators rather than blank-line heuristics: commit bodies are
    multi-line and file paths are not reliably distinguishable from prose.
    """
    out = git(root, "log", f"--max-count={max_commits}", f"--since={months} months ago",
              "--no-merges", "--name-only",
              f"--format={REC}%H%x02%at%x02%an%x02%s%x02%b{END}")
    if not out:
        return []
    commits = []
    for chunk in out.split(REC):
        if not chunk.strip():
            continue
        message, _, filepart = chunk.partition(END)
        parts = message.split("\x02")
        if len(parts) < 4:
            continue
        sha, ts, author, subject = parts[0], parts[1], parts[2], parts[3]
        body = parts[4].strip() if len(parts) > 4 else ""
        files = [l.strip() for l in filepart.splitlines() if l.strip()]
        try:
            tsi = int(ts)
        except ValueError:
            tsi = 0
        commits.append((sha, tsi, author, subject, body, files))
    return commits


def scoped(files, includes):
    if not includes:
        return files
    return [f for f in files if any(f.startswith(i.strip("/")) for i in includes)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--include", action="append", default=None,
                    help="rank by these paths only; history is still read repo-wide")
    ap.add_argument("--months", type=int, default=24)
    ap.add_argument("--max-commits", type=int, default=8000)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--md", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = args.root.resolve()
    if not has_git(root):
        print(f"error: {root} is not a git repository — Stage 1 loses Repaired and Reasoned "
              f"evidence entirely. Say so in the ledger; lean harder on enforcement config "
              f"and on asking the team.", file=sys.stderr)
        return 1

    commits = parse_log(root, args.months, args.max_commits)
    if not commits:
        print("error: no commits in window; widen --months", file=sys.stderr)
        return 1

    reverts, alignments, reasoned = [], [], []
    fix_count: Counter = Counter()
    touch_count: Counter = Counter()
    authors_per_file: dict[str, set] = defaultdict(set)

    for sha, ts, author, subject, body, files in commits:
        sfiles = scoped(files, args.include)
        for f in sfiles:
            touch_count[f] += 1
            authors_per_file[f].add(author)
        if REVERT_RE.search(subject) or REVERT_RE.search(body[:400]):
            reverts.append((sha[:10], subject[:90], len(files), body.splitlines()[0][:70] if body else ""))
        if FIX_RE.search(subject):
            for f in sfiles:
                fix_count[f] += 1
        if ALIGN_RE.search(subject) and len(files) >= 4:
            alignments.append((sha[:10], subject[:90], len(files)))
        if len(body.splitlines()) >= 5:
            reasoned.append((sha[:10], subject[:80], len(body.splitlines()), len(files)))

    out = [f"# History — {root}", "",
           f"- window: last {args.months} months, {len(commits)} commits parsed",
           f"- scope for ranking: {', '.join(args.include) if args.include else 'whole repo'}"]

    out.append(section("REVERTS — negative knowledge"))
    out.append("Each one is a hypothesis the team tested in production. `git show <sha>` on the "
               "revert and its parent gives you both the tempting approach and the reason it "
               "failed. Encode as tripwires: temptation, consequence, pointer.\n")
    out.append(table(["sha", "subject", "files", "first body line"],
                     [list(r) for r in reverts[:args.top]]))

    out.append(section("ALIGNMENTS — Repaired evidence"))
    out.append("Wide-and-shallow commits: someone spent an afternoon bringing files into line, "
               "which means the pattern mattered enough to pay for. Check whether any of these "
               "was itself reverted — that is the team deciding the pattern did **not** matter.\n")
    out.append(table(["sha", "subject", "files touched"],
                     [list(r) for r in sorted(alignments, key=lambda r: -r[2])[:args.top]]))

    out.append(section("FIX DENSITY — where the codebase learned something"))
    out.append(table(["file", "fix commits", "total commits", "authors"],
                     [[f, n, touch_count[f], len(authors_per_file[f])]
                      for f, n in fix_count.most_common(args.top)]))
    out.append("High density = load-bearing (mine it) or chronically broken (do not). "
               "Read three of its commits to tell which. Many authors on one file is where a "
               "house style congealed.\n")

    out.append(section("REASONED COMMITS — ADRs in disguise"))
    out.append(table(["sha", "subject", "body lines", "files"],
                     [list(r) for r in sorted(reasoned, key=lambda r: -r[2])[:args.top]]))

    out.append(section("Churn"))
    out.append(table(["file", "commits", "authors"],
                     [[f, n, len(authors_per_file[f])] for f, n in touch_count.most_common(args.top)]))

    if args.json:
        emit(json.dumps({"reverts": reverts[:args.top], "alignments": alignments[:args.top],
                         "fix_density": fix_count.most_common(args.top),
                         "reasoned": reasoned[:args.top]}, indent=2))
        return 0

    out.append("\n---\nRead the top reverts and the top fix-density files in full before "
               "writing a single ledger row.\n")
    emit("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
