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
    `.indexes/` is: it is the skill's working data, so the rule that keeps it out
    of git travels with the skill instead of being a line in a root
    `.gitignore` that a different checkout would not have.

    Gitignored, and it has to be for a reason beyond size: every clone carries
    its own `.git`, and `git add .` over a directory containing one writes a
    gitlink -- a phantom submodule pointing at a repository nobody can fetch.
    The leading dot also means `_is_skipped_dir` skips it, so indexing a
    codebase can never wander into twenty other codebases.

    A sibling of `.indexes/`, not a directory inside it. They are both derived,
    but they are not equally disposable: `.indexes/` rebuilds from local disk
    in minutes and the documentation says so, while this is gigabytes over the
    network. Nesting them would make "delete `.indexes/` and rebuild" quietly
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
    everywhere; `practice` opts back in always, and `deps` only when asked to
    with `--references`.
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


# What shape the records are in. Stamped on every meta.json and checked when a
# query reads one.
#
# There is already one migration in the codebase handled by *sniffing*: calls
# used to be bare strings and are now `[name, line]`, and `call_sites()` tells
# them apart by looking. That works exactly once and only because the two
# shapes are distinguishable -- the next change might be a field that means
# something different rather than one that looks different, and there would be
# nothing to sniff. A number is what makes the next migration a check.
#
# Bump when a change makes records written by an older `index.py` wrong to read
# rather than merely thinner. Adding a field is not a bump; changing what an
# existing field means is.
INDEX_SCHEMA = 1

INDEX_DIR = ".indexes"

# One directory per role, named for the config key that fills it, so the three
# names in `config.json` and the three names on disk are the same three words.
#
# The role is the *location*, not a field. That is the whole point of this
# layout: holding references out of a contract computation used to mean reading
# a `roles` map from meta.json and filtering on it, so a meta.json that lost the
# key -- or predated it -- silently promoted twenty-three reference codebases to
# exemplars and answered anyway. There is no key here to be absent. A reference
# is held out by not opening `reference_corpus/`.
ROLE_DIRS = {"exemplar": "exemplar_corpus",
             "reference": "reference_corpus",
             "target": "solution"}
DEFAULT_ROLE = "exemplar"

# Streaming order, and it is deliberate rather than alphabetical: what the
# solution already decided comes before what the sources say, and references
# come last because most commands never reach them at all.
ROLE_ORDER = ("exemplar", "target", "reference")
CONTRACT_ROLES = ("exemplar", "target")


INDEX_ENV = "APP_BUILDER_INDEX"


def index_root() -> Path:
    """`<skill>/.indexes/` -- what was derived from the codebases.

    `APP_BUILDER_INDEX` moves it elsewhere. This is what `--name` used to be
    for, and the environment is the better home for it: a *name* sat in the
    same sentence as repository names and was read as one often enough that
    the troubleshooting notes had to say it was not. A path cannot be mistaken
    for a repository. It is also what lets the selftest build a fixture index
    without writing over the real one -- isolation the named workspaces used
    to provide, and which would otherwise have been lost with them.

    A sibling of `.reference_corpus/`, which holds the codebases themselves, at
    a mirrored path: `.reference_corpus/django/` is the source and
    `.indexes/reference_corpus/django/` is what this skill knows about it.

    Gitignored, and it has to be -- the skill around it is tracked, so a blanket
    `git add .` would otherwise commit structure derived from someone else's
    repository along with the skill. The leading dot is load bearing for a
    second reason: it is what makes `_is_skipped_dir` prune this directory, so
    indexing a codebase that contains the skill cannot index the index.
    """
    override = os.environ.get(INDEX_ENV)
    return Path(override).expanduser() if override else skill_root() / INDEX_DIR


def role_dir(role: str) -> Path:
    return index_root() / ROLE_DIRS.get(role, ROLE_DIRS[DEFAULT_ROLE])


def safe_name(repo: str) -> str:
    """A repository's directory name. Not the repo name verbatim: a name is free
    text from a config file and reaches the filesystem here.

    Two config names can sanitise to one directory. That is now a collision
    `index.py` must refuse rather than absorb -- as files they merely
    overwrote, as directories they would interleave two codebases into one and
    report the blend as a convention.
    """
    return "".join(c if (c.isalnum() or c in "-_.") else "_" for c in repo) or "repo"


def index_path(role: str, repo: str) -> Path:
    """Where one repository's index lives: `.indexes/<role>/<repo>/`.

    One directory per repository rather than one file for everything, so a
    rebuild can be *partial*: editing one file in the solution used to mean
    re-reading every reference codebase as well, minutes of work to learn
    something about seventy files.

    A directory rather than a single shard file because the stats belong beside
    the records. When a repository's totals lived in one shared meta.json, a
    partial rebuild had to merge what it did not rebuild back in, and the
    version that forgot to merge dropped every untouched repository -- leaving
    the summary describing three repositories while twenty shards sat on disk.
    Each repository now owns its own totals, and there is nothing to merge.
    """
    return role_dir(role) / safe_name(repo)


def index_file(role: str, repo: str) -> Path:
    return index_path(role, repo) / "index.jsonl"


def index_meta(role: str, repo: str) -> Path:
    return index_path(role, repo) / "meta.json"


def rollup_path() -> Path:
    """`.indexes/meta.json` -- totals across every repository, and the claims
    map, which is global by nature: its job is telling two repositories apart."""
    return index_root() / "meta.json"


