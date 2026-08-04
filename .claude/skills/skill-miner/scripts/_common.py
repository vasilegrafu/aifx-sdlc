"""Shared helpers for the skill-miner scripts. Standard library only.

Every script here is polyglot by construction: nothing parses a language, all
signals come from file layout, line shape, and git history.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

# Dot-directories are skipped, except these: enforcement config lives in them,
# and a convention a machine rejects is the cheapest evidence there is.
KEEP_DOTDIRS = {".github", ".gitlab", ".circleci", ".buildkite", ".husky",
                ".azure-pipelines", ".claude", ".config", ".changeset"}

IGNORED_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules", "__pycache__",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".gradle", ".idea",
    ".vs", ".vscode", "dist", "build", "out", "target", "bin", "obj", "vendor",
    "third_party", "coverage", ".next", ".nuxt", ".svelte-kit", ".terraform",
    "site-packages", "Pods", "DerivedData", ".cache", ".turbo", "bower_components",
}

BINARY_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".svg", ".pdf", ".zip",
    ".gz", ".tar", ".7z", ".rar", ".jar", ".war", ".class", ".exe", ".dll",
    ".so", ".dylib", ".bin", ".woff", ".woff2", ".ttf", ".eot", ".mp3", ".mp4",
    ".mov", ".avi", ".pyc", ".pyo", ".wasm", ".db", ".sqlite", ".lock",
}

CODE_EXT = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs", ".java",
    ".kt", ".kts", ".scala", ".rb", ".php", ".cs", ".fs", ".c", ".h", ".cc",
    ".cpp", ".hpp", ".m", ".mm", ".swift", ".dart", ".ex", ".exs", ".erl",
    ".clj", ".hs", ".ml", ".lua", ".pl", ".r", ".sql", ".sh", ".bash", ".ps1",
    ".vue", ".svelte", ".tf", ".proto", ".graphql", ".gql",
}

MAX_BYTES = 400_000  # skip generated blobs; nothing hand-written is this big

DAY = 86400


# ---------------------------------------------------------------- filesystem

def walk(root: Path, includes=None, max_bytes: int = MAX_BYTES):
    """Yield text-ish files under root, honouring --include scoping."""
    roots = [root / i for i in includes] if includes else [root]
    seen = set()
    for base in roots:
        if not base.exists():
            print(f"warning: {base} does not exist", file=sys.stderr)
            continue
        if base.is_file():
            if base not in seen:
                seen.add(base)
                yield base
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [
                d for d in dirnames
                if (d not in IGNORED_DIRS and not d.startswith(".")) or d in KEEP_DOTDIRS
            ]
            for name in filenames:
                p = Path(dirpath) / name
                if p in seen:
                    continue
                if p.suffix.lower() in BINARY_EXT:
                    continue
                try:
                    if p.stat().st_size > max_bytes:
                        continue
                except OSError:
                    continue
                seen.add(p)
                yield p


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def is_code(path: Path) -> bool:
    return path.suffix.lower() in CODE_EXT


# ---------------------------------------------------------------------- git

def git(root: Path, *args: str, timeout: int = 120) -> str | None:
    """Run a git command in root. Returns None when git or the repo is absent."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout


def has_git(root: Path) -> bool:
    return git(root, "rev-parse", "--git-dir") is not None


_HISTORY_CACHE: dict[tuple[str, int], dict[str, dict]] = {}


def file_history(root: Path, max_commits: int = 20000) -> dict[str, dict]:
    """path -> {"last": ts, "first": ts, "authors": set, "recent_authors": set}.

    One `git log` pass for every dating and authorship question, cached: on a
    large repo a per-file version takes minutes and this takes seconds.

    `recent_authors` are those who touched the file in the last year — the ones
    whose habits are still shaping the codebase.
    """
    key = (str(root), max_commits)
    if key in _HISTORY_CACHE:
        return _HISTORY_CACHE[key]

    out = git(root, "log", f"--max-count={max_commits}", "--no-merges",
              "--name-only", "--format=%x01%at%x02%an")
    hist: dict[str, dict] = {}
    if not out:
        _HISTORY_CACHE[key] = hist
        return hist

    import time as _time
    year_ago = _time.time() - 365 * DAY
    ts, author = 0, ""
    for line in out.splitlines():
        if line.startswith("\x01"):
            head = line[1:]
            tstr, _, author = head.partition("\x02")
            try:
                ts = int(tstr)
            except ValueError:
                ts = 0
        elif line.strip():
            rec = hist.setdefault(line.strip(),
                                  {"last": ts, "first": ts, "authors": set(), "recent_authors": set()})
            rec["first"] = ts          # log is newest-first: the last write wins
            rec["authors"].add(author)
            if ts >= year_ago:
                rec["recent_authors"].add(author)
    _HISTORY_CACHE[key] = hist
    return hist


def last_touch_map(root: Path, max_commits: int = 20000) -> dict[str, int]:
    return {p: r["last"] for p, r in file_history(root, max_commits).items()}


def first_touch_map(root: Path, max_commits: int = 20000) -> dict[str, int]:
    return {p: r["first"] for p, r in file_history(root, max_commits).items()}


def repo_authors(root: Path, max_commits: int = 20000) -> set[str]:
    """Every author in the window. One name means author spread says nothing."""
    out: set[str] = set()
    for rec in file_history(root, max_commits).values():
        out |= rec["authors"]
    return out


def age_days(ts: int, now: float | None = None) -> float:
    if not ts:
        return float("inf")
    return ((now or time.time()) - ts) / DAY


# ------------------------------------------------------------------ output

def table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "_none_\n"
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |")
    return "\n".join(out) + "\n"


def section(title: str) -> str:
    return f"\n## {title}\n\n"


def emit(text: str) -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(text)
