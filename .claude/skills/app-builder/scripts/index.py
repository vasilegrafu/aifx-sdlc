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
import contextlib
import json
import os
import shutil
import subprocess
import tempfile
import sys
import time
from collections import defaultdict
from pathlib import Path

from _common import (SKIP_DIRS, _is_excluded, _is_included,
                     _may_contain_included, _is_skipped_dir,
                     configured_references,
                     configured_repositories, configured_solution, index_path,
                     iter_source_files, load_config, rel, shard_name, workspace)
from extractors import ALL_EXTENSIONS, REGISTRY, for_path
import manifests
import segmenters


def _manifest_filter(root: Path, include, exclude):
    """Decide whether the manifest walk should keep a path.

    Returns None when there is nothing to filter, so the common case walks
    exactly as it did before this existed.
    """
    included = tuple(i.strip("/").lower() for i in include if i.strip("/"))
    excluded = tuple(e.strip("/").lower() for e in exclude if e.strip("/"))
    if not included and not excluded:
        return None

    def keep(entry: Path, is_dir: bool) -> bool:
        relpath = rel(entry, root)
        if _is_excluded(relpath, excluded):
            return False
        if not included:
            return True
        if is_dir:
            return _may_contain_included(relpath, included)
        # The repository's own top-level manifest is what it declares overall,
        # and it is never inside an included subtree.
        return _is_included(relpath, included) or entry.parent == root

    return keep


def package_root(path: Path, root: Path) -> Path:
    """The package a file belongs to: the nearest directory holding its deps.

    A monorepo installs per package, and a Python solution installs its
    frontend below the repository root -- so the answer is neither the file's
    own directory nor the root, and getting it wrong skips every file with a
    reason that sounds like the toolchain is missing.
    """
    for directory in [path.parent, *path.parent.parents]:
        if (directory / "node_modules").is_dir() or (directory / "package.json").is_file():
            return directory
        if directory == root:
            break
    return root


@contextlib.contextmanager
def borrowed_parser(extractor, pkg: Path):
    """Point an extractor at the parser belonging to `pkg`, for one call.

    A span is read from a temporary directory, and every JavaScript toolchain
    finds its compiler by walking up from the file -- which from there finds
    nothing, however well installed the real project is. The extractors already
    carry an override for the case of a source file that is not where the
    toolchain expects it; this is that case.
    """
    env = getattr(extractor, "ENV_OVERRIDE", None)
    finder = (getattr(extractor, "find_parser", None)
              or getattr(extractor, "find_typescript", None))
    found = finder(pkg) if (env and finder) else None
    if not found:
        yield                      # nothing to borrow, or none needed
        return
    previous = os.environ.get(env)
    os.environ[env] = str(found)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(env, None)
        else:
            os.environ[env] = previous


