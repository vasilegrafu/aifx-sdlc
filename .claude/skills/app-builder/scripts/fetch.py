"""Clone the reference codebases named in `config.json` into `.reference_corpus/`.

The corpus is *declared* in config and *materialised* here, so setting up this
solution on another machine is one command rather than twenty-three manual
clones and a set of paths that only exist on one laptop.

    ./.venv/Scripts/python.exe .claude/skills/app-builder/scripts/fetch.py

Deliberately separate from `index.py`. Indexing is a local, offline, repeatable
operation and it should stay that way -- a build that silently reaches for the
network is a build that fails differently depending on where you run it.

Clones are made with `--filter=blob:none`: full commit history, so `AGEING` and
`practice` dates are real, without downloading every historical blob. Shallow
clones would be smaller and would make every file in a repository share one
date, which the skill would then correctly report as "no history" -- losing the
signal that separates a live convention from a fossil.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys

from _common import configured_references, corpus_root


def _git(*args, cwd=None, timeout=1800) -> tuple[int, str]:
    try:
        proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def head_of(path) -> str:
    code, out = _git("rev-parse", "HEAD", cwd=path, timeout=60)
    return out.split()[0][:12] if code == 0 and out else ""


def clone(ref) -> tuple[bool, str]:
    target = ref["path"]
    code, out = _git("clone", "--filter=blob:none", "--quiet",
                     ref["repo"], str(target))
    if code != 0:
        return False, out.splitlines()[-1] if out else "clone failed"
    if ref.get("rev"):
        code, out = _git("checkout", "--quiet", ref["rev"], cwd=target)
        if code != 0:
            return False, f"cloned, but rev {ref['rev']} not found"
    return True, head_of(target)


def update(ref) -> tuple[bool, str]:
    target = ref["path"]
    if ref.get("rev"):
        return True, f"pinned at {ref['rev'][:12]}, not updated"
    # The remote is reset first: a directory moved here from somewhere else --
    # which is exactly how this corpus was migrated -- still points at whatever
    # origin it was cloned with, and that may not be what config now says.
    _git("remote", "set-url", "origin", ref["repo"], cwd=target)
    code, out = _git("pull", "--quiet", "--ff-only", cwd=target)
    if code != 0:
        return False, out.splitlines()[-1] if out else "pull failed"
    return True, head_of(target)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", action="append", metavar="NAME", default=[],
                    help="only these references; repeatable")
    ap.add_argument("--update", action="store_true",
                    help="pull references that are already present")
    ap.add_argument("--prune", action="store_true",
                    help="delete directories in the corpus that config no longer names")
    ap.add_argument("--dry-run", action="store_true",
                    help="say what would happen and do nothing")
    args = ap.parse_args(argv)

    if shutil.which("git") is None:
        sys.exit("git is not on PATH")

    refs = configured_references()
    if args.name:
        wanted = set(args.name)
        unknown = wanted - {r["name"] for r in refs}
        if unknown:
            sys.exit(f"not configured: {', '.join(sorted(unknown))}")
        refs = [r for r in refs if r["name"] in wanted]

    without_url = [r["name"] for r in refs if not r["repo"]]
    refs = [r for r in refs if r["repo"]]
    if without_url:
        print(f"no repo url, left alone: {', '.join(without_url)}\n")

    root = corpus_root()
    if not args.dry_run:
        root.mkdir(parents=True, exist_ok=True)

    failures = 0
    for ref in refs:
        name = ref["name"]
        if ref["path"].is_dir():
            if not args.update:
                print(f"  have      {name:<22} {head_of(ref['path'])}")
                continue
            if args.dry_run:
                print(f"  would pull {name}")
                continue
            ok, note = update(ref)
            print(f"  {'updated ' if ok else 'FAILED  '}  {name:<22} {note}")
            failures += 0 if ok else 1
            continue
        if args.dry_run:
            print(f"  would clone {name}  <- {ref['repo']}")
            continue
        ok, note = clone(ref)
        # One unreachable URL must not stop a setup: the other twenty-two are
        # still worth having, and the failure is reported rather than raised.
        print(f"  {'cloned  ' if ok else 'FAILED  '}  {name:<22} {note}")
        failures += 0 if ok else 1

    if args.prune and root.is_dir():
        keep = {r["name"] for r in configured_references()}
        for child in sorted(root.iterdir()):
            if child.is_dir() and child.name not in keep:
                print(f"  {'would prune' if args.dry_run else 'pruned  '}  {child.name}")
                if not args.dry_run:
                    shutil.rmtree(child, ignore_errors=True)

    print(f"\n{len(refs)} reference(s) in {root}"
          + (f", {failures} failed" if failures else ""))
    if failures:
        print("A missing reference is not fatal -- `practice` will report a"
              "\nsmaller corpus rather than a wrong answer. Re-run to retry.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
