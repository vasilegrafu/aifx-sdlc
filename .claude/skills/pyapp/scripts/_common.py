"""Shared helpers for the pyapp scripts.

The index is never read into a conversation whole. Everything here is built so
that `query.py` can filter a multi-megabyte file down to a few hundred lines
before anything reads it.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Directories that are never source: build output, caches, vendored copies.
SKIP_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", ".tox", "node_modules", "site-packages",
    "build", "dist", ".eggs", ".idea", ".vscode",
}

def skill_root() -> Path:
    """The pyapp skill directory these scripts live in."""
    return Path(__file__).resolve().parents[1]


def repo_root() -> Path:
    """The checkout holding config.json."""
    return skill_root().parents[2]


# ------------------------------------------------------------------ config


def load_config() -> dict:
    """The `pyapp` block of `config.json`.

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

    block = cfg.get("pyapp") or {}
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
                    "exclude": tuple(entry.get("exclude") or ())})
    return out


def solution_dir() -> Path:
    """Where generated applications are built. Named in config.json; `solution` if absent."""
    configured = load_config().get("solution") or "solution"
    path = Path(configured)
    return path.resolve() if path.is_absolute() else (repo_root() / path).resolve()


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
            f".claude/skills/pyapp/scripts/index.py --name {name} <codebase-root>..."
        )
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def _is_excluded(relpath: str, excluded: tuple[str, ...]) -> bool:
    low = relpath.lower()
    return any(low == e or low.startswith(e + "/") for e in excluded)


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
            if d not in SKIP_DIRS and not d.startswith(".")
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
