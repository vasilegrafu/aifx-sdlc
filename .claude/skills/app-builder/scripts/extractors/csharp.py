"""C# extraction, through Roslyn -- the compiler's own parser.

Syntax only: no compilation is built, because that would need every project
restored, and the structure of a family is visible without it. What that costs is
named honestly in `references/languages.md` and reported by `query.py calls`:
an extension method is declared outside the type it appears to hang off, so a
called-but-not-defined check cannot resolve it from syntax alone.

The adapter is a small dotnet tool built once, on demand. If you are reading a
C# codebase, the SDK is present by definition.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from _common import rel

LANGUAGE = "csharp"
FIDELITY = "ast"
EXTENSIONS = (".cs",)

PROJECT = Path(__file__).resolve().parents[1] / "adapters" / "CsExtract"
ASSEMBLY = PROJECT / "bin" / "Release" / "net9.0" / "CsExtract.dll"


def available(root: Path | None = None) -> str | None:
    """None when usable, otherwise the reason -- which the index must report."""
    if shutil.which("dotnet") is None:
        return "dotnet is not on PATH"
    if not (PROJECT / "CsExtract.csproj").is_file():
        return f"adapter project missing: {PROJECT}"
    return None


def _ensure_built() -> str | None:
    """Build the adapter once. Returns a reason on failure, None on success."""
    if ASSEMBLY.is_file():
        return None
    print(f"  building the C# adapter (first run): {PROJECT.name}", file=sys.stderr)
    try:
        proc = subprocess.run(
            ["dotnet", "build", "-c", "Release", "-v", "q", "--nologo", str(PROJECT)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=600)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"dotnet build failed: {exc}"
    if proc.returncode != 0 or not ASSEMBLY.is_file():
        tail = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
        return f"dotnet build exited {proc.returncode}: {tail[-1] if tail else ''}"
    return None


def extract(files, root: Path, repo: str, commits=None, timeout: int = 600):
    if not files:
        return
    reason = _ensure_built()
    if reason:
        yield {"k": "unparsed", "lang": LANGUAGE, "repo": repo, "path": "",
               "error": reason[:200]}
        return

    payload = {"repo": repo, "files": []}
    for path in files:
        try:
            mtime = int(path.stat().st_mtime)
        except OSError:
            mtime = 0
        payload["files"].append({
            "path": str(path),
            "mtime": mtime,
            "commit": (commits or {}).get(rel(path, root)),
        })

    try:
        proc = subprocess.run(
            ["dotnet", str(ASSEMBLY), str(root)],
            input=json.dumps(payload), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        yield {"k": "unparsed", "lang": LANGUAGE, "repo": repo, "path": "",
               "error": f"adapter failed: {exc}"[:200]}
        return

    notes = [ln for ln in (proc.stderr or "").splitlines() if ln.strip()]
    if proc.returncode != 0:
        yield {"k": "unparsed", "lang": LANGUAGE, "repo": repo, "path": "",
               "error": f"adapter exited {proc.returncode}: "
                        f"{notes[-1] if notes else 'no output'}"[:200]}
        return
    for note in notes:
        print(note.rstrip(), file=sys.stderr)

    for line in proc.stdout.splitlines():
        line = line.strip()
        if line:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
