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

# The config block this skill reads. Earlier names are still accepted: a rename
# of the skill should not silently stop it finding the codebases it was given.
CONFIG_KEYS = ("app-builder", "pyapp-builder", "pyapp")

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


def configured_repositories() -> list[dict]:
    """`[{name, path, exists}]` from config. Paths may be relative to the root."""
    out = []
    for entry in load_config().get("repositories") or []:
        if not isinstance(entry, dict) or not entry.get("path"):
            continue
        path = Path(entry["path"])
        if not path.is_absolute():
            path = repo_root() / path
        path = path.resolve()
        out.append({"name": entry.get("name") or path.name,
                    "path": path, "exists": path.is_dir(),
                    "exclude": tuple(entry.get("exclude") or ()),
                    "is_target": False})
    return out


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
            "is_target": True}


def solution_dir() -> Path:
    """Where generated applications are built. Named in config.json; `solution` if absent."""
    return configured_solution()["path"]


def workspace(name: str) -> Path:
    """Where an index and its decisions live: `<skill>/.data/<name>/`.

    Gitignored, and it has to be -- the skill around it is tracked, so a
    blanket `git add .` would otherwise commit structure derived from someone
    else's repository along with the skill.
    """
    return skill_root() / ".data" / name


def index_path(name: str) -> Path:
    return workspace(name) / "index.jsonl"


def read_index(name: str):
    """Yield index records. Streams -- the file can be larger than memory."""
    path = index_path(name)
    if not path.exists():
        sys.exit(
            f"no index named {name!r} at {path}\n"
            f"build one first:  ./.venv/Scripts/python.exe "
            f".claude/skills/app-builder/scripts/index.py --name {name} <codebase-root>..."
        )
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def _is_skipped_dir(name: str) -> bool:
    return (name in SKIP_DIRS or name.startswith(".")
            or name.lower().startswith(SKIP_PREFIXES))


def _is_excluded(relpath: str, excluded: tuple[str, ...]) -> bool:
    low = relpath.lower()
    return any(low == e or low.startswith(e + "/") for e in excluded)


def iter_source_files(root: Path, max_bytes: int, exclude: tuple[str, ...] = (),
                      extensions: tuple[str, ...] = (".py",)):
    """Walk a codebase for files any extractor can read. See iter_py_files."""
    lowered = tuple(e.lower() for e in extensions)
    excluded = tuple(e.strip("/").lower() for e in exclude if e.strip("/"))
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        dirnames[:] = [
            d for d in dirnames
            if not _is_skipped_dir(d)
            and not _is_excluded(rel(here / d, root), excluded)
        ]
        for fn in filenames:
            if not fn.lower().endswith(lowered):
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