def extract_containers(paths, root, repo, commits, uncovered, skipped):
    """Read container files -- one file holding several languages.

    Every span is written into one temporary directory and handed to the
    ordinary extractor for its language, so a `.vue` script block is read by
    exactly the parser that reads a `.ts` file and nothing downstream learns a
    new concept. The extractors are called once per language, not once per
    file, for the same reason they always were.

    Two things have to be undone afterwards, and both are silent when wrong:
    the **line offset**, because a record pointing into a temporary file looks
    correct and is not; and the **module record**, because one file that holds
    two script blocks would otherwise count as two files and skew every
    percentage `shape` reports.

    Spans in a language nothing here reads -- markup and styles, today -- are
    counted as not covered rather than dropped. A component whose template went
    unread is not a component that has no template.
    """
    tmp = Path(tempfile.mkdtemp(prefix="app-builder-spans-"))
    try:
        # Keyed by (language, the package the *original* file belongs to). A
        # span sits in a temporary directory, and every JavaScript toolchain
        # finds its compiler by walking up from the file -- so handing the
        # extractor the temp directory finds nothing, in a monorepo or anywhere
        # else. The original file's package is the honest answer, and grouping
        # by it keeps one extractor process per package rather than per file.
        by_language, back = defaultdict(list), {}
        for i, path in enumerate(paths):
            segmenter = segmenters.for_path(path)
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            relpath = rel(path, root)
            kwargs = {"name": path.name} if segmenter.FORMAT == "razor" else {}
            try:
                spans = list(segmenter.segment(text, **kwargs))
            except Exception as exc:                       # noqa: BLE001
                yield {"k": "unparsed", "repo": repo, "path": relpath,
                       "reason": f"{segmenter.FORMAT} segmenter: {exc}"}
                continue
            seen_any = False
            for j, (ext, body, offset, role) in enumerate(spans):
                extractor = for_path(Path("span" + ext))
                # Only the code-bearing spans are routed. A Vue `<template>` is
                # Vue's own dialect, not a Django page, and handing it to the
                # HTML extractor would file every component under the wrong
                # language and describe markup that has no directives at all.
                if role not in ("script", "code") or extractor is None:
                    uncovered[ext] = uncovered.get(ext, 0) + 1
                    continue
                span = tmp / f"{i}_{j}{ext}"
                span.write_text(body, encoding="utf-8")
                by_language[(extractor.LANGUAGE, package_root(path, root))].append(span)
                back[span.name] = (relpath, offset, path)
                seen_any = True
            if not seen_any:
                # 24 of 230 real components are template and style only. They
                # are still files and still have to be counted, or the layer
                # looks smaller than it is.
                yield module_stub(relpath, repo, path, commits)

        merged: dict[str, dict] = {}
        for (language, pkg), spans in sorted(by_language.items()):
            extractor = REGISTRY[language]
            reason = extractor.available(pkg)
            if reason:
                skipped.append((repo, f"embedded {language}", len(spans), reason))
                print(f"  {repo}: {len(spans)} embedded {language} span(s)"
                      f" SKIPPED -- {reason}", file=sys.stderr)
                continue
            # The spans are handed over with the temp directory as their root,
            # not the package. An adapter is entitled to compute a relative path
            # by trimming the root it was given, and a file outside that root
            # then comes back as a mangled name whose record is silently
            # dropped -- which is what happened. So the root is honest, and the
            # package's compiler is passed separately, by the override that
            # exists for exactly this: a source file that is not where the
            # toolchain expects to find it.
            with borrowed_parser(extractor, pkg):
                for rec in extractor.extract(spans, tmp, repo, {}):
                    entry = back.get(Path(rec.get("path", "")).name)
                    if entry is None:
                        continue
                    relpath, offset, real = entry
                    rec["path"] = relpath
                    rec["mtime"] = int(real.stat().st_mtime) if real.exists() else 0
                    rec["commit"] = commits.get(relpath, 0)
                    shift_lines(rec, offset)
                    if rec.get("k") == "module":
                        merge_module(merged, relpath, rec)
                    else:
                        yield rec
        yield from merged.values()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def shift_lines(rec, offset: int) -> None:
    if isinstance(rec.get("line"), int):
        rec["line"] = max(1, rec["line"] + offset)
    for m in rec.get("methods") or ():
        if isinstance(m.get("line"), int):
            m["line"] = max(1, m["line"] + offset)


def module_stub(relpath, repo, path, commits) -> dict:
    return {"k": "module", "lang": None, "repo": repo, "path": relpath,
            "pkg": "", "dir": relpath.rsplit("/", 1)[0] if "/" in relpath else "",
            "loc": 0, "mtime": int(path.stat().st_mtime) if path.exists() else 0,
            "commit": commits.get(relpath, 0), "main": False,
            "exports": [], "imports": []}


def merge_module(merged: dict, relpath: str, rec: dict) -> None:
    """One container file is one module record, however many blocks it holds."""
    first = merged.get(relpath)
    if first is None:
        merged[relpath] = rec
        return
    first["loc"] = first.get("loc", 0) + rec.get("loc", 0)
    for key in ("imports", "exports"):
        have = first.setdefault(key, [])
        for item in rec.get(key) or ():
            if item not in have:
                have.append(item)
    first["main"] = first.get("main") or rec.get("main")