def indexed_repositories(roles=ROLE_ORDER) -> list[dict]:
    """What is actually on disk, in role order. The index describes itself.

    Read from the tree rather than from the config, because the config can
    change after a build and the records cannot.
    """
    out = []
    for role in roles:
        directory = role_dir(role)
        if not directory.is_dir():
            continue
        for child in sorted(directory.iterdir()):
            records = child / "index.jsonl"
            if records.is_file():
                out.append({"role": role, "dir": child.name,
                            "records": records, "meta": child / "meta.json"})
    return out


def indexed_roles() -> dict[str, str]:
    """`{repo: role}` as the tree records it.

    Derived from where each repository sits, not from a field anyone wrote:
    the directory is the role. Read from the index rather than from the config
    because the config can change after a build and the records cannot -- but
    unlike the roles map this replaces, it cannot be absent or disagree, since
    a repository with no role has nowhere to be.

    For display. Nothing decides anything by it; `read_index` holds references
    out by not opening their directory.
    """
    out = {}
    for shard in indexed_repositories():
        repo = shard["dir"]
        try:
            repo = json.loads(shard["meta"].read_text(encoding="utf-8")).get("repo") or repo
        except (OSError, ValueError):
            pass
        out[repo] = shard["role"]
    return out


def index_schema_warning() -> str | None:
    """Whether this index was written by an `index.py` that disagrees with us.

    Silence when it agrees, or when the index predates the field entirely --
    schema 1 is what everything written before the stamp existed effectively
    is, and treating "no answer" as a mismatch would report every existing
    index as broken on the day this shipped.
    """
    found = set()
    for shard in indexed_repositories():
        try:
            meta = json.loads(shard["meta"].read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        found.add(meta.get("schema", INDEX_SCHEMA))
    stale = sorted(v for v in found if v != INDEX_SCHEMA)
    if not stale:
        return None
    return (f"index schema {', '.join(str(v) for v in stale)}, but these "
            f"scripts read schema {INDEX_SCHEMA}. Rebuild: scripts/index.py")


def read_index(include_references: bool = False):
    """Yield index records. Streams -- the index can be larger than memory.

    Reference repositories are held out unless asked for. That default is the
    mechanism behind `configured_references`: a reference is evidence about the
    wider world, and the moment it reaches a command that computes what is
    ALWAYS true, the contract being reproduced is no longer the exemplar's.
    Opting in is one keyword; `practice` always does, and `deps` does only
    when passed `--references`.

    A held-out repository is not opened, not filtered -- it is in a directory
    this call never walks into.
    """
    wanted = indexed_repositories(ROLE_ORDER if include_references
                                  else CONTRACT_ROLES)
    if not wanted:
        # Two different answers, and conflating them turns a real finding into
        # what looks like a tooling problem: nothing built at all, versus an
        # index holding references and nothing to hold them out *of*.
        if indexed_repositories():
            sys.exit(
                f"{display_path(index_root())} holds reference codebases only.\n"
                "References are evidence, never a template, so no contract can be"
                " computed from them.\nConfigure an `exemplar_corpus` or a"
                " `solution`, then rebuild:  scripts/index.py"
            )
        sys.exit(
            f"no index at {display_path(index_root())}\n"
            "build one first:  ./.venv/Scripts/python.exe "
            ".claude/skills/app-builder/scripts/index.py"
        )
    for shard in wanted:
        with shard["records"].open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)


def _is_skipped_dir(name: str) -> bool:
    return (name in SKIP_DIRS or name.startswith(".")
            or name.lower().startswith(SKIP_PREFIXES))


def _is_corpus_dir(path: Path, corpus: Path) -> bool:
    """Whether this directory *is* the reference corpus.

    A second lock on the same door. `_is_skipped_dir` already prunes it,
    but only because `.reference_corpus` happens to start with a dot -- the
    corpus is protected by a naming coincidence, not by a rule, and dropping
    the dot from `CORPUS_DIR` would silently make twenty-three reference
    codebases walkable as part of whatever contains them.

    That is the worst failure this skill has, not a small one: a reference
    swept in as an exemplar does not fail, it votes. Twenty-three of them
    outnumber one exemplar, and the contract being reproduced quietly becomes
    an average of the internet -- exactly what `configured_references` exists
    to prevent, arriving through the walk instead of through the config.

    Cheap on purpose: the name is compared first, so the resolve only happens
    for a directory that could actually be it.
    """
    if path.name != corpus.name:
        return False
    try:
        return path.resolve() == corpus
    except OSError:
        return False


def _walking_inside_corpus(root: Path, corpus: Path) -> bool:
    """Whether the walk *started* in the corpus -- indexing a reference itself.

    The guard has to be one-directional. Indexing `django` means the root is
    already inside `.reference_corpus`, and a rule that refused to walk the
    corpus at all would report every reference as empty.
    """
    try:
        resolved = root.resolve()
    except OSError:
        return False
    return resolved == corpus or corpus in resolved.parents


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
    corpus = corpus_root()
    guard_corpus = not _walking_inside_corpus(root, corpus)
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        depth = len(here.relative_to(root).parts) if here != root else 0
        if depth >= max_depth:
            dirnames[:] = []
        dirnames[:] = [d for d in dirnames if not _is_skipped_dir(d)
                       and not (guard_corpus and _is_corpus_dir(here / d, corpus))]
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
    corpus = corpus_root()
    guard_corpus = not _walking_inside_corpus(root, corpus)
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        dirnames[:] = [
            d for d in dirnames
            if not _is_skipped_dir(d)
            and not (guard_corpus and _is_corpus_dir(here / d, corpus))
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
    corpus = corpus_root()
    guard_corpus = not _walking_inside_corpus(root, corpus)
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        dirnames[:] = [
            d for d in dirnames
            if not _is_skipped_dir(d)
            and not (guard_corpus and _is_corpus_dir(here / d, corpus))
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
