#!/usr/bin/env python
"""Stage 1, last step: the questions only a person can answer.

    python interview.py <root> [--include src] [--months 24] [--max 12]

Every other script reads artifacts. The knowledge that decides whether a skill
is any good is often in nobody's artifact: why the obvious approach was rejected,
which of two live patterns won, what the constraint really was. That knowledge
is cheap to get and impossible to mine — but only if the question is specific.
"Tell me about your codebase" gets nothing; "these two patterns both look live
and contradict each other, which wins?" gets a decisive answer in one line.

This generates the specific questions, from the gaps the other scripts found,
ranked by how much the answer would change what gets encoded. Answers come back
into the ledger as **Confirmed** evidence, with a name and a date, so the claim
can be re-asked when it ages out (see drift.py).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import emit, file_history, has_git, repo_authors, section  # noqa: E402
from conventions import collect, contradictions, dedupe_blocks  # noqa: E402
from history import parse_log  # noqa: E402

FIX_HINT = ("Is this file load-bearing — the place the interesting decisions live — "
            "or is it just chronically broken? The answer decides whether I mine it "
            "or avoid it.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--include", action="append", default=None)
    ap.add_argument("--months", type=int, default=24)
    ap.add_argument("--min-files", type=int, default=3)
    ap.add_argument("--max", type=int, default=12, help="questions to ask; keep it short")
    args = ap.parse_args()

    root = args.root.resolve()
    if not root.exists():
        print(f"error: {root} does not exist", file=sys.stderr)
        return 2

    slices, prologue, idiom, blocks, _ = collect(root, args.include, args.min_files)
    hist = file_history(root) if has_git(root) else {}
    team = repo_authors(root) if hist else set()
    commits = parse_log(root, args.months, 8000) if hist else []

    # (weight, question, why it matters)
    qs: list[tuple[int, str, str]] = []

    # 1. contradictions with no ruling — the answer changes what gets encoded at all
    for role, a, sa, b, sb in contradictions(idiom, slices, hist, 365)[:4]:
        qs.append((100,
                   f"Two live ways to do one thing ({role}):\n"
                   f"    A: `{a.key.splitlines()[0][:80]}` — {sa['files']} files, "
                   f"{sa['authors']} authors, {sa['pct_recent']}% recent\n"
                   f"    B: `{b.key.splitlines()[0][:80]}` — {sb['files']} files, "
                   f"{sb['authors']} authors, {sb['pct_recent']}% recent\n"
                   f"    Which one should new code use, and is the other being removed?",
                   "Encoding the losing side of a live argument gets the skill quietly abandoned."))

    # 2. reverts with no explanation — the densest knowledge in the repo, unrecorded
    for sha, ts, author, subject, body, files in commits:
        if len(qs) > 40:
            break
        if subject.lower().startswith("revert") and len(body.splitlines()) < 2:
            qs.append((95,
                       f"Commit `{sha[:10]}` reverted \"{subject[8:80]}\" with no explanation.\n"
                       f"    What went wrong, and would you hit it again today?",
                       "A reverted approach is exactly what a capable generator will reinvent."))

    # 3. patterns carried by one author in a team repo — habit or house style?
    # Below three authors this asks nothing: "one of two people wrote it" is the
    # expected state, not a signal.
    if len(team) >= 3:
        for c, s in sorted(((c, c.stats(hist, 365)) for c in slices + idiom),
                           key=lambda t: -t[1]["files"])[:40]:
            if s["authors"] == 1 and s["files"] >= 5 and s["verdict"] == "LIVE":
                qs.append((80,
                           f"`{c.key.splitlines()[0][:80]}` appears in {s['files']} files but "
                           f"comes from one author out of {len(team)}.\n"
                           f"    Is this house style, or one person's habit that spread by "
                           f"copy-paste?",
                           "Encoding one person's habit propagates it as if the team agreed."))
                if len([q for q in qs if q[0] == 80]) >= 3:
                    break

    # 4. big repeated chunks nobody extracted — the reason is usually the convention
    for c, s in ((c, c.stats(hist, 365)) for c in dedupe_blocks(blocks)[:3]):
        lines = c.key.count("\n") + 1
        if s["files"] >= 5 and lines >= 4:
            qs.append((70,
                       f"This {lines}-line block is repeated verbatim in {s['files']} files "
                       f"(e.g. `{sorted(c.files)[0]}`):\n"
                       + "\n".join("        " + l for l in c.key.splitlines()) +
                       "\n    Is the duplication deliberate, or is extracting it just never "
                       "worth it?",
                       "If deliberate, it is a convention to encode; if not, do not teach it."))

    # 5. the file that keeps breaking
    fixes: dict[str, int] = {}
    for sha, ts, author, subject, body, files in commits:
        if any(w in subject.lower() for w in ("fix", "bug", "hotfix", "regress")):
            for f in files:
                fixes[f] = fixes.get(f, 0) + 1
    for f, n in sorted(fixes.items(), key=lambda kv: -kv[1])[:2]:
        if n >= 3:
            qs.append((60, f"`{f}` appears in {n} fix commits. {FIX_HINT}",
                       "High fix-density means either the interesting file or the cursed one."))

    # 6. always worth asking, because no artifact records them
    qs += [
        (55, "What is the last thing a new joiner got wrong here that the code, the tests and "
             "the linter all let through?",
         "That is a one-sentence description of the exact quadrant this skill exists to cover."),
        (50, "Is anything in scope mid-migration right now — a pattern you are moving away from "
             "that still dominates by file count?",
         "Otherwise the skill will teach the fossil, because there is more of it."),
        (45, "Which constraint would someone competent violate without noticing? "
             "(latency budget, a library that must not be imported, a compliance rule)",
         "Constraints are rarely written down and never visible in a single file."),
        (40, "Which directory in scope would you tell someone not to copy from?",
         "Cold and legacy zones look identical to good code from the outside."),
    ]

    qs.sort(key=lambda q: -q[0])
    out = [f"# Interview — {root.name}", "",
           "Specific questions beat open ones. Ask these, record each answer in the ledger as "
           "**Confirmed** evidence with the person's name and today's date, and carry both into "
           "`provenance.jsonl` — `drift.py` will bring it back up when the confirmation ages out.",
           ""]
    if not hist:
        out.append("_No git history here, so several question types could not be generated. In a "
                   "repo like this the interview is not a supplement to mining — it is most of "
                   "the evidence you are going to get._\n")

    out.append(section("Ask these"))
    for i, (_w, q, why) in enumerate(qs[:args.max], 1):
        out.append(f"**{i}.** {q}\n\n   *Why it matters:* {why}\n")

    out.append(section("Recording an answer"))
    out.append("""```json
{"id": "<kebab-id>", "claim": "<the answer as a rule>", "form": "prose",
 "where": "SKILL.md#rules",
 "evidence": [{"class": "Confirmed", "pointer": "<who, where asked>"}],
 "source": {"repo": "<repo>", "path": "<file it applies to>"},
 "mined": "<today>", "confirmed_by": "<name>", "confirmed_on": "<today>"}
```

A Confirmed item still needs a second evidence class unless someone can point at
enforcement. An answer nobody can corroborate is a strong hypothesis, not a
settled convention — and if the person who gave it leaves, `drift.py` is the
only thing that will ever ask again.""")
    emit("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
