"""Shared helpers for the app-builder scripts.

The index is never read into a conversation whole. Everything here is built so
that `query.py` can filter a multi-megabyte file down to a few hundred lines
before anything reads it.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# The config block this skill reads. If the skill is ever renamed again, append
# the old name rather than replacing it: a rename should not silently stop it
# finding the codebases it was given.
CONFIG_KEYS = ("app-builder",)

# Directories that are never source: build output, caches, vendored copies.
SKIP_DIRS = {
    # version control and editors
    ".git", ".hg", ".svn", ".idea", ".vscode", ".vs",
    # python
    ".venv", "venv", "env", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".tox", "site-packages", ".eggs",
    # javascript / typescript
    "node_modules", ".next", ".nuxt", ".svelte-kit", "coverage",
    # dotnet
    "obj", "packages",
    # shared build output
    "build", "dist", "out", "target",
}

# Build output is often named after the mode it was built in -- `dist.dev`,
# `dist.prod`, `build.release`. Minified bundles parse perfectly and would be
# indexed as if they were source, reporting a "convention" no one wrote.
SKIP_PREFIXES = ("dist.", "build.", "out.")

# Extensions that could never be a language this skill reads: assets, archives,
# binaries, data, configuration and prose. Everything else that a walk finds and
# no extractor claims is reported as *not covered*, because a file type nobody
# mentions reads as a convention that does not exist -- the same error as
# skipping a language whose toolchain is missing and saying nothing.
NOT_A_LANGUAGE = {
    # images, fonts, media
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".ico", ".webp", ".avif",
    ".woff", ".woff2", ".ttf", ".eot", ".otf", ".mp3", ".mp4", ".wav", ".webm",
    # archives and binaries
    ".zip", ".gz", ".tgz", ".tar", ".7z", ".rar", ".exe", ".dll", ".pdb",
    ".so", ".dylib", ".a", ".lib", ".o", ".obj", ".class", ".jar", ".wasm",
    ".pyc", ".pyo", ".pyd", ".nupkg", ".whl",
    # data and databases
    ".csv", ".tsv", ".parquet", ".db", ".sqlite", ".sqlite3", ".pkl", ".npy",
    ".bin", ".dat", ".log", ".map",
    # configuration, lockfiles and prose -- read by people and tools, not parsed
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".properties",
    ".xml", ".lock", ".md", ".rst", ".txt", ".pdf", ".docx", ".xlsx",
    ".editorconfig", ".gitattributes", ".gitignore", ".gitkeep", ".env",
    ".snap", ".patch", ".diff", ".license", ".sample",
}

def skill_root() -> Path:
    """The app-builder skill directory these scripts live in."""
    return Path(__file__).resolve().parents[1]


def repo_root() -> Path:
    """The checkout holding config.json."""
    return skill_root().parents[2]


# ------------------------------------------------------------------ config


def load_config() -> dict:
    """The skill's block of `config.json`.

    A missing file or a missing block is not an error -- every script still
    takes explicit paths on the command line, and saying so is more use than
    failing before anyone has been told what to write.
    """
    cfg_file = repo_root() / "config.json"
    cfg = {}
    if cfg_file.exists():
        try:
            cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            sys.exit(f"{cfg_file} is not valid JSON: {exc}")

    block = next((cfg[k] for k in CONFIG_KEYS if k in cfg), {})
    block["_file"] = str(cfg_file)
    block["_exists"] = cfg_file.exists()
    return block


CORPUS_DIR = ".reference_corpus"


def corpus_root() -> Path:
    """Where fetched reference codebases live: `<skill>/.reference_corpus/`.

    Inside the skill rather than at the checkout root, for the same reason
    `.data/` is: it is the skill's working data, so the rule that keeps it out
    of git travels with the skill instead of being a line in a root
    `.gitignore` that a different checkout would not have.

    Gitignored, and it has to be for a reason beyond size: every clone carries
    its own `.git`, and `git add .` over a directory containing one writes a
    gitlink -- a phantom submodule pointing at a repository nobody can fetch.
    The leading dot also means `_is_skipped_dir` skips it, so indexing a
    codebase can never wander into twenty other codebases.

    A sibling of `.data/`, not a directory inside it. They are both derived,
    but they are not equally disposable: `.data/` rebuilds from local disk in
    minutes and the documentation says so, while this is gigabytes over the
    network. Nesting them would make "delete `.data/` and rebuild" quietly
    mean "re-clone the corpus".
    """
    return skill_root() / CORPUS_DIR


def _repo_records(entries, role: str) -> list[dict]:
    out = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        url = entry.get("repo")
        name = entry.get("name")
        if url:
            # A reference is named, cloned and located by that one name, so the
            # directory *is* the name and there is nothing to keep in sync. A
            # config that also gave a path would have two answers to where the
            # code is, and they would disagree the first time one was edited.
            if not name:
                name = url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
            path = corpus_root() / name
        elif entry.get("path"):
            path = Path(entry["path"])
            if not path.is_absolute():
                path = repo_root() / path
        else:
            continue
        path = path.resolve()
        out.append({"name": name or path.name,
                    "path": path, "exists": path.is_dir(),
                    "repo": url or "", "rev": entry.get("rev") or "",
                    "exclude": tuple(entry.get("exclude") or ()),
                    "include": tuple(entry.get("include") or ()),
                    "role": role, "is_target": role == "target"})
    return out


def configured_repositories() -> list[dict]:
    """`[{name, path, exists}]` from config. Paths may be relative to the root."""
    cfg = load_config()
    # `repositories` was the earlier spelling. Kept for the same reason as
    # `references`: a renamed key does not fail, it returns nothing -- and a
    # config with no exemplars produces a skill that reports every layer as
    # missing rather than saying it was pointed at nothing.
    entries = cfg.get("exemplar_corpus")
    if entries is None:
        entries = cfg.get("repositories")
    return _repo_records(entries, "exemplar")


def configured_references() -> list[dict]:
    """Widely-used codebases indexed as *evidence*, never as templates.

    A third role, and the distinction it draws is the whole point of it:

        exemplar   what we copy      -- its conventions are the contract
        target     what we build     -- the later decision, and it wins
        reference  what we consult   -- what the wider world does, and when

    They are indexed together because the question "is this convention still
    how anyone does it" cannot be answered from one codebase, and it is the
    question that separates a live convention from a fossil that happens to
    hold a majority.

    They must never reach `shape`, `layers`, `exemplars`, `questions` or
    DISAGREEMENTS. Nine reference repositories outnumber one exemplar, so
    letting them into a contract computation replaces the convention being
    reproduced with an average of the internet -- the same failure as averaging
    two exemplars, at nine times the scale. `read_index` filters them out
    everywhere; `practice` opts back in, and is the only thing that does.
    """
    cfg = load_config()
    # `references` was the earlier spelling, kept working on purpose: renaming a
    # config key should not silently empty the corpus, and an empty corpus is
    # the failure that looks like an answer -- `practice` would report a smaller
    # world rather than an error.
    entries = cfg.get("reference_corpus")
    if entries is None:
        entries = cfg.get("references")
    return _repo_records(entries, "reference")


def configured_solution() -> dict:
    """The target application, as a repository record like any other.

    `solution` may be a path, or an object carrying `exclude` for a tree that
    should not be walked. It is indexed alongside the sources deliberately: once
    the target holds the layer being asked for, it is the later decision, and a
    convention it has deliberately dropped must not be reintroduced from the
    source that still has it.
    """
    entry = load_config().get("solution") or "solution"
    if isinstance(entry, str):
        entry = {"path": entry}
    path = Path(entry.get("path") or "solution")
    if not path.is_absolute():
        path = repo_root() / path
    path = path.resolve()
    return {"name": entry.get("name") or path.name, "path": path,
            "exists": path.is_dir(), "exclude": tuple(entry.get("exclude") or ()),
            "include": tuple(entry.get("include") or ()),
            "repo": "", "rev": "",
            "role": "target", "is_target": True}


QUESTION_MODES = ("many", "key", "none")


def configured_questions(default: str = "many") -> str:
    """How eagerly to ask: a policy, not a count.

    A count was the wrong axis. Capping at three does not stop the fourth
    decision existing -- it makes it a silent guess, which is worse than a
    question. What limits questions properly is that each one must be load
    bearing *and* unanswerable from the codebase; the count was only ever a
    crude proxy for that restraint.

        many  -- ask at every genuine decision point, however many that is
        key   -- ask only what is expensive to reverse
        none  -- decide everything and report it

    Older configs carried an integer. `0` still means none, and any other
    number means `key`, so a config written against the previous design keeps
    working rather than failing at a startup nobody expects to fail.
    """
    value = load_config().get("questions", default)
    if isinstance(value, bool):
        return "many" if value else "none"
    if isinstance(value, int):
        return "none" if value == 0 else "key"
    text = str(value).strip().lower()
    return text if text in QUESTION_MODES else default


def solution_dir() -> Path:
    """Where generated applications are built. Named in config.json; `solution` if absent."""
    return configured_solution()["path"]


def workspace(name: str) -> Path:
    """Where an index lives: `<skill>/.data/<name>/`.

    Gitignored, and it has to be -- the skill around it is tracked, so a
    blanket `git add .` would otherwise commit structure derived from someone
    else's repository along with the skill. Everything in here is derived and
    safe to delete: `index.py` rebuilds it in seconds.
    """
    return skill_root() / ".data" / name


def shard_name(repo: str) -> str:
    """A repository's file name inside a workspace. Not the repo name verbatim:
    a name is free text from a config file and reaches the filesystem here."""
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in repo)
    return f"{safe or 'repo'}.jsonl"


def index_path(name: str, repo: str | None = None) -> Path:
    """Where a repository's records live, or the workspace holding all of them.

    One file per repository rather than one file for everything. The whole point
    is that a rebuild can be *partial*: editing one file in the target used to
    mean re-reading every reference codebase as well, which is minutes of work to
    learn something about seventy files. Each repository is independently
    readable and independently replaceable, and `read_index` streams whichever
    shards are present.
    """
    ws = workspace(name)
    return ws / shard_name(repo) if repo else ws


def index_shards(name: str) -> list[Path]:
    ws = workspace(name)
    return sorted(ws.glob("*.jsonl")) if ws.is_dir() else []


def indexed_roles(name: str) -> dict[str, str]:
    """`{repo: role}` as the index recorded it.

    Read from the index rather than from the config, because the config can
    change after a build and the records cannot. An index built before roles
    existed reports none, and everything in it is treated as an exemplar --
    which is what it was.
    """
    try:
        meta = json.loads((workspace(name) / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dict(meta.get("roles") or {})


def reference_repos(name: str) -> frozenset:
    return frozenset(r for r, role in indexed_roles(name).items()
                     if role == "reference")


def read_index(name: str, include_references: bool = False):
    """Yield index records. Streams -- the file can be larger than memory.

    Reference repositories are held out unless asked for. That default is the
    mechanism behind `configured_references`: a reference is evidence about the
    wider world, and the moment it reaches a command that computes what is
    ALWAYS true, the contract being reproduced is no longer the exemplar's.
    Opting in is one keyword and `practice` is the only caller that uses it.
    """
    shards = index_shards(name)
    if not shards:
        sys.exit(
            f"no index named {name!r} at {display_path(workspace(name))}\n"
            f"build one first:  ./.venv/Scripts/python.exe "
            f".claude/skills/app-builder/scripts/index.py --name {name} <codebase-root>..."
        )
    held_out = frozenset() if include_references else reference_repos(name)
    for path in shards:
        # A held-out repository's shard is not opened at all, which is the
        # incidental reward for splitting the file: the common case reads only
        # the exemplars and the target.
        if not include_references and path.stem in {shard_name(r).removesuffix(".jsonl")
                                                    for r in held_out}:
            continue
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                # Still checked per record: a shard name is derived from a repo
                # name and two names can sanitise to one file.
                if rec.get("repo") in held_out:
                    continue
                yield rec


def _is_skipped_dir(name: str) -> bool:
    return (name in SKIP_DIRS or name.startswith(".")
            or name.lower().startswith(SKIP_PREFIXES))


def _is_excluded(relpath: str, excluded: tuple[str, ...]) -> bool:
    low = relpath.lower()
    return any(low == e or low.startswith(e + "/") for e in excluded)


def _is_included(relpath: str, included: tuple[str, ...]) -> bool:
    """Whether a path is inside one of the named subtrees. Empty means all.

    The mirror of `_is_excluded`, and the right primitive for a reference
    codebase. `exclude` is a blacklist: you have to name everything you do not
    want, you will miss some, and what you miss is silently indexed as evidence.
    `include` names the directories where a library is *used* -- which is the
    only part of a library's own repository worth having -- and everything else
    is out without being enumerated.

    Both may be given. `include` chooses the subtrees, `exclude` removes parts of
    them, which is how you take `examples/` while dropping `examples/**/dist`.
    """
    if not included:
        return True
    low = relpath.lower()
    return any(low == i or low.startswith(i + "/") for i in included)


def _may_contain_included(relpath: str, included: tuple[str, ...]) -> bool:
    """Whether walking into this directory could still reach an included subtree.

    Without this the walk descends the whole repository and discards it a file
    at a time -- correct, and slow enough to matter on a monorepo of 6,000
    files. A directory is worth entering when it is inside an include, or when
    an include is inside it.
    """
    if not included:
        return True
    low = relpath.lower()
    return any(low == i or low.startswith(i + "/") or i.startswith(low + "/")
               for i in included)


def find_files(root: Path, names: tuple[str, ...], max_depth: int = 4) -> list[str]:
    """Named files at or below a root, as posix paths relative to it.

    Root-only was the earlier bug, and it is the same one the TypeScript
    extractor already learned: a Python solution installs its frontend *below*
    the root, so `package.json` lives at `webapp/package.json` and a check at
    the root alone concludes that a TypeScript project has no configuration at
    all. A monorepo has several of each.
    """
    wanted = {n.lower() for n in names}
    suffixes = tuple(n.lower() for n in names if n.startswith("*"))
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        depth = len(here.relative_to(root).parts) if here != root else 0
        if depth >= max_depth:
            dirnames[:] = []
        dirnames[:] = [d for d in dirnames if not _is_skipped_dir(d)]
        for fn in filenames:
            low = fn.lower()
            if low in wanted or any(low.endswith(s[1:]) for s in suffixes):
                out.append(rel(here / fn, root))
    return sorted(out)


def iter_source_files(root: Path, max_bytes: int, exclude: tuple[str, ...] = (),
                      extensions: tuple[str, ...] = (".py",), uncovered=None,
                      include: tuple[str, ...] = ()):
    """Walk a codebase for files any extractor can read.

    `exclude` behaves as it does in `iter_py_files`, which is the Python-only
    walk `smoke.py` still uses. Note that `extensions` decides what is *seen*:
    a file no extractor claims is not yielded here, so counting what a codebase
    holds but this skill cannot read is `index.py`'s job, not this one's.
    """
    lowered = tuple(e.lower() for e in extensions)
    excluded = tuple(e.strip("/").lower() for e in exclude if e.strip("/"))
    included = tuple(i.strip("/").lower() for i in include if i.strip("/"))
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        dirnames[:] = [
            d for d in dirnames
            if not _is_skipped_dir(d)
            and not _is_excluded(rel(here / d, root), excluded)
            and _may_contain_included(rel(here / d, root), included)
        ]
        # A file directly under an included subtree's parent is not in it. The
        # directory prune above keeps the walk cheap; this is what keeps it
        # correct.
        if not _is_included(rel(here, root), included) and here != root:
            continue
        for fn in filenames:
            if included and not _is_included(rel(here / fn, root), included):
                continue
            if not fn.lower().endswith(lowered):
                # Not ours. Count it anyway if the caller is keeping a tally:
                # what this skill cannot read has to be reportable.
                if uncovered is not None:
                    ext = Path(fn).suffix.lower()
                    if ext and ext not in NOT_A_LANGUAGE:
                        uncovered[ext] = uncovered.get(ext, 0) + 1
                continue
            p = here / fn
            try:
                if p.stat().st_size > max_bytes:
                    continue
            except OSError:
                continue
            yield p


def iter_py_files(root: Path, max_bytes: int, exclude: tuple[str, ...] = ()):
    """Walk a codebase, skipping what is never source and what was excluded.

    `exclude` holds paths relative to the root, matched as prefixes. It exists
    for the directory that is really another repository linked in: Python's walk
    descends a junction as if it were an ordinary directory, so without this the
    linked tree is silently indexed under the wrong repository's name.
    """
    excluded = tuple(e.strip("/").lower() for e in exclude if e.strip("/"))
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        dirnames[:] = [
            d for d in dirnames
            if not _is_skipped_dir(d)
            and not _is_excluded(rel(here / d, root), excluded)
        ]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            p = Path(dirpath) / fn
            try:
                if p.stat().st_size > max_bytes:
                    continue
            except OSError:
                continue
            yield p


def display_path(path) -> str:
    """A path as it should be printed: relative to the checkout when it is
    inside it, absolute only when it genuinely is not.

    `D:\\Dev.Work\\aifx-sdlc\\.claude\\skills\\app-builder\\.reference_corpus`
    tells a reader one useful thing and one useless one. The useful part is the
    same in every checkout; the prefix is true on one laptop, cannot be pasted
    into a command by anyone else, and quietly goes stale the moment it is
    copied into a document -- which is exactly how it got into SETUP.md.

    What lives outside the checkout keeps its absolute path, because there the
    location *is* the information: an exemplar somewhere else on the disk is
    only findable by saying where.
    """
    p = Path(path)
    try:
        return p.resolve().relative_to(repo_root().resolve()).as_posix()
    except (ValueError, OSError):
        return str(p)


def rel(path: Path, root: Path) -> str:
    """Forward-slash relative path -- stable across platforms and greppable.

    Tried without resolving first, and that order matters: a directory reached
    through a junction or symlink resolves to somewhere outside the root, and
    resolving first would push every file under it back to an absolute path --
    which then matches no `--path` glob and silently disappears from `shape`.
    """
    for p, r in ((path, root), (path.resolve(), root.resolve())):
        try:
            return p.relative_to(r).as_posix()
        except ValueError:
            continue
    return path.as_posix()


def pct(n: int, total: int) -> int:
    return round(100 * n / total) if total else 0


def truncate(s: str, limit: int = 160) -> str:
    s = " ".join(s.split())
    return s if len(s) <= limit else s[: limit - 1] + "…"
