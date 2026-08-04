#!/usr/bin/env python
"""Stage 4: compare a regenerated artifact against the real one — and against
the no-skill baseline, which is the comparison that says whether the skill fired.

    python regen_diff.py --original src/x.ts --skilled out/skilled.ts \\
                         [--baseline out/base.ts] \\
                         [--normalize-cmd "npx prettier --write {file}"] [--json]

Normalisation runs the repo's own formatter over copies of all three files
first. Anything a formatter erases was never a divergence, and unnormalised
diffs are mostly whitespace archaeology.

The script reports evidence: similarity across the three pairs, a
declaration-level shape diff, and the raw unified diffs. It deliberately does
**not** classify divergences as meaningful or acceptable — that is judgment, and
a script pretending to make it produces confident nonsense. The rubric is in
references/validating.md.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import read_text  # noqa: E402

# Top-level declaration markers, deliberately shallow: enough to say "this
# function/class/route exists in one file and not the other" in most languages.
DECL_RE = re.compile(
    r"""(?x)^\s{0,4}(
      (?:export\s+)?(?:default\s+)?(?:public|private|protected|internal|open|final|static|abstract|async|pub)?\s*
      (?:function|class|interface|type|enum|struct|trait|impl|def|fn|func|const|let|var|record|module|object|
         namespace|component|describe|it|test|route|@app\.\w+|@router\.\w+|CREATE\s+TABLE)
      \b[^\n{(=:]{0,80}
    )""", re.I | re.M)

DECORATOR_RE = re.compile(r"^\s*[@#\[]\s*\w[\w.]*", re.M)

# Indented `name(args) {` — plain class methods, which carry no keyword in most
# C-family languages and are the commonest declaration in OO codebases.
METHOD_RE = re.compile(
    r"""(?xm)^[ \t]{1,12}
        ((?:(?:public|private|protected|internal|static|async|override|final|suspend)\s+)*
         [A-Za-z_$][\w$]*\s*\([^;{}]*\)\s*(?::\s*[^={;]+?)?)\s*\{""")  # body may open on the same line
NOT_A_DECL = {"if", "for", "while", "switch", "catch", "return", "with", "using",
              "match", "when", "do", "else", "try", "foreach", "lock"}


def normalise(path: Path, cmd: str | None, workdir: Path) -> Path:
    """Copy into a temp dir and optionally run the repo's formatter over the copy."""
    dest = workdir / f"{path.stem}__{abs(hash(str(path))) % 10000}{path.suffix}"
    shutil.copyfile(path, dest)
    if cmd:
        filled = cmd.replace("{file}", str(dest))
        try:
            proc = subprocess.run(filled, shell=True, capture_output=True, text=True, timeout=180)
            if proc.returncode != 0:
                print(f"warning: normalise failed for {path.name}: "
                      f"{(proc.stderr or proc.stdout).strip()[:200]}", file=sys.stderr)
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"warning: normalise could not run: {exc}", file=sys.stderr)
    return dest


def lines_of(path: Path) -> list[str]:
    return [l.rstrip() for l in read_text(path).splitlines()]


def similarity(a: list[str], b: list[str]) -> float:
    return round(difflib.SequenceMatcher(None, "\n".join(a), "\n".join(b)).ratio() * 100, 1)


def declarations(text: str) -> list[str]:
    out = [re.sub(r"\s+", " ", m.group(1)).strip() for m in DECL_RE.finditer(text)]
    out += [re.sub(r"\s+", " ", m.group(0)).strip() for m in DECORATOR_RE.finditer(text)]
    for m in METHOD_RE.finditer(text):
        decl = re.sub(r"\s+", " ", m.group(1)).strip()
        if decl.split("(")[0].split()[-1].lower() in NOT_A_DECL:
            continue  # a control-flow header, not a declaration
        out.append(decl)
    seen, unique = set(), []
    for d in out:
        if d not in seen:
            seen.add(d)
            unique.append(d)
    return unique


def shape_diff(a: str, b: str) -> tuple[list[str], list[str]]:
    da, db = declarations(a), declarations(b)
    only_a = [d for d in da if d not in db]
    only_b = [d for d in db if d not in da]
    return only_a, only_b


def udiff(a: list[str], b: list[str], na: str, nb: str) -> str:
    return "\n".join(difflib.unified_diff(a, b, fromfile=na, tofile=nb, lineterm="", n=2))


def verdict(sim_ob: float | None, sim_os: float, sim_bs: float | None) -> tuple[str, str]:
    if sim_ob is None or sim_bs is None:
        return ("NO BASELINE",
                "Without a baseline arm you cannot tell a wrong skill from a silent one. "
                "Generate the no-skill version and re-run.")
    if sim_bs >= 92:
        return ("NOT FIRING",
                "Skilled output is nearly identical to the no-skill baseline. Fix the "
                "description, not the content — and do not add content, it makes the next "
                "diagnosis harder. Check name/frontmatter validity and whether the rule sits "
                "below the attention budget, then re-run.")
    if sim_os > sim_ob + 3:
        return ("FIRING, CLOSER",
                "The skill moved output toward the original. Remaining divergences are additive "
                "edits: new exemplar or new decision-rule row.")
    if sim_os < sim_ob - 3:
        return ("FIRING, WORSE",
                "The skill moved output away from the original. Some encoded rule is suppressing "
                "an instinct the model already had — find it and remove it.")
    return ("FIRING, WRONG",
            "The skill changed the output but not toward the original: a rule is mis-stated, its "
            "decision key is not observable in the request, or the exemplar shows the wrong thing.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", type=Path, required=True)
    ap.add_argument("--skilled", type=Path, required=True)
    ap.add_argument("--baseline", type=Path, default=None,
                    help="the no-skill generation from Stage 2 — omit it and you cannot "
                         "distinguish a wrong skill from one that never loaded")
    ap.add_argument("--normalize-cmd", default=None,
                    help='e.g. "npx prettier --write {file}" or "ruff format {file}"')
    ap.add_argument("--full-diff", action="store_true", help="print the raw unified diffs")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    for p in (args.original, args.skilled) + ((args.baseline,) if args.baseline else ()):
        if not p.is_file():
            print(f"error: {p} not found", file=sys.stderr)
            return 2

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        o = normalise(args.original, args.normalize_cmd, work)
        s = normalise(args.skilled, args.normalize_cmd, work)
        b = normalise(args.baseline, args.normalize_cmd, work) if args.baseline else None

        lo, ls = lines_of(o), lines_of(s)
        lb = lines_of(b) if b else None
        to, ts = read_text(o), read_text(s)
        tb = read_text(b) if b else None

        sim_os = similarity(lo, ls)
        sim_ob = similarity(lo, lb) if lb is not None else None
        sim_bs = similarity(lb, ls) if lb is not None else None
        v, advice = verdict(sim_ob, sim_os, sim_bs)

        miss, extra = shape_diff(to, ts)
        diffs = {"original vs skilled": udiff(lo, ls, "original", "skilled")}
        if lb is not None:
            diffs["original vs baseline"] = udiff(lo, lb, "original", "baseline")
            diffs["baseline vs skilled"] = udiff(lb, ls, "baseline", "skilled")

        if args.json:
            print(json.dumps({
                "similarity": {"original_skilled": sim_os, "original_baseline": sim_ob,
                               "baseline_skilled": sim_bs},
                "verdict": v, "advice": advice,
                "in_original_not_skilled": miss, "in_skilled_not_original": extra,
                "lines": {"original": len(lo), "skilled": len(ls),
                          "baseline": len(lb) if lb else None},
            }, indent=2))
            return 0

        out = [f"# Regeneration diff — {args.original.name}", "",
               f"- normalisation: `{args.normalize_cmd or 'NONE — expect whitespace noise'}`",
               f"- lines: original {len(lo)}, skilled {len(ls)}"
               + (f", baseline {len(lb)}" if lb is not None else ""), "",
               "## Similarity", "",
               f"- original ↔ skilled: **{sim_os}%**  (the residual gap)",
               f"- original ↔ baseline: **{sim_ob if sim_ob is not None else 'n/a'}%**  (the delta that exists)",
               f"- baseline ↔ skilled: **{sim_bs if sim_bs is not None else 'n/a'}%**  (did the skill do anything)",
               "", f"## Verdict: {v}", "", advice, "",
               "## Shape diff", "",
               "In the original, absent from the skilled output:",
               ("\n".join(f"- `{d}`" for d in miss[:40]) or "- _none_"), "",
               "In the skilled output, absent from the original:",
               ("\n".join(f"- `{d}`" for d in extra[:40]) or "- _none_"), "",
               "## Next", "",
               "Read each divergence against the rubric in `references/validating.md`: it is "
               "meaningful only if it changes the public surface, placement or naming, failure "
               "behaviour, a cross-cutting ceremony, or test shape. Map each survivor through "
               "the divergence→edit table, then log the run in `references/regressions.md`.",
               "", "Percentages are for tracking movement between runs, not a score. A run that "
               "improves similarity while breaking the public surface has gotten worse."]

        if args.full_diff:
            for title, d in diffs.items():
                out += ["", f"## Diff — {title}", "", "```diff", d or "(identical)", "```"]

        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
