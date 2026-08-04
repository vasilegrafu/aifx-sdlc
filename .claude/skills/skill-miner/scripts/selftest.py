#!/usr/bin/env python
"""Prove the detectors still detect. Run this before trusting a mining run.

    python selftest.py [--keep]

Builds a throwaway git repository containing one planted instance of everything
the pipeline claims to find — a two-author convention, a repeated block, a
one-way import direction, a barrel file, a revert, an alignment commit, a
leaked key, a fossil next to a live pattern — then runs each script over it and
checks that the plant comes back.

The fixture doubles as documentation: if you want to know what a signal
actually detects, read what this file plants for it.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable
DAY = 86400

RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((bool(ok), name, detail))


def run(script: str, *args: str) -> tuple[int, str]:
    proc = subprocess.run([PY, str(HERE / script), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=300)
    return proc.returncode, proc.stdout


def git(repo: Path, *args: str, when: float | None = None) -> None:
    env = dict(os.environ)
    if when is not None:
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(when))
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = stamp
    subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=env,
                   check=False)


def commit(repo: Path, message: str, author: str, when: float) -> None:
    git(repo, "add", "-A")
    git(repo, "-c", f"user.name={author}", "-c", f"user.email={author.lower()}@example.com",
        "commit", "-q", "-m", message, when=when)


def write(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


HANDLER = """import {{ logger }} from "../lib/log";
import {{ {svc}Service }} from "../services/{low}.service";

// the planted block below is verbatim in every handler; the lines that mention
// the entity are deliberately outside it, because those are shape, not chunk
export async function {low}Handler(req, res) {{
  const started = Date.now();
  const requestId = req.headers["x-request-id"] ?? randomUUID();
  logger.info({{ requestId, path: req.path }}, "handling request");
  try {{
    const out = await {svc}Service.run(req.body);
    return res.json(out);
  }} catch (err) {{
    logger.error({{ requestId, err }}, "request failed");
    return res.status(500).json({{ code: "INTERNAL" }});
  }}
}}
"""

SERVICE = """import {{ db }} from "../lib/db";

