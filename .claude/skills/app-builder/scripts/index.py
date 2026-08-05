"""Build a structural index of one or more codebases.

Emits one JSON record per module, class and function -- signatures, bases,
decorators, annotated attributes, imports, and what each function calls. Not
source. The point is that a codebase of any size collapses into something a
query can filter, so only a handful of files are ever opened and read.

Language is decided by extension and handled by an extractor under
`extractors/`; every record says which language produced it and at what
fidelity. Adding a language means adding an extractor, not touching a query.

With no roots it indexes every repository in `config.json`:

    ./.venv/Scripts/python.exe .claude/skills/app-builder/scripts/index.py --name atlas

Explicit roots override the config, keeping each root's directory name as its
repo identity. Re-running rebuilds from scratch -- indexing is cheap, staleness
is not.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

from _common import (SKIP_DIRS, configured_repositories, configured_solution,
                     index_path, iter_source_files, load_config, workspace)
from extractors import ALL_EXTENSIONS, REGISTRY, for_path


def git_last_commit(root: Path, timeout: int = 180) -> dict[str, int]:
    """`{relative path: epoch of the last commit that touched it}`.

    One `git log` for the whole repository, not one per file. Empty when the
    root is not a working tree -- and empty for anything reached through a
    symlink out of it, which then falls back to mtime.

    This is the only thing in the index that can tell a live convention from a
    fossil. Without it `shape` counts files, and a pattern being abandoned still
    wins on count.
    """
    def run(*args) -> str | None:
        try:
            proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                                  text=True, timeout=timeout, errors="replace")
        except (OSError, subprocess.TimeoutExpired):
            return None
        return proc.stdout if proc.returncode == 0 else None

    # git reports paths from the top of the working tree, which is not always
    # the directory being indexed -- a solution can sit one level down inside a
    # larger repository. Without stripping that prefix nothing ever matches and
    # every file silently falls back to mtime.
    top = run("rev-parse", "--show-toplevel")
    if top is None:
        return {}
    prefix = ""
    try:
        inside = root.resolve().relative_to(Path(top.strip()).resolve()).as_posix()
        prefix = "" if inside == "." else inside + "/"
    except ValueError:
        prefix = ""

    out = run("log", "--no-merges", "--format=%ct", "--name-only")
    if out is None:
        return {}

    dates: dict[str, int] = {}
    stamp = None
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if len(line) == 10 and line.isdigit():
            stamp = int(line)
        elif stamp is not None:
            if prefix:
                if not line.startswith(prefix):
                    continue
                line = line[len(prefix):]
            # log is newest-first, so the first sighting is the latest commit
            dates.setdefault(line, stamp)
    return dates


def linked_dirs(root: Path) -> list[Path]:
    """Top-level directories that are junctions or symlinks out of the tree."""
    out = []
    try:
        children = list(root.iterdir())
    except OSError:
        return out
    for child in children:
        if child.name in SKIP_DIRS or child.name.startswith("."):
            continue
        try:
            if child.is_dir() and (child.is_symlink() or child.resolve() != child):
                out.append(child)
        except OSError:
            continue
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("roots", nargs="*",
                    help="codebase roots to index (default: every repository "
                         "in config.json)")
    ap.add_argument("--name", default="default",
                    help="index name (workspace <skill>/.data/<name>/)")
    ap.add_argument("--max-bytes", type=int, default=2_000_000,
                    help="skip files larger than this")
    ap.add_argument("--no-git", action="store_true",
                    help="skip last-commit dates; mtime alone decides recency")
    ap.add_argument("--no-solution", action="store_true",
                    help="index only the sources, leaving out the generated target")
    args = ap.parse_args()

    if args.roots:
        targets = [{"name": Path(r).resolve().name, "path": Path(r).resolve(),
                    "exclude": ()} for r in args.roots]
    else:
        targets = [t for t in configured_repositories()]
        # The generated application is indexed alongside its sources. Where it
        # has already diverged deliberately, that divergence has to be visible
        # or the next generation will quietly undo it.
        solution = configured_solution()
        if solution["exists"] and not args.no_solution:
            targets.append(solution)
        if not targets:
            sys.exit("no roots given and no repositories in config"
                     f" ({load_config()['_file']}).\n"
                     'Add them under "app-builder": {"repositories": '
                     '[{"name": ..., "path": ...}]}')
        gone = [t for t in targets if not t["exists"]]
        if gone:
            print("configured but not found on this machine:", file=sys.stderr)
            for t in gone:
                print(f"  {t['name']}: {t['path']}", file=sys.stderr)
            targets = [t for t in targets if t["exists"]]
            if not targets:
                sys.exit("nothing left to index")

    ws = workspace(args.name)
    ws.mkdir(parents=True, exist_ok=True)
    out_path = index_path(args.name)

    started = time.time()
    files = classes = funcs = unparsed = dated = 0
    repos = []
    # One physical file is indexed once, under whichever root reached it first.
    # Two solutions linked to the same library resolve to the same directory, and
    # indexing it twice makes every count wrong, every DISAGREEMENTS row compare a
    # file against itself, and every doubly defined name ambiguous. Config order
    # decides the owner, so sources come before the target and the library lands
    # with the exemplars that call it.
    seen_real: dict[str, str] = {}
    duplicates = 0
    per_language: dict[str, int] = {}
    fidelity: dict[str, str] = {}
    skipped_languages: list[tuple] = []

    with out_path.open("w", encoding="utf-8", newline="\n") as fh:
        for target in targets:
            root, repo = target["path"], target["name"]
            if not root.is_dir():
                print(f"not a directory, skipped: {root}", file=sys.stderr)
                continue
            repos.append(repo)
            n_before = files
            commits = {} if args.no_git else git_last_commit(root)
            if not args.no_git:
                # A linked-in directory belongs to the solution but is tracked in
                # its own repository, so the root's log says nothing about it.
                # Ask its repository too, and key the answers by the name the
                # solution knows it under.
                for child in linked_dirs(root):
                    for path, stamp in git_last_commit(child).items():
                        commits.setdefault(f"{child.name}/{path}", stamp)
            dated += len(commits)
            skipped_here = 0

            # Group by extractor before calling any of them. Every extractor but
            # Python shells out to its language's own toolchain, and a process
            # per file turns a two-second index into minutes.
            by_language: dict[str, list[Path]] = defaultdict(list)
            for path in iter_source_files(root, args.max_bytes,
                                          target.get("exclude", ()), ALL_EXTENSIONS):
                try:
                    real = str(path.resolve())
                except OSError:
                    real = str(path)
                if real in seen_real:
                    skipped_here += 1
                    duplicates += 1
                    continue
                seen_real[real] = repo
                extractor = for_path(path)
                if extractor is not None:
                    by_language[extractor.LANGUAGE].append(path)

            counted = []
            for language, paths in sorted(by_language.items()):
                extractor = REGISTRY[language]
                reason = extractor.available(root)
                if reason:
                    # Say so. A silently incomplete index is the worst output
                    # from a tool whose job is to report what is ALWAYS true --
                    # absent evidence reads as absent convention.
                    skipped_languages.append((repo, language, len(paths), reason))
                    print(f"  {repo}: {len(paths)} {language} files SKIPPED -- {reason}",
                          file=sys.stderr)
                    continue
                # Counted from the records, not from the extractor's own name:
                # one extractor may report more than one language, and the file
                # is the authority on which it was.
                here: dict[str, int] = {}
                for rec in extractor.extract(paths, root, repo, commits):
                    kind = rec.get("k")
                    if kind == "class":
                        classes += 1
                    elif kind == "func":
                        funcs += 1
                    elif kind in ("unparsed", "unreadable"):
                        unparsed += 1
                    elif kind == "module":
                        seen = rec.get("lang") or language
                        here[seen] = here.get(seen, 0) + 1
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                for seen, n in here.items():
                    files += n
                    per_language[seen] = per_language.get(seen, 0) + n
                    fidelity[seen] = extractor.FIDELITY
                counted += [f"{n} {seen}" for seen, n in sorted(here.items())]

            print(f"  {repo}: {files - n_before} files"
                  + (f"  ({', '.join(counted)})" if len(counted) > 1 else "")
                  + (f"  ({skipped_here} already indexed elsewhere)" if skipped_here else "")
                  + f"  <- {root}")

    meta = {
        "name": args.name,
        "roots": {t["name"]: str(t["path"]) for t in targets},
        "source": "command line" if args.roots else load_config()["_file"],
        "repos": repos, "target": next((t["name"] for t in targets if t.get("is_target")), None),
        "files": files, "classes": classes, "funcs": funcs,
        "unparsed": unparsed, "git_dated": dated, "duplicates_skipped": duplicates,
        "languages": {lang: {"files": n, "fidelity": fidelity.get(lang, "?")}
                      for lang, n in sorted(per_language.items())},
        "skipped": [{"repo": r, "language": l, "files": n, "reason": why}
                    for r, l, n, why in skipped_languages],
        "built": time.strftime("%Y-%m-%d %H:%M:%S"),
        "seconds": round(time.time() - started, 1),
    }
    (ws / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    size_mb = out_path.stat().st_size / 1e6
    print(f"\nindexed {files} files -> {classes} classes, {funcs} functions"
          f"{f', {unparsed} unparsed' if unparsed else ''}")
    print(f"{out_path}  ({size_mb:.1f} MB, {meta['seconds']}s)")
    print("\nDo not read this file. Query it:")
    print(f"  scripts/query.py layers --name {args.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
