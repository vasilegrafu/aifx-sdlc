#!/usr/bin/env python
"""Stage 1, step 2: census a repo — shape, mass, stacks, enforcement, cold zones.

    python survey.py <root> [--include src --include lib] [--md] [--json]

Read the output for: which directory is the repeated unit, which is the junk
drawer, what enforces conventions, and which parts are cold enough that mining
them would encode a past house style.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (age_days, emit, git, has_git, is_code, last_touch_map,  # noqa: E402
                     read_text, rel, section, table, walk)

MANIFESTS = {
    "package.json": "node", "pnpm-workspace.yaml": "node", "deno.json": "deno",
    "pyproject.toml": "python", "setup.py": "python", "requirements.txt": "python",
    "go.mod": "go", "Cargo.toml": "rust", "pom.xml": "java", "build.gradle": "jvm",
    "build.gradle.kts": "jvm", "Gemfile": "ruby", "composer.json": "php",
    "mix.exs": "elixir", "Package.swift": "swift", "pubspec.yaml": "dart",
    "CMakeLists.txt": "c/c++", "Makefile": "make", "Dockerfile": "docker",
    "docker-compose.yml": "docker",
}

ENFORCEMENT = (
    ".eslintrc", "eslint.config", "biome.json", ".prettierrc", "ruff.toml",
    ".flake8", "setup.cfg", "mypy.ini", "tsconfig.json", ".editorconfig",
    ".pre-commit-config.yaml", "CODEOWNERS", ".golangci", "rustfmt.toml",
    "clippy.toml", "checkstyle", ".rubocop.yml", "phpstan", "sonar-project",
)

ENFORCEMENT_DIRS = ("/.github/workflows/", "/.circleci/", "/.husky/", "/.buildkite/",
                    "/.gitlab/", "/.azure-pipelines/", "/.changeset/")

REASONING_DIRS = ("adr", "adrs", "decisions", "rfc", "rfcs", "docs", "runbook",
                  "runbooks", "playbook", "playbooks")


def bucket_of(relpath: str, depth: int) -> str:
    parts = relpath.split("/")
    if len(parts) > depth:
        return "/".join(parts[:depth])
    return "/".join(parts[:-1]) or "."


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--include", action="append", default=None,
                    help="limit to this path (repeatable); root enforcement config is listed anyway")
    ap.add_argument("--depth", type=int, default=2, help="directory rollup depth")
    ap.add_argument("--md", action="store_true", help="markdown report (the default)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = args.root.resolve()
    if not root.exists():
        print(f"error: {root} does not exist", file=sys.stderr)
        return 2

    by_ext: Counter = Counter()
    lines_by_ext: Counter = Counter()
    dir_files: Counter = Counter()
    dir_lines: Counter = Counter()
    manifests: list[tuple[str, str]] = []
    enforcement: list[str] = []
    reasoning: list[str] = []
    tests: list[str] = []
    total_files = total_lines = 0

    scan_targets = [None] if not args.include else [args.include]
    for includes in scan_targets:
        for path in walk(root, includes):
            r = rel(root, path)
            ext = path.suffix.lower() or "(none)"
            text = read_text(path)
            nlines = text.count("\n") + 1 if text else 0
            total_files += 1
            total_lines += nlines
            by_ext[ext] += 1
            lines_by_ext[ext] += nlines
            b = bucket_of(r, args.depth)
            dir_files[b] += 1
            dir_lines[b] += nlines

            name = path.name
            if name in MANIFESTS:
                manifests.append((r, MANIFESTS[name]))
            # match on the name (.eslintrc) or on the directory (.circleci/config.yml):
            # half of all enforcement lives in a dot-directory, not in a known filename
            if any(k in name for k in ENFORCEMENT) or any(d in "/" + r for d in ENFORCEMENT_DIRS):
                enforcement.append(r)
            low = "/" + r.lower()
            if any(f"/{d}/" in low for d in REASONING_DIRS):
                reasoning.append(r)
            if is_code(path) and ("test" in low or "spec" in low or "__tests__" in low):
                tests.append(r)

    # root-level enforcement config, even when scoped to subdirectories
    if args.include:
        for p in root.iterdir():
            if p.is_file() and any(k in p.name for k in ENFORCEMENT):
                enforcement.append(p.name)

    cold: list[tuple] = []
    live: list[tuple] = []
    git_summary = "no git history available — Repaired and Reasoned evidence will be hard to find"
    if has_git(root):
        touched = last_touch_map(root)
        dir_age: dict[str, list[float]] = defaultdict(list)
        for p, ts in touched.items():
            if args.include and not any(p.startswith(i.strip("/")) for i in args.include):
                continue
            dir_age[bucket_of(p, args.depth)].append(age_days(ts))
        for d, ages in dir_age.items():
            ages.sort()
            median = ages[len(ages) // 2]
            recent = sum(1 for a in ages if a <= 365) / len(ages)
            row = (d, len(ages), round(median), round(recent * 100))
            (cold if median > 365 else live).append(row)
        cold.sort(key=lambda r: -r[2])
        live.sort(key=lambda r: -r[1])
        first = (git(root, "log", "--reverse", "--format=%as", "--max-count=1") or "").strip()
        last = (git(root, "log", "--format=%as", "--max-count=1") or "").strip()
        count = (git(root, "rev-list", "--count", "HEAD") or "?").strip()
        git_summary = f"{count} commits, {first.splitlines()[0] if first else '?'} to {last or '?'}"

    if args.json:
        emit(json.dumps({
            "root": str(root), "files": total_files, "lines": total_lines,
            "by_ext": by_ext.most_common(), "dirs_by_files": dir_files.most_common(20),
            "manifests": manifests, "enforcement": enforcement,
            "reasoning": reasoning, "cold": cold, "live": live, "git": git_summary,
        }, indent=2))
        return 0

    out = [f"# Survey — {root}", "",
           f"- files scanned: **{total_files}**, lines: **{total_lines:,}**",
           f"- git: {git_summary}",
           f"- scope: {', '.join(args.include) if args.include else 'whole repo'}"]

    out.append(section("Stacks present (manifests)"))
    out.append(table(["manifest", "stack"], [[m, s] for m, s in sorted(manifests)][:40])
               if manifests else "_no manifests found_\n")

    out.append(section("Enforcement — read these first"))
    out.append("A rule a machine rejects is a settled convention: no further evidence needed, "
               "and usually no space in the skill either.\n")
    out.append("\n".join(f"- `{e}`" for e in sorted(set(enforcement))[:60]) or
               "_none found — every convention here will need Repaired or Reasoned evidence_")

    out.append(section("Where the mass is"))
    out.append(table(["directory", "files", "lines"],
                     [[d, n, f"{dir_lines[d]:,}"] for d, n in dir_files.most_common(20)]))
    out.append("Many sibling directories with similar counts = the repeated unit, and your "
               "exemplar set. One enormous directory = the junk drawer; do not mine it.\n")

    out.append(section("File types"))
    out.append(table(["ext", "files", "lines"],
                     [[e, n, f"{lines_by_ext[e]:,}"] for e, n in by_ext.most_common(15)]))

    out.append(section("Live directories (median last touch under a year)"))
    out.append(table(["directory", "files", "median age (days)", "% touched in last year"],
                     [list(r) for r in live[:15]]))

    out.append(section("Cold zones — do not mine"))
    out.append(table(["directory", "files", "median age (days)", "% touched in last year"],
                     [list(r) for r in cold[:15]]))
    out.append("Cold code encodes the house style of whenever it was last written.\n")

    out.append(section("Reasoning sources"))
    out.append("\n".join(f"- `{p}`" for p in sorted(reasoning)[:40]) or
               "_no ADR/docs/runbook directories — reasoning must come from commit bodies and PRs_")

    out.append(section("Tests"))
    if tests:
        out.append(f"{len(tests)} test files. Sample:\n" + "\n".join(f"- `{p}`" for p in tests[:10]))
    else:
        out.append("_no test files found — the skill's exemplar set may have no test half to copy_")

    out.append("\n\n---\nNext: `conventions.py` for candidate shapes, `history.py` for reasoning.\n")
    emit("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