export const {svc}Service = {{
  async run(input) {{
    return db.{low}.insert(input);
  }},
}};
"""


def build_fixture(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init", "-q", ".")
    now = time.time()
    old = now - 900 * DAY

    # --- a fossil, written long ago by one person, never touched since
    write(repo, "src/legacy/report.controller.js",
          "class ReportController {\n  handle() { return 1; }\n}\n")
    write(repo, ".circleci/config.yml", "jobs:\n  lint:\n    steps: [checkout, run: eslint .]\n")
    commit(repo, "the old way", "Dana", old)

    # --- the live convention: three vertical slices, two authors
    for i, (name, author) in enumerate((("order", "Ash"), ("refund", "Kim"), ("invoice", "Ash"))):
        svc, low = name.capitalize(), name
        write(repo, f"src/handlers/{low}.handler.ts", HANDLER.format(svc=svc, low=low))
        write(repo, f"src/services/{low}.service.ts", SERVICE.format(svc=svc, low=low))
        write(repo, f"src/handlers/{low}.handler.test.ts",
              f'import {{ {low}Handler }} from "./{low}.handler";\n'
              f'test("{low}", async () => {{ expect({low}Handler).toBeDefined(); }});\n')
        commit(repo, f"add the {low} slice", author, now - (30 - i) * DAY)

    # --- a barrel: the wiring a new slice must be added to
    write(repo, "src/handlers/index.ts",
          "\n".join(f'export * from "./{n}.handler";' for n in ("order", "refund", "invoice")))
    commit(repo, "register handlers", "Kim", now - 25 * DAY)

    # --- Repaired evidence: a wide, shallow alignment commit
    for n in ("order", "refund", "invoice"):
        p = repo / f"src/services/{n}.service.ts"
        p.write_text(p.read_text(encoding="utf-8").replace("db.", "database."), encoding="utf-8")
    commit(repo, "align every service on the database handle", "Ash", now - 20 * DAY)

    # --- negative knowledge: a revert with no explanation
    write(repo, "src/services/cache.service.ts", "export const cache = new LruCache(1000);\n")
    commit(repo, "add a cache in front of the services", "Kim", now - 15 * DAY)
    (repo / "src/services/cache.service.ts").unlink()
    commit(repo, 'Revert "add a cache in front of the services"', "Kim", now - 14 * DAY)

    # --- a leaked credential, for the linter
    # assembled at runtime: a secret scanner that ignores its own test data is
    # a scanner nobody can trust, so this file holds no key-shaped literal
    planted = "sk-" + "live" + "93kfjeixMMdozp2841ba"
    write(repo, "skill/assets/leaky.ts", f'const KEY = "{planted}";\n')
    write(repo, "skill/SKILL.md", "---\nname: wrong-name\ndescription: too short\n---\n\n# X\n")
    commit(repo, "a skill with problems", "Ash", now - 10 * DAY)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="leave the fixture repo on disk")
    args = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="skill-miner-selftest-"))
    repo = tmp / "fixture"
    try:
        build_fixture(repo)
        r = str(repo)

        # ---------------------------------------------------------- survey
        code, out = run("survey.py", r, "--json")
        data = json.loads(out) if code == 0 else {}
        check(any(".circleci" in e for e in data.get("enforcement", [])),
              "survey finds CI config inside a dot-directory",
              "the walk allowlist must keep .circleci/.husky and friends")
        check(any("legacy" in c[0] for c in data.get("cold", [])),
              "survey marks the 900-day-old directory cold")

        # ----------------------------------------------------- conventions
        code, out = run("conventions.py", r, "--json", "--min-files", "3", "--top", "40")
        conv = json.loads(out) if code == 0 else {}
        check(conv.get("team_size") == 3, "conventions counts the authors",
              f"got {conv.get('team_size')}, planted 3")
        slices = {s["key"]: s for s in conv.get("slice", [])}
        check(any(k.endswith("handler.ts") for k in slices),
              "conventions finds the handler filename role")
        multi = [s for s in conv.get("slice", []) + conv.get("idiom", []) if s["authors"] >= 2]
        check(bool(multi), "conventions attributes patterns to more than one author")
        blocks = conv.get("block", [])
        check(any("logger.error" in b["key"] and b["files"] >= 3 for b in blocks),
              "conventions finds the planted repeated block",
              "block detection is what makes chunks reusable")
        check(not any("planted block" in b["key"] for b in blocks),
              "comment prose stays out of the block signal")

        # ----------------------------------------------------------- graph
        code, out = run("graph.py", r, "--json", "--depth", "2")
        graph = json.loads(out) if code == 0 else {}
        lay = graph.get("layering", [])
        check(any(row[0] == "src/handlers → src/services" and row[3] in {"ONE WAY", "DOMINANT"}
                  for row in lay),
              "graph finds the one-way import direction",
              f"got {[row[0] for row in lay]}")
        check(any("index.ts" in row[0] for row in graph.get("wiring", [])),
              "graph finds the barrel a new slice must be added to")

        # --------------------------------------------------------- history
        code, out = run("history.py", r, "--json", "--months", "60")
        hist = json.loads(out) if code == 0 else {}
        check(any("cache" in rev[1].lower() for rev in hist.get("reverts", [])),
              "history finds the revert")
        check(any("align" in a[1].lower() for a in hist.get("alignments", [])),
              "history finds the wide-and-shallow alignment commit")

        # ------------------------------------------------------- interview
        code, out = run("interview.py", r, "--months", "60", "--max", "12")
        check(code == 0 and "Ask these" in out, "interview generates questions")
        check("repeated verbatim" in out or "no explanation" in out,
              "interview asks about a planted gap, not only the generic questions")

        # ------------------------------------------------------ lint_skill
        code, out = run("lint_skill.py", str(repo / "skill"))
        check(code == 1, "lint fails a broken skill")
        check("sk-live" not in out and "possible" in out and "key" in out.lower(),
              "lint catches the leaked credential without echoing it")
        check("does not match directory" in out, "lint catches the name/directory mismatch")

        # ------------------------------------------------------ regen_diff
        a = repo / "src/handlers/order.handler.ts"
        # the baseline arm must be genuinely unlike the original, or the run
        # measures nothing: two handlers differing by one noun are 90% identical
        b = repo / "src/legacy/report.controller.js"
        code, out = run("regen_diff.py", "--original", str(a), "--baseline", str(b),
                        "--skilled", str(b), "--json")
        rd = json.loads(out) if code == 0 else {}
        check(rd.get("verdict") == "NOT FIRING",
              "regen_diff calls an unchanged skilled run NOT FIRING",
              f"got {rd.get('verdict')}")
        code, out = run("regen_diff.py", "--original", str(a), "--baseline", str(b),
                        "--skilled", str(a), "--json")
        rd = json.loads(out) if code == 0 else {}
        check(rd.get("verdict") == "FIRING, CLOSER",
              "regen_diff calls a matching skilled run FIRING, CLOSER",
              f"got {rd.get('verdict')}")

        # ----------------------------------------------------------- drift
        skill = tmp / "mined-skill"
        (skill / "assets").mkdir(parents=True)
        (skill / "references").mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: mined-skill\ndescription: x\n---\n\n# x\n", encoding="utf-8")
        (skill / "assets/order.handler.ts").write_text(a.read_text(encoding="utf-8"),
                                                       encoding="utf-8")
        (skill / "references/provenance.jsonl").write_text(json.dumps({
            "id": "handler-shape", "claim": "Handlers log on entry and delegate to a service.",
            "form": "exemplar", "where": "assets/order.handler.ts",
            "evidence": [{"class": "Recent", "pointer": "newest files"},
                         {"class": "Repaired", "pointer": "deadbeef"}],
            "source": {"repo": "fixture", "path": "src/handlers/order.handler.ts"},
            "mined": "2026-08-04"}) + "\n", encoding="utf-8")
        code, out = run("drift.py", str(skill), "--source", r, "--json")
        rows = json.loads(out).get("rows", []) if out.strip().startswith("{") else []
        check(rows and rows[0][1] == "OK", "drift reports OK for an unchanged exemplar",
              f"got {rows[0][1] if rows else 'nothing'}")
        a.write_text(a.read_text(encoding="utf-8").replace("logger.info", "console.log")
                     + "\nexport const extra = 1;\n" * 8, encoding="utf-8")
        code, out = run("drift.py", str(skill), "--source", r, "--json")
        rows = json.loads(out).get("rows", []) if out.strip().startswith("{") else []
        check(rows and rows[0][1] == "DRIFTED", "drift catches a rewritten source file",
              f"got {rows[0][1] if rows else 'nothing'}")

        # -------------------------------------------------------- coverage
        skills_dir = tmp / "skills"
        (skills_dir / "mined-skill").mkdir(parents=True)
        (skills_dir / "mined-skill/SKILL.md").write_text(
            "---\nname: mined-skill\ndescription: builds a handler in this repo\n---\n\n# x\n",
            encoding="utf-8")
        code, out = run("coverage.py", r, "--skills", str(skills_dir), "--json")
        cov = json.loads(out) if code == 0 else {}
        covered = [t for t in cov.get("types", []) if "handler" in t[0] and t[5] != "—"]
        uncovered = [t[0] for t in cov.get("uncovered", [])]
        check(bool(covered), "coverage matches the handler type to the skill that names it")
        check(any("service" in t for t in uncovered),
              "coverage reports the service type as uncovered", f"uncovered: {uncovered}")

    finally:
        if not args.keep:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
        else:
            print(f"fixture kept at {tmp}\n")

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    failed = [r for r in RESULTS if not r[0]]
    for ok, name, detail in RESULTS:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"\n      {detail}" if detail and not ok else ""))
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    if failed:
        print("\nA failure here means a detector stopped detecting — fix it before mining "
              "anything, or the run will quietly find less than it reports.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