def git_is_shallow(root: Path) -> bool:
    """Whether this working tree is a `--depth 1` clone.

    Worth asking git rather than inferring. A shallow clone has one commit, so
    every file carries the same date -- but so does a repository where one
    commit created everything, which is an ordinary and correctly dated thing.
    The two are indistinguishable from the dates themselves, and only one of
    them means the history is missing.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-shallow-repository"],
            capture_output=True, text=True, timeout=30, errors="replace")
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0 and proc.stdout.strip() == "true"


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
    ap.add_argument("--no-references", action="store_true",
                    help="leave out the reference corpus (much faster to build)")
    ap.add_argument("--only", metavar="NAME[,NAME...]",
                    help="rebuild only these repositories, keeping every other "
                         "shard as it is. The target changes constantly and the "
                         "reference corpus never does")
    args = ap.parse_args()

    if args.roots:
        targets = [{"name": Path(r).resolve().name, "path": Path(r).resolve(),
                    "exclude": (), "role": "exemplar"} for r in args.roots]
    else:
        targets = [t for t in configured_repositories()]
        # The generated application is indexed alongside its sources. Where it
        # has already diverged deliberately, that divergence has to be visible
        # or the next generation will quietly undo it.
        solution = configured_solution()
        if solution["exists"] and not args.no_solution:
            targets.append(solution)
        # References last, and the order is load bearing. One physical file is
        # indexed once, under whichever root reached it first; putting evidence
        # after exemplars means a directory shared between them lands with the
        # code that copies it rather than with the code that merely illustrates
        # it.
        if not args.no_references:
            targets += [r for r in configured_references()]
        if not targets:
            sys.exit("no roots given and no repositories in config"
                     f" ({load_config()['_file']}).\n"
                     'Add them under "app-builder": {"exemplar_corpus": '
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

    previous = {}
    if (ws / "meta.json").is_file():
        try:
            previous = json.loads((ws / "meta.json").read_text(encoding="utf-8"))
        except ValueError:
            previous = {}

    if args.only:
        wanted = {n.strip() for n in args.only.split(",") if n.strip()}
        unknown = wanted - {t["name"] for t in targets}
        if unknown:
            sys.exit(f"--only names nothing configured: {', '.join(sorted(unknown))}\n"
                     f"available: {', '.join(t['name'] for t in targets)}")
        rebuilding = [t for t in targets if t["name"] in wanted]
        if not previous:
            print("no previous index, so --only builds those repositories alone",
                  file=sys.stderr)
    else:
        rebuilding = targets
        # A full build owns the workspace, so a shard left by a repository that
        # has since been removed from the config must go with it. Otherwise a
        # dropped reference keeps answering queries, which is the failure the
        # role separation exists to prevent, arriving by a different door.
        keep = {shard_name(t["name"]) for t in targets}
        for stale in ws.glob("*.jsonl"):
            if stale.name not in keep:
                print(f"  removing shard for a repository no longer configured:"
                      f" {stale.name}")
                stale.unlink()

    started = time.time()
    files = classes = funcs = unparsed = dated = 0
    manifest_count = 0
    repos = []
    per_repo: dict[str, dict] = {}
    # One physical file is indexed once, under whichever root reached it first.
    # Two solutions linked to the same library resolve to the same directory, and
    # indexing it twice makes every count wrong, every DISAGREEMENTS row compare a
    # file against itself, and every doubly defined name ambiguous. Config order
    # decides the owner, so sources come before the target and the library lands
    # with the exemplars that call it.
    # Persisted, because a partial rebuild has to honour claims made by repos it
    # is not rebuilding. devfx is reached through both atlas and the solution;
    # rebuilding the solution alone without this would index those 268 files a
    # second time and every count that mentions them would be wrong.
    seen_real: dict[str, str] = {
        real: owner for real, owner in (previous.get("claims") or {}).items()
        if owner not in {t["name"] for t in rebuilding}
    }
    duplicates = 0
    per_language: dict[str, int] = {}
    fidelity: dict[str, str] = {}
    skipped_languages: list[tuple] = []
    # Repositories whose history is truncated. Their dates are real but
    # uniform, and AGEING cannot mean anything against them.
    shallow: list[str] = []
    # File types that are plainly source in *some* language and that no
    # extractor here claims. Reported, never silently dropped: `shape` cannot
    # distinguish "this codebase has no components" from "nothing read them".
    uncovered: dict[str, int] = {}

    with contextlib.ExitStack() as stack:
        for target in rebuilding:
            root, repo = target["path"], target["name"]
            if not root.is_dir():
                # Before the shard is opened, deliberately: opening it in "w"
                # truncates, so a repository that is temporarily unreachable --
                # an unmounted drive, a moved checkout -- would have its records
                # destroyed rather than left alone.
                print(f"not a directory, skipped: {root}", file=sys.stderr)
                continue
            # One handle per repository, all closed together by the stack. A
            # dozen open files costs nothing, and closing them here rather than
            # per iteration means an extractor that raises cannot leave a
            # half-written shard behind that still parses for its first N lines.
            fh = stack.enter_context(
                index_path(args.name, repo).open("w", encoding="utf-8", newline="\n"))
            repos.append(repo)
            n_before, c_before = files, classes
            f_before, u_before, m_before = funcs, unparsed, manifest_count
            repo_langs: dict[str, int] = {}
            commits = {} if args.no_git else git_last_commit(root)
            if not args.no_git and git_is_shallow(root):
                shallow.append(repo)
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
            containers: list[Path] = []
            for path in iter_source_files(root, args.max_bytes,
                                          target.get("exclude", ()),
                                          ALL_EXTENSIONS + segmenters.ALL_EXTENSIONS,
                                          uncovered=uncovered,
                                          include=target.get("include", ())):
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
                elif segmenters.for_path(path) is not None:
                    containers.append(path)

            counted = []
            if containers:
                here: dict[str, int] = {}
                for rec in extract_containers(containers, root, repo, commits,
                                              uncovered, skipped_languages):
                    kind = rec.get("k")
                    if kind == "class":
                        classes += 1
                    elif kind == "func":
                        funcs += 1
                    elif kind in ("unparsed", "unreadable"):
                        unparsed += 1
                    elif kind == "module":
                        seen = rec.get("lang") or "unknown"
                        here[seen] = here.get(seen, 0) + 1
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                for seen, n in here.items():
                    files += n
                    per_language[seen] = per_language.get(seen, 0) + n
                    repo_langs[seen] = repo_langs.get(seen, 0) + n
                    fidelity.setdefault(seen, "ast")
                counted += [f"{n} {seen}" for seen, n in sorted(here.items())]
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
                    repo_langs[seen] = repo_langs.get(seen, 0) + n
                    fidelity[seen] = extractor.FIDELITY
                counted += [f"{n} {seen}" for seen, n in sorted(here.items())]

            # Manifests are read per repository rather than per language: they
            # are a fact about the project, not about any file in it, and the
            # language they describe is often not the language they are written
            # in.
            here_manifests = 0
            # A manifest outside the included subtrees describes code that was
            # not indexed, so `deps` would report dependencies for files nothing
            # can see. The root's own manifest is kept either way: it is what
            # the project as a whole declares.
            keep_manifest = _manifest_filter(root, target.get("include", ()),
                                             target.get("exclude", ()))
            for rec in manifests.extract(root, repo, _is_skipped_dir, keep_manifest):
                manifest_count += 1
                here_manifests += 1
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

            per_repo[repo] = {
                "files": files - n_before, "classes": classes - c_before,
                "funcs": funcs - f_before, "unparsed": unparsed - u_before,
                "manifests": manifest_count - m_before, "languages": repo_langs,
            }

            print(f"  {repo}: {files - n_before} files"
                  + (f"  ({', '.join(counted)})" if len(counted) > 1 else "")
                  + (f"  ({here_manifests} manifest(s))" if here_manifests else "")
                  + (f"  ({skipped_here} already indexed elsewhere)" if skipped_here else "")
                  + f"  <- {root}")

    # A partial build knows only about what it read, so anything describing the
    # whole index has to be merged with what the previous build recorded for the
    # repositories left alone. Totals are the obvious casualty: reporting 71
    # files after rebuilding just the target would be a lie about the index that
    # queries are actually reading.
    kept: dict[str, dict] = {}
    if args.only and previous:
        rebuilt = {t["name"] for t in rebuilding}
        kept = {r: v for r, v in (previous.get("per_repo") or {}).items()
                if r not in rebuilt and r in {t["name"] for t in targets}}
        for r, v in kept.items():
            files += v.get("files", 0)
            classes += v.get("classes", 0)
            funcs += v.get("funcs", 0)
            unparsed += v.get("unparsed", 0)
            manifest_count += v.get("manifests", 0)
            for lang, n in (v.get("languages") or {}).items():
                per_language[lang] = per_language.get(lang, 0) + n
        repos = sorted(set(repos) | set(kept))
        shallow = sorted(set(shallow) | {r for r in (previous.get("shallow") or ())
                                         if r in kept})
        seen_real.update({real: owner
                          for real, owner in (previous.get("claims") or {}).items()
                          if owner in kept})

    meta = {
        "name": args.name,
        "roots": {t["name"]: str(t["path"]) for t in targets},
        "source": "command line" if args.roots else load_config()["_file"],
        "repos": repos, "target": next((t["name"] for t in targets if t.get("is_target")), None),
        "roles": {t["name"]: t.get("role") or "exemplar" for t in targets},
        "files": files, "classes": classes, "funcs": funcs,
        "unparsed": unparsed, "git_dated": dated, "duplicates_skipped": duplicates,
        "manifests": manifest_count,
        # Merged, not replaced. Writing only what this run rebuilt made the
        # damage cumulative: each partial build dropped every repository it did
        # not touch, so the *next* partial build had nothing left to merge and
        # meta.json converged on describing a handful of repositories while
        # twenty shards sat on disk. The shards were always right; the summary
        # of them was not, which is the harder kind of wrong to notice.
        "per_repo": {**kept, **per_repo},
        # Which repository owns each physically distinct file, so a partial
        # rebuild can honour claims it did not make itself.
        "claims": seen_real,
        "partial": sorted(t["name"] for t in rebuilding) if args.only else None,
        "languages": {lang: {"files": n, "fidelity": fidelity.get(lang, "?")}
                      for lang, n in sorted(per_language.items())},
        "shallow": shallow,
        "skipped": [{"repo": r, "language": l, "files": n, "reason": why}
                    for r, l, n, why in skipped_languages],
        "not_covered": dict(sorted(uncovered.items(), key=lambda kv: -kv[1])),
        "built": time.strftime("%Y-%m-%d %H:%M:%S"),
        "seconds": round(time.time() - started, 1),
    }
    (ws / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    shards = sorted(ws.glob('*.jsonl'))
    size_mb = sum(f.stat().st_size for f in shards) / 1e6
    print(f"\nindexed {files} files -> {classes} classes, {funcs} functions"
          f"{f', {unparsed} unparsed' if unparsed else ''}")
    if uncovered:
        top = sorted(uncovered.items(), key=lambda kv: -kv[1])[:8]
        print("not covered: " + ", ".join(f"{n} {ext}" for ext, n in top)
              + (f", and {len(uncovered) - len(top)} more types"
                 if len(uncovered) > len(top) else "")
              + "\n  no extractor reads these, so nothing about them is in the"
                " index -- do not\n  read their absence from `shape` as their"
                " absence from the codebase.")
    print(f"{ws}  ({len(shards)} shard(s), {size_mb:.1f} MB,"
          f" {meta['seconds']}s)")
    if args.only:
        print(f"  partial: rebuilt {', '.join(sorted(t['name'] for t in rebuilding))};"
              f" every other shard was left as it was")
    print("\nDo not read this file. Query it:")
    print(f"  scripts/query.py layers --name {args.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
